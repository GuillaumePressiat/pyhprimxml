"""Écriture de messages HPRIM XML.

Entrée : un dictionnaire imbriqué au format xmltodict, c'est-à-dire le même
format que celui que produit la lecture (``read_hprimxml``) :

- les attributs et les éléments enfants sont des clés du même dictionnaire
  (préfixe ``@`` accepté mais facultatif) : c'est le XSD qui tranche ;
- un élément répété est une liste ;
- un élément à contenu simple portant des attributs utilise la clé ``#text``.

L'ordre des clés n'a pas d'importance : les enfants sont émis dans l'ordre du XSD.
"""
from __future__ import annotations

import datetime as dt
import warnings
from decimal import Decimal
from pathlib import Path
from typing import Any

import lxml.etree as ET

from pyhprimxml.xsd import HPRIM_NS, Schema, get_schema, validate

DEFAULT_VERSION = "2.4"


class HprimWriteError(ValueError):
    pass


def format_value(v: Any, xsd_type: str | None = None) -> str:
    """Formate une valeur Python au format XSD attendu.

    Le type XSD cible corrige les dates venues de pandas (datetime64 sans type date) :
    un datetime vers ``xsd:date`` devient une date, une date vers ``xsd:dateTime`` minuit.
    """
    if hasattr(v, "to_pydatetime"):  # pandas.Timestamp
        v = v.to_pydatetime()
    if xsd_type == "date" and isinstance(v, dt.datetime):
        v = v.date()
    elif xsd_type == "time" and isinstance(v, dt.datetime):
        v = v.time()
    elif xsd_type == "dateTime" and isinstance(v, dt.date) and not isinstance(v, dt.datetime):
        v = dt.datetime.combine(v, dt.time())
    if isinstance(v, bool):
        return "oui" if v else "non"
    if isinstance(v, dt.datetime):
        return v.replace(microsecond=0, tzinfo=None).isoformat()
    if isinstance(v, dt.date):
        return v.isoformat()
    if isinstance(v, dt.time):
        return v.replace(microsecond=0).isoformat()
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    if isinstance(v, Decimal):
        return format(v, "f")
    return str(v)


def _is_empty(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and v != v:  # NaN pandas
        return True
    if isinstance(v, str) and v.strip() == "":
        return True
    if isinstance(v, (dict, list)) and len(v) == 0:
        return True
    return False


def _key(d: dict, name: str) -> str | None:
    if name in d:
        return name
    if f"@{name}" in d:
        return f"@{name}"
    return None


class _Builder:
    def __init__(self, schema: Schema, ns: str | None, drop_empty: bool, strict: bool):
        self.schema = schema
        self.ns = ns
        self.drop_empty = drop_empty
        self.strict = strict

    def tag(self, name: str) -> str:
        return f"{{{self.ns}}}{name}" if self.ns else name

    def build(self, parent: ET._Element | None, name: str, value: Any, type_name: str | None,
              path: str, required: bool = False) -> ET._Element | None:
        if isinstance(value, list):
            out = None
            for i, item in enumerate(value):
                out = self.build(parent, name, item, type_name, f"{path}[{i}]", required)
            return out
        # un élément complexe obligatoire est conservé même vide (ex. <diagnostics/>)
        keep = required and self.schema.is_complex(type_name) and isinstance(value, dict)
        if self.drop_empty and _is_empty(value) and not keep:
            return None

        el = ET.Element(self.tag(name), nsmap={None: self.ns} if parent is None and self.ns else None)

        if not self.schema.is_complex(type_name):
            if isinstance(value, dict):
                raise HprimWriteError(f"{path} : valeur simple attendue, dictionnaire reçu")
            # valeur vide conservée (drop_empty=False) : élément vide <x/>, comme xml2 en R
            el.text = None if _is_empty(value) else format_value(value, type_name)
        else:
            ct = self.schema.ctype(type_name)
            if not isinstance(value, dict):
                if ct.text:  # contenu simple sans attribut renseigné
                    value = {"#text": value}
                else:
                    raise HprimWriteError(f"{path} : élément complexe attendu, valeur simple reçue ({value!r})")
            used = set()
            for a in ct.attrs:
                k = _key(value, a)
                if k is None:
                    continue
                used.add(k)
                v = value[k]
                if self.drop_empty and _is_empty(v):
                    continue
                el.set(a, "" if v is None else format_value(v))
            if ct.text and "#text" in value:
                used.add("#text")
                if not _is_empty(value["#text"]) or not self.drop_empty:
                    el.text = format_value(value["#text"]) if not _is_empty(value["#text"]) else None
            for cname in ct.child_names():
                k = _key(value, cname)
                if k is None:
                    continue
                used.add(k)
                self.build(el, cname, value[k], ct.child_type(cname), f"{path}/{cname}",
                           cname in ct.required)
            unknown = [k for k in value if k not in used and not k.startswith("@xmlns") and k != "xmlns"]
            if unknown:
                msg = f"{path} : clés inconnues du XSD {self.schema.version} : {unknown}"
                if self.strict:
                    raise HprimWriteError(msg)
                warnings.warn(msg, stacklevel=2)
            if (self.drop_empty and not keep and len(el) == 0 and not el.attrib
                    and not (el.text or "").strip()):
                return None

        if parent is not None:
            parent.append(el)
        return el


def to_element(tree: dict, *, version: str | None = None, xmlns: str | None = HPRIM_NS,
               drop_empty: bool = True, strict: bool = True) -> ET._Element:
    """Construit l'élément racine lxml à partir d'un dictionnaire ``{racine: {...}}``.

    Args:
        tree: dictionnaire au format xmltodict (celui de ``parse_xml``).
        version: version du schéma. Par défaut l'attribut ``version`` du message, sinon 2.4.
            Si renseignée, elle remplace aussi l'attribut.
        xmlns: namespace à déclarer ; ``None`` ou ``""`` : pas de namespace.
        drop_empty: supprime les éléments et attributs vides (None, "", NaN), sauf les
            éléments complexes obligatoires du XSD.
        strict: lève une erreur si une clé ne correspond à rien dans le XSD
            (sinon simple avertissement).

    Returns:
        L'élément racine lxml.

    Raises:
        HprimWriteError: structure incompatible avec le XSD.
    """
    if len(tree) != 1:
        raise HprimWriteError("Le dictionnaire doit avoir une seule clé : l'élément racine")
    root_name, content = next(iter(tree.items()))
    content = dict(content)
    for k in ("@xmlns", "xmlns"):
        content.pop(k, None)
    vkey = _key(content, "version")
    if version is None:
        version = str(content[vkey]) if vkey else DEFAULT_VERSION
    if vkey:
        content.pop(vkey)
    content["version"] = version

    schema = get_schema(version, root_name)
    builder = _Builder(schema, xmlns or None, drop_empty, strict)
    return builder.build(None, root_name, content, schema.root_type(), root_name)


def to_xml(tree: dict, *, version: str | None = None, xmlns: str | None = HPRIM_NS,
           encoding: str = "UTF-8", pretty: bool = True, drop_empty: bool = True,
           strict: bool = True, validate_xsd: str | bool = False) -> bytes:
    """Sérialise un message HPRIM XML à partir d'un dictionnaire.

    Les enfants sont émis dans l'ordre du XSD, quel que soit l'ordre des clés ; le XSD
    décide aussi si une clé est un attribut ou un élément.

    Args:
        tree: dictionnaire ``{racine: {...}}`` au format xmltodict.
        version: version du schéma (voir ``to_element``).
        xmlns: ``HPRIM_NS`` (défaut) ; ``None`` : aucune déclaration ; ``""`` : écrit
            ``xmlns=""`` littéralement sur la racine.
        encoding: encodage du fichier (UTF-8 par défaut).
        pretty: indentation (deux espaces, mise en forme de libxml2).
        drop_empty: voir ``to_element``.
        strict: voir ``to_element``.
        validate_xsd: ``False``, ``"warn"`` ou ``"error"`` (``True`` équivaut à ``"error"``).

    Returns:
        Le contenu XML, déclaration comprise.

    Raises:
        HprimWriteError: structure incompatible ou, avec ``validate_xsd="error"``,
            message non conforme au XSD.
    """
    root = to_element(tree, version=version, xmlns=xmlns, drop_empty=drop_empty, strict=strict)
    if validate_xsd:
        errors = validate(root)
        if errors:
            msg = "XML non conforme au XSD :\n" + "\n".join(errors[:20])
            if validate_xsd == "warn":
                warnings.warn(msg, stacklevel=2)
            else:
                raise HprimWriteError(msg)
    decl = f'<?xml version="1.0" encoding="{encoding}" standalone="yes"?>\n'.encode("ascii")
    # mise en forme par libxml2 (comme xml2 en R) : indentation de deux espaces
    out = decl + ET.tostring(root, encoding=encoding, xml_declaration=False, pretty_print=pretty)
    if not out.endswith(b"\n"):  # mode compact : saut de ligne final, comme xml2 en R
        out += b"\n"
    if xmlns == "":
        name = ET.QName(root).localname.encode()
        out = out.replace(b"<" + name, b"<" + name + b' xmlns=""', 1)
    return out


def write_xml(tree: dict, path: str | Path, **kwargs: Any) -> Path:
    """Écrit un message HPRIM XML dans un fichier.

    Args:
        tree: dictionnaire ``{racine: {...}}``.
        path: fichier de sortie.
        **kwargs: options de ``to_xml``.

    Returns:
        Le chemin écrit.
    """
    path = Path(path)
    path.write_bytes(to_xml(tree, **kwargs))
    return path
