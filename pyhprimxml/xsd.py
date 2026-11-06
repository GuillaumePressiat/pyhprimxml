"""Introspection et validation des schémas HPRIM XML vendorisés.

L'écriture s'appuie sur le XSD pour deux choses que le tabulaire ne porte pas :
- l'ordre des éléments enfants (xsd:sequence) ;
- la distinction attribut / élément pour une même clé de dictionnaire.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import lxml.etree as ET

HPRIM_NS = "http://www.hprim.org/hprimXML"
XS = "{http://www.w3.org/2001/XMLSchema}"
SCHEMA_DIR = Path(__file__).parent / "schemas"


def available_versions() -> list[str]:
    return sorted(p.name for p in SCHEMA_DIR.iterdir() if p.is_dir())


@dataclass
class ComplexType:
    attrs: list[str] = field(default_factory=list)
    # (nom de l'élément enfant, nom du type) dans l'ordre du XSD
    children: list[tuple[str, str | None]] = field(default_factory=list)
    text: bool = False  # simpleContent : l'élément porte une valeur texte
    required: set[str] = field(default_factory=set)  # enfants minOccurs >= 1 (hors choice)
    repeated: set[str] = field(default_factory=set)  # enfants maxOccurs > 1
    text_type: str | None = None  # type de la valeur texte (simpleContent)

    def child_type(self, name: str) -> str | None:
        for n, t in self.children:
            if n == name:
                return t
        raise KeyError(name)

    def child_names(self) -> list[str]:
        seen: list[str] = []
        for n, _ in self.children:
            if n not in seen:
                seen.append(n)
        return seen


def _local(qname: str | None) -> str | None:
    if qname is None:
        return None
    return qname.split(":", 1)[1] if ":" in qname else qname


class Schema:
    """Schéma d'un type de message (ex. evenementsPMSI) pour une version donnée."""

    def __init__(self, version: str, root: str):
        self.version = version
        self.root = root
        self.dir = SCHEMA_DIR / version / "ns"
        if not self.dir.exists():
            raise ValueError(f"Version HPRIM inconnue : {version!r} (disponibles : {available_versions()})")
        self.entry = self._find_entry()
        self._ctypes_xml: dict[str, ET._Element] = {}
        self._groups: dict[str, ET._Element] = {}
        self._attr_groups: dict[str, ET._Element] = {}
        self._elements: dict[str, ET._Element] = {}
        self._stypes: dict[str, ET._Element] = {}
        self._load(self.entry, set())
        self._cache: dict[str, ComplexType] = {}
        self._anon = 0

    # ---- chargement -------------------------------------------------------
    def _find_entry(self) -> Path:
        pat = re.compile(rf'<xsd:element\s+name="{re.escape(self.root)}"')
        for f in sorted(self.dir.glob("msg*.xsd")):
            if pat.search(f.read_text(encoding="utf-8")):
                return f
        raise ValueError(f"Aucun message {self.root!r} dans les schémas {self.version}")

    def _load(self, path: Path, seen: set[Path]) -> None:
        if path in seen:
            return
        seen.add(path)
        doc = ET.parse(str(path)).getroot()
        for inc in doc.iter(f"{XS}include"):
            self._load(path.parent / inc.get("schemaLocation"), seen)
        for node in doc:
            name = node.get("name")
            if node.tag == f"{XS}complexType":
                self._ctypes_xml[name] = node
            elif node.tag == f"{XS}simpleType":
                self._stypes[name] = node
            elif node.tag == f"{XS}group":
                self._groups[name] = node
            elif node.tag == f"{XS}attributeGroup":
                self._attr_groups[name] = node
            elif node.tag == f"{XS}element":
                self._elements[name] = node

    # ---- introspection ----------------------------------------------------
    def root_type(self) -> str:
        return _local(self._elements[self.root].get("type"))

    def is_complex(self, type_name: str | None) -> bool:
        return type_name is not None and type_name in self._ctypes_xml

    _KINDS = {
        "date": "date", "dateTime": "datetime", "time": "time",
        "integer": "int", "int": "int", "long": "int", "short": "int", "positiveInteger": "int",
        "nonNegativeInteger": "int", "negativeInteger": "int", "nonPositiveInteger": "int",
    }

    def simple_kind(self, type_name: str | None) -> str:
        """Nature d'un type simple : date, datetime, time, int ou str (décimaux en str)."""
        seen = set()
        while type_name and type_name in self._stypes and type_name not in seen:
            seen.add(type_name)
            r = self._stypes[type_name].find(f"{XS}restriction")
            if r is None:
                return "str"  # union, list
            type_name = _local(r.get("base"))
        return self._KINDS.get(type_name, "str")

    def ctype(self, type_name: str) -> ComplexType:
        if type_name not in self._cache:
            self._cache[type_name] = self._build(self._ctypes_xml[type_name])
        return self._cache[type_name]

    def _build(self, node: ET._Element) -> ComplexType:
        ct = ComplexType()
        for child in node:
            tag = child.tag
            if tag in (f"{XS}complexContent", f"{XS}simpleContent"):
                for der in child:
                    if der.tag not in (f"{XS}extension", f"{XS}restriction"):
                        continue
                    base = _local(der.get("base"))
                    if self.is_complex(base) and der.tag == f"{XS}extension":
                        b = self.ctype(base)
                        ct.attrs += b.attrs
                        ct.children += b.children
                        ct.required |= b.required
                        ct.repeated |= b.repeated
                        ct.text = b.text
                        ct.text_type = b.text_type
                    if tag == f"{XS}simpleContent":
                        ct.text = True
                        if not self.is_complex(base):
                            ct.text_type = base
                    self._collect(der, ct)
            else:
                self._collect_one(child, ct)
        return ct

    def _collect(self, node: ET._Element, ct: ComplexType, optional: bool = False,
                 repeated: bool = False) -> None:
        for child in node:
            self._collect_one(child, ct, optional, repeated)

    def _collect_one(self, child: ET._Element, ct: ComplexType, optional: bool = False,
                     repeated: bool = False) -> None:
        tag = child.tag
        many = child.get("maxOccurs", "1") not in ("0", "1")
        if tag in (f"{XS}sequence", f"{XS}choice", f"{XS}all"):
            opt = optional or tag == f"{XS}choice" or child.get("minOccurs") == "0"
            self._collect(child, ct, opt, repeated or many)
        elif tag == f"{XS}element":
            ename = child.get("name") or _local(child.get("ref"))
            if not optional and child.get("minOccurs", "1") != "0":
                ct.required.add(ename)
            if repeated or many:
                ct.repeated.add(ename)
            if child.get("ref"):
                ref = _local(child.get("ref"))
                ct.children.append((ref, _local(self._elements[ref].get("type"))))
            else:
                t = _local(child.get("type"))
                inline = child.find(f"{XS}complexType")
                if t is None and inline is not None:
                    self._anon += 1
                    t = f"__anon{self._anon}_{child.get('name')}"
                    self._ctypes_xml[t] = inline
                ct.children.append((child.get("name"), t))
        elif tag == f"{XS}attribute":
            ct.attrs.append(child.get("name") or _local(child.get("ref")))
        elif tag == f"{XS}group":
            self._collect(self._groups[_local(child.get("ref"))], ct)
        elif tag == f"{XS}attributeGroup":
            self._collect(self._attr_groups[_local(child.get("ref"))], ct)


@lru_cache(maxsize=None)
def get_schema(version: str, root: str) -> Schema:
    return Schema(version, root)


@lru_cache(maxsize=None)
def _xmlschema(version: str, root: str, namespaced: bool) -> ET.XMLSchema:
    entry = get_schema(version, root).entry
    path = entry if namespaced else entry.parent.parent / "nons" / entry.name
    return ET.XMLSchema(ET.parse(str(path)))


def validate(xml: bytes | ET._Element | ET._ElementTree, version: str | None = None) -> list[str]:
    """Valide un message contre le XSD de sa version.

    La variante de schéma (avec ou sans namespace) est choisie d'après le XML lui-même.

    Args:
        xml: contenu (bytes), élément ou arbre lxml.
        version: version du schéma ; par défaut l'attribut ``version`` du message.

    Returns:
        La liste des erreurs, vide si le message est conforme.
    """
    if isinstance(xml, bytes):
        xml = ET.fromstring(xml)
    root = xml.getroot() if isinstance(xml, ET._ElementTree) else xml
    qn = ET.QName(root)
    version = version or root.get("version")
    schema = _xmlschema(version, qn.localname, qn.namespace == HPRIM_NS)
    if schema.validate(root):
        return []
    return [f"ligne {e.line} : {e.message}" for e in schema.error_log]
