"""Suivi des dépôts de fichiers et de leurs marqueurs ``.ok``.

Protocole : l'émetteur dépose le ``.xml``, puis, une fois celui-ci écrit intégralement,
un fichier ``.ok`` vide de même nom. Le destinataire ne traite un ``.xml`` qu'une fois son
``.ok`` présent. Avec ``fichier_ok=True``, les fonctions ``write_*`` appliquent ce
protocole ; ``read_*(..., exiger_ok=True)`` ne lit que les dépôts terminés.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import polars as pl

from pyhprimxml.common import Sources, Table, iter_sources


def _mtime(p: Path) -> dt.datetime:
    return dt.datetime.fromtimestamp(p.stat().st_mtime)


def suivi_depots(fichiers: Sources, *, extension_ok: str = ".ok",
                 backend: str = "polars") -> Table:
    """État des dépôts : quels ``.xml`` ont leur ``.ok``, lesquels sont encore incomplets.

    Côté émetteur, la fonction vérifie que tout a été déposé ; côté destinataire, elle
    indique ce qui est prêt à être traité.

    Args:
        fichiers: dossier, motif glob ou liste de ``.xml``.
        extension_ok: extension des fichiers marqueurs.
        backend: ``"polars"`` ou ``"pandas"``.

    Returns:
        Une ligne par fichier, avec ``evt_id`` (nom sans extension, même clé que les
        tables de lecture), ``fichier``, ``date_xml``, ``complet`` (le ``.ok`` est
        présent) et ``date_ok`` (dates de modification des fichiers). Les ``.ok`` d'un
        dossier qui n'ont pas de ``.xml`` correspondant sont ajoutés avec ``fichier`` nul
        et ``complet`` faux.
    """
    rows, vus, dossiers = [], set(), set()
    for evt_id, src in iter_sources(fichiers):
        if not isinstance(src, Path):
            continue
        ok = src.with_suffix(extension_ok)
        present = ok.exists()
        vus.add(ok.resolve())
        dossiers.add(src.parent)
        rows.append({"evt_id": evt_id, "fichier": str(src), "date_xml": _mtime(src),
                     "complet": present, "date_ok": _mtime(ok) if present else None})
    for d in sorted(dossiers):
        for ok in sorted(d.glob(f"*{extension_ok}")):
            if ok.resolve() not in vus:
                rows.append({"evt_id": ok.stem, "fichier": None, "date_xml": None,
                             "complet": False, "date_ok": _mtime(ok)})
    schema = {"evt_id": pl.String, "fichier": pl.String, "date_xml": pl.Datetime("us"),
              "complet": pl.Boolean, "date_ok": pl.Datetime("us")}
    df = pl.DataFrame(rows, schema=schema)
    return df.to_pandas() if backend == "pandas" else df
