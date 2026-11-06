"""Lecture XML -> dictionnaire (format accepté par ``to_xml``), guidée par le XSD.

Par rapport à xmltodict :
- un élément répétable selon le XSD est toujours une liste (même avec 1 seul élément) ;
- les valeurs sont typées d'après le XSD : date, datetime, time, int (le reste en str ;
  les attributs restent en str) ;
- le namespace, quel qu'il soit (ou son absence), est ignoré.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import lxml.etree as ET

from pyhprimxml.xsd import Schema, get_schema

DEFAULT_VERSION = "2.4"


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _convert(text: str | None, kind: str) -> Any:
    if text is None or text.strip() == "":
        return None
    t = text.strip()
    try:
        if kind == "date":
            return dt.date.fromisoformat(t[:10])
        if kind == "datetime":
            return dt.datetime.fromisoformat(t.replace("Z", "+00:00")).replace(tzinfo=None)
        if kind == "time":
            return dt.time.fromisoformat(t)
        if kind == "int":
            return int(t)
    except ValueError:
        return t  # valeur non conforme : on la garde telle quelle
    return t


def _generic(el: ET._Element) -> Any:
    """Élément absent du XSD : conversion sans typage."""
    d: dict = dict(el.attrib)
    for c in el:
        if isinstance(c.tag, str):
            d.setdefault(_local(c.tag), []).append(_generic(c))
    d = {k: (v[0] if isinstance(v, list) and len(v) == 1 else v) for k, v in d.items()}
    text = el.text.strip() if el.text and el.text.strip() else None
    if not d:
        return text
    if text:
        d["#text"] = text
    return d


def _node(el: ET._Element, type_name: str | None, schema: Schema, typed: bool) -> Any:
    if not schema.is_complex(type_name):
        return _convert(el.text, schema.simple_kind(type_name) if typed else "str")
    ct = schema.ctype(type_name)
    d: dict = {_local(k): v for k, v in el.attrib.items()}
    for child in el:
        if not isinstance(child.tag, str):  # commentaires, PI
            continue
        name = _local(child.tag)
        try:
            value = _node(child, ct.child_type(name), schema, typed)
        except KeyError:
            value = _generic(child)
        if name in ct.repeated:
            d.setdefault(name, []).append(value)
        elif name in d:  # répétition non prévue par le XSD
            d[name] = (d[name] if isinstance(d[name], list) else [d[name]]) + [value]
        else:
            d[name] = value
    if ct.text:
        text = _convert(el.text, schema.simple_kind(ct.text_type) if typed else "str")
        if not d:
            return text
        if text is not None:
            d["#text"] = text
    return d


def parse_xml(source: str | Path | bytes, *, version: str | None = None,
              typed: bool = True) -> dict:
    """Lit un message HPRIM XML en dictionnaire ``{racine: {...}}``.

    Lecture guidée par le XSD : les éléments répétables sont toujours des listes et les
    valeurs sont typées (date, datetime, time, int ; le reste et les attributs en texte).
    Le namespace est ignoré. Le résultat est accepté tel quel par ``to_xml``.

    Args:
        source: chemin de fichier ou contenu (bytes).
        version: schéma à utiliser ; par défaut l'attribut ``version`` du message.
        typed: ``False`` pour garder toutes les valeurs en texte.

    Returns:
        Le message sous forme de dictionnaire.
    """
    if isinstance(source, bytes):
        root = ET.fromstring(source)
    else:
        root = ET.parse(str(source)).getroot()
    name = _local(root.tag)
    version = version or root.get("version") or DEFAULT_VERSION
    schema = get_schema(version, name)
    return {name: _node(root, schema.root_type(), schema, typed)}
