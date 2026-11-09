"""Briques partagées par les couches tabulaires (PMSI, serveur d'actes, états patient).

Colonnes-chemins
----------------
En plus des colonnes « métier » nommées (``ipp``, ``um``…), toute colonne dont le nom
contient ``/`` ou commence par ``@`` est un chemin XML relatif au nœud que décrit la
table ; ``@nom`` en dernier segment désigne un attribut. Exemples :

- table ``evenements`` : ``patient/@anonyme``, ``venue/@prive``,
  ``patient/identifiant/emetteur/@portee``
- table ``rum`` : ``@classant``, ``medecinResponsable/identification/code``
- table ``actes`` : ``CCAM/@remboursementExceptionnel``

Tout élément du XSD reste ainsi accessible sans colonne dédiée. Les valeurs nulles
sont ignorées.
"""
from __future__ import annotations

import datetime as dt
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Iterable, Iterator, Union


import polars as pl

if TYPE_CHECKING:  # pragma: no cover
    import pandas as pd

#: Table acceptée en entrée : DataFrame polars ou pandas.
Table = Union[pl.DataFrame, "pd.DataFrame"]
#: Source de lecture : fichier, dossier, motif glob, contenu, ou liste de ces éléments.
Sources = Union[str, Path, bytes, Iterable[Union[str, Path, bytes]]]

from pyhprimxml.io.output import HprimWriteError, to_xml
from pyhprimxml.xsd import HPRIM_NS


# ---- tables -----------------------------------------------------------------
def as_polars(df, name: str, required: list[str], colmap: dict | None = None) -> pl.DataFrame:
    """Normalise une table (polars, pandas ou None) et vérifie les colonnes obligatoires."""
    if df is None:
        df = pl.DataFrame({c: [] for c in required})
    if not isinstance(df, pl.DataFrame):
        df = pl.from_pandas(df)
    if colmap:
        df = df.rename({k: v for k, v in colmap.items() if k in df.columns})
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise HprimWriteError(f"Table {name} : colonnes obligatoires manquantes {missing}")
    return df


def rows_by(df: pl.DataFrame, key: str) -> dict[Any, list[dict]]:
    """Regroupe les lignes d'une table par valeur de ``key`` (ordre conservé)."""
    out: dict[Any, list[dict]] = {}
    for row in df.to_dicts():
        out.setdefault(row[key], []).append(row)
    return out


# ---- colonnes-chemins -------------------------------------------------------
def is_path(col: str) -> bool:
    return "/" in col or col.startswith("@")


def apply_paths(node: dict, row: dict) -> dict:
    """Fusionne les colonnes-chemins d'une ligne dans le nœud (en place)."""
    for col, value in row.items():
        if not is_path(col) or value is None:
            continue
        parts = [p for p in col.split("/") if p]
        cur = node
        for p in parts[:-1]:
            nxt = cur.get(p)
            if not isinstance(nxt, dict):
                nxt = {} if nxt is None else {"#text": nxt}
                cur[p] = nxt
            cur = nxt
        last = parts[-1].lstrip("@")
        cur[last] = value
    return node


def g(row: dict, col: str, default: Any = None) -> Any:
    v = row.get(col)
    return default if v is None else v


def to_datetime(d: Any, heure: Any = None) -> Any:
    """xsd:dateTime depuis une date et une heure facultative."""
    if d is None or isinstance(d, (dt.datetime, str)):
        return d
    if isinstance(heure, dt.time):
        return dt.datetime.combine(d, heure)
    return dt.datetime.combine(d, dt.time())


def date_heure(row: dict, date_col: str, heure_col: str) -> dict | None:
    if row.get(date_col) is None:
        return None
    return {"date": row[date_col], "heure": row.get(heure_col)}


def code(v: Any) -> dict | None:
    return None if v is None else {"code": v}


# ---- blocs communs ----------------------------------------------------------
ENTETE_KEYS = ["version", "acquittement_attendu", "mode_traitement", "identifiant_message",
               "date_heure_production", "emetteur", "emetteur_categorie", "destinataire",
               "destinataire_categorie", "commentaire"]


def ent(evt: dict, entete: dict, key: str, default: Any = None) -> Any:
    """Valeur d'en-tête : colonne de ``evenements`` en priorité, sinon dict ``entete``."""
    v = evt.get(key)
    if v is None:
        v = (entete or {}).get(key)
    return default if v is None else v


_NOM12 = re.compile(r"[A-Za-z0-9\-,_]{1,12}")


def check_identifiant_message(v: Any, evt_id: Any, fichier: str | None = None) -> str:
    """identifiantMessage est de type nom12 : 1 à 12 caractères parmi lettres, chiffres, - , _"""
    v = str(v)
    if not _NOM12.fullmatch(v):
        if fichier:
            raise HprimWriteError(
                f"Événement {evt_id} : le nom de fichier {fichier!r} ne peut pas servir "
                f"d'identifiantMessage ({v!r}) : 12 caractères au plus (sans l'extension), "
                f"parmi lettres, chiffres, - , _. Raccourcir evt_id ou le gabarit filename.")
        raise HprimWriteError(
            f"Événement {evt_id} : identifiantMessage {v!r} invalide (nom12 : 12 caractères max, "
            f"lettres, chiffres, - , _). Renseigner une colonne identifiant_message plus courte.")
    return v


def entete_tree(entete: dict, evt: dict) -> dict:
    """enteteMessage. Chaque clé de ``entete`` peut aussi être une colonne de
    ``evenements`` (valeur par événement, prioritaire) : voir ``ENTETE_KEYS``."""
    def agent(code_, categorie):
        return {"agents": {"agent": {"categorie": categorie, "code": code_}}}

    return {
        "modeTraitement": ent(evt, entete, "mode_traitement"),
        # contrôlé (et aligné sur le nom de fichier) par write_trees
        "identifiantMessage": str(ent(evt, entete, "identifiant_message", evt["evt_id"])),
        "dateHeureProduction": ent(evt, entete, "date_heure_production", dt.datetime.now()),
        "emetteur": agent(ent(evt, entete, "emetteur"),
                          ent(evt, entete, "emetteur_categorie", "application")),
        "destinataire": agent(ent(evt, entete, "destinataire"),
                              ent(evt, entete, "destinataire_categorie", "application")),
        "commentaireMessage": ent(evt, entete, "commentaire"),
    }


def patient_tree(e: dict) -> dict:
    """patient : ipp, ipp_recepteur, sexe, nom_usuel, nom_naissance, prenom, date_naissance."""
    rec = e.get("ipp_recepteur")
    return {
        "identifiant": {"emetteur": {"valeur": e["ipp"]},
                        "recepteur": {"valeur": rec} if rec is not None else None},
        "personnePhysique": {
            "sexe": e["sexe"],
            "nomUsuel": e.get("nom_usuel"),
            "nomNaissance": e.get("nom_naissance"),
            "prenoms": {"prenom": e.get("prenom")},
            "dateNaissance": {"date": e["date_naissance"]},
        },
    }


def venue_tree(e: dict) -> dict | None:
    """venue : nda, nda_recepteur, venue_date_entree, venue_heure_entree,
    venue_mode_entree, venue_uf_responsable, venue_date_sortie, venue_heure_sortie."""
    if e.get("nda") is None:
        return None
    rec = e.get("nda_recepteur")
    sortie = date_heure(e, "venue_date_sortie", "venue_heure_sortie")
    return {
        "identifiant": {"emetteur": {"valeur": e["nda"]},
                        "recepteur": {"valeur": rec} if rec is not None else None},
        "entree": {
            "dateHeureOptionnelle": date_heure(e, "venue_date_entree", "venue_heure_entree"),
            "modeEntree": code(e.get("venue_mode_entree")),
            "uniteFonctionnelleResponsable": code(e.get("venue_uf_responsable")),
        },
        "sortie": {"dateHeureOptionnelle": sortie} if sortie else None,
    }


def intervention_tree(e: dict) -> dict | None:
    """intervention : intervention_id, intervention_date_debut/heure_debut,
    intervention_date_fin/heure_fin, intervention_uf, demande_date, demande_heure, demande_uf."""
    if e.get("intervention_id") is None:
        return None
    demande = None
    if e.get("demande_date") is not None:
        demande = {"datePrescription": date_heure(e, "demande_date", "demande_heure"),
                   "uniteFonctionnelle": code(e.get("demande_uf"))}
    return {
        "identifiant": {"emetteur": e["intervention_id"]},
        "debut": date_heure(e, "intervention_date_debut", "intervention_heure_debut"),
        "fin": date_heure(e, "intervention_date_fin", "intervention_heure_fin"),
        "uniteFonctionnelle": code(e.get("intervention_uf")),
        "demande": demande,
    }


def root_attrs(entete: dict, evt: dict, version: str | None) -> dict:
    """Attributs de la racine. Version : paramètre, sinon colonne ``version``, sinon 2.4."""
    return {"version": version or ent(evt, entete, "version", "2.4"),
            "acquittementAttendu": ent(evt, entete, "acquittement_attendu")}


# ---- atomicité ---------------------------------------------------------------
def decouper(e: dict, objets: list[dict], extra=None) -> Iterator[tuple[dict, dict]]:
    """Un message par objet atomique (acte, diagnostic) : la ligne d'événement est répétée,
    avec ``evt_id = {evt_id}_{rang}``, ``evt_origine`` (l'evt_id de départ) et ``rang``.
    Une colonne ``identifiant_message`` de l'objet prime sur celle de l'événement."""
    if not objets:
        import warnings
        warnings.warn(f"Événement {e['evt_id']} : aucun objet à écrire en mode atomique, ignoré",
                      stacklevel=3)
    for rang, o in enumerate(objets, start=1):
        e_o = {**e, "evt_origine": e["evt_id"], "rang": rang, "evt_id": f"{e['evt_id']}_{rang}",
               **(extra(o) if extra else {})}
        if o.get("identifiant_message") is not None:
            e_o["identifiant_message"] = o["identifiant_message"]
        yield e_o, o


# ---- écriture ---------------------------------------------------------------
def write_trees(trees: Iterable[tuple[dict, dict]], *, out_dir: str | Path,
                filename: str | Callable[[dict], str], xmlns: str | None = HPRIM_NS,
                encoding: str = "UTF-8", validate_xsd: str | bool = "error",
                entete: dict | None = None, identifiant_egal_nom_fichier: bool = True,
                fichier_ok: bool = False) -> list[Path]:
    """Écrit un fichier par (ligne evenement, arbre).

    Avec ``identifiant_egal_nom_fichier`` (défaut), l'identifiantMessage de chaque message
    est le nom de son fichier sans extension ; une colonne ``identifiant_message``
    contradictoire lève une erreur.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths, vus = [], {}
    for e, tree in trees:
        name = filename(e) if callable(filename) else filename.format(**e)
        if name in vus:
            raise HprimWriteError(
                f"Nom de fichier {name!r} produit par deux événements ({vus[name]} et "
                f"{e['evt_id']}) : le gabarit filename doit donner un nom unique par message.")
        vus[name] = e["evt_id"]
        head = next(iter(tree.values()))["enteteMessage"]
        if identifiant_egal_nom_fichier:
            stem = Path(name).stem
            explicite = ent(e, entete, "identifiant_message")
            if explicite is not None and str(explicite) != stem:
                raise HprimWriteError(
                    f"Événement {e['evt_id']} : identifiant_message {str(explicite)!r} différent "
                    f"du nom de fichier {name!r}. L'identifiant du message doit être le nom du "
                    f"fichier sans extension : retirer identifiant_message, ou s'en servir pour "
                    f"nommer le fichier (filename=\"{{identifiant_message}}.xml\").")
            head["identifiantMessage"] = check_identifiant_message(stem, e["evt_id"], name)
        else:
            head["identifiantMessage"] = check_identifiant_message(
                head["identifiantMessage"], e["evt_id"])
        try:
            data = to_xml(tree, xmlns=xmlns, encoding=encoding, validate_xsd=validate_xsd)
        except HprimWriteError as err:
            raise HprimWriteError(f"Événement {e['evt_id']} : {err}") from err
        path = out_dir / name
        deposer(path, data, fichier_ok=fichier_ok)
        paths.append(path)
    return paths


def chemin_ok(path: Path, extension_ok: str = ".ok") -> Path:
    """Fichier marqueur associé à un XML : même nom, extension ``.ok``."""
    return path.with_suffix(extension_ok)


def deposer(path: Path, data: bytes, *, fichier_ok: bool = False) -> None:
    """Dépose un fichier de façon atomique, puis son ``.ok`` si demandé.

    1. un ``.ok`` existant est d'abord supprimé : pendant le remplacement, le fichier
       n'est jamais signalé comme complet ;
    2. le contenu est écrit sous un nom temporaire caché (``.nom.xml.tmp``), puis renommé :
       le fichier n'apparaît sous son nom définitif qu'une fois complet ;
    3. le ``.ok`` vide est créé en dernier.
    """
    ok = chemin_ok(path)
    if fichier_ok and ok.exists():
        ok.unlink()
    tmp = path.with_name(f".{path.name}.tmp")
    try:
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()
    if fichier_ok:
        ok.write_bytes(b"")


def iter_rows(df: pl.DataFrame) -> Iterator[dict]:
    yield from df.to_dicts()


# =============================================================================
# Lecture
# =============================================================================
def as_list(v: Any) -> list:
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def pick(node: Any, path: str) -> Any:
    """Valeur au chemin ``a/b/@c`` (premier élément si répété ; ``#text`` si besoin)."""
    cur = node
    for p in (x for x in path.split("/") if x):
        if isinstance(cur, list):
            cur = cur[0] if cur else None
        if not isinstance(cur, dict):
            return None
        cur = cur.get(p.lstrip("@"))
    if isinstance(cur, list):
        cur = cur[0] if cur else None
    if isinstance(cur, dict):
        cur = cur.get("#text")
    return cur


def pick_list(node: Any, path: str) -> list:
    """Liste des nœuds au chemin ``a/b`` (le dernier segment peut être répété)."""
    *head, last = [x for x in path.split("/") if x]
    cur = node
    for p in head:
        if isinstance(cur, list):
            cur = cur[0] if cur else None
        if not isinstance(cur, dict):
            return []
        cur = cur.get(p)
    if isinstance(cur, list):
        cur = cur[0] if cur else None
    return as_list(cur.get(last)) if isinstance(cur, dict) else []


def extra_cols(node: Any, paths: list[str] | None) -> dict:
    return {p: pick(node, p) for p in (paths or [])}


def modificateurs_str(node: Any) -> str | None:
    mods = [m.get("#text") if isinstance(m, dict) else m for m in pick_list(node, "modificateurs/modificateur")]
    mods = [str(m) for m in mods if m is not None]
    return "".join(mods) or None


def entete_cols(root: dict) -> dict:
    e = root.get("enteteMessage") or {}
    return {
        "version": root.get("version"),
        "acquittement_attendu": root.get("acquittementAttendu"),
        "mode_traitement": e.get("modeTraitement"),
        "identifiant_message": e.get("identifiantMessage"),
        "date_heure_production": e.get("dateHeureProduction"),
        "emetteur": pick(e, "emetteur/agents/agent/code"),
        "emetteur_categorie": pick(e, "emetteur/agents/agent/@categorie"),
        "destinataire": pick(e, "destinataire/agents/agent/code"),
        "destinataire_categorie": pick(e, "destinataire/agents/agent/@categorie"),
        "commentaire": e.get("commentaireMessage"),
    }


def patient_cols(ev: dict) -> dict:
    p = ev.get("patient")
    return {
        "ipp": pick(p, "identifiant/emetteur/valeur"),
        "ipp_recepteur": pick(p, "identifiant/recepteur/valeur"),
        "sexe": pick(p, "personnePhysique/@sexe"),
        "nom_usuel": pick(p, "personnePhysique/nomUsuel"),
        "nom_naissance": pick(p, "personnePhysique/nomNaissance"),
        "prenom": pick(p, "personnePhysique/prenoms/prenom"),
        "date_naissance": pick(p, "personnePhysique/dateNaissance/date"),
    }


def venue_cols(ev: dict) -> dict:
    v = ev.get("venue")
    return {
        "nda": pick(v, "identifiant/emetteur/valeur"),
        "nda_recepteur": pick(v, "identifiant/recepteur/valeur"),
        "venue_date_entree": pick(v, "entree/dateHeureOptionnelle/date"),
        "venue_heure_entree": pick(v, "entree/dateHeureOptionnelle/heure"),
        "venue_mode_entree": pick(v, "entree/modeEntree/code"),
        "venue_uf_responsable": pick(v, "entree/uniteFonctionnelleResponsable/code"),
        "venue_date_sortie": pick(v, "sortie/dateHeureOptionnelle/date"),
        "venue_heure_sortie": pick(v, "sortie/dateHeureOptionnelle/heure"),
    }


def intervention_cols(ev: dict) -> dict:
    i = ev.get("intervention")
    return {
        "intervention_id": pick(i, "identifiant/emetteur"),
        "intervention_date_debut": pick(i, "debut/date"),
        "intervention_heure_debut": pick(i, "debut/heure"),
        "intervention_date_fin": pick(i, "fin/date"),
        "intervention_heure_fin": pick(i, "fin/heure"),
        "intervention_uf": pick(i, "uniteFonctionnelle/code"),
        "demande_date": pick(i, "demande/datePrescription/date"),
        "demande_heure": pick(i, "demande/datePrescription/heure"),
        "demande_uf": pick(i, "demande/uniteFonctionnelle/code"),
    }


def iter_sources_completes(sources, exiger_ok: bool = False) -> Iterator[tuple[str, Any]]:
    """Comme ``iter_sources`` ; avec ``exiger_ok``, ignore les fichiers sans ``.ok``
    (dépôt pas encore terminé) et signale leur nombre par un avertissement."""
    ignores = []
    for ident, src in iter_sources(sources):
        if exiger_ok and isinstance(src, Path) and not chemin_ok(src).exists():
            ignores.append(src.name)
            continue
        yield ident, src
    if ignores:
        import warnings
        warnings.warn(f"{len(ignores)} fichier(s) sans .ok ignoré(s) (dépôt incomplet) : "
                      f"{', '.join(ignores[:5])}{'…' if len(ignores) > 5 else ''}", stacklevel=3)


def iter_sources(sources) -> Iterator[tuple[str, Any]]:
    """(identifiant, source) pour : chemin de fichier, dossier (*.xml), motif glob,
    bytes, ou liste de tout cela. L'identifiant est le nom du fichier sans extension."""
    if isinstance(sources, (bytes, bytearray)):
        yield "message", bytes(sources)
        return
    if isinstance(sources, (str, Path)):
        p = Path(sources)
        if p.is_dir():
            for f in sorted(p.glob("*.xml")):
                yield f.stem, f
        elif any(c in str(sources) for c in "*?["):
            for f in sorted(Path().glob(str(sources))) if not p.is_absolute() else \
                    sorted(Path(p.anchor).glob(str(p.relative_to(p.anchor)))):
                yield f.stem, f
        else:
            yield p.stem, p
        return
    for s in sources:
        yield from iter_sources(s)


def frame(rows: list[dict], columns: list[str], backend: str = "polars"):
    """DataFrame à partir de lignes ; colonnes dans l'ordre donné (+ extras à la suite)."""
    cols = list(dict.fromkeys(columns + [k for r in rows for k in r]))
    if rows:
        df = pl.DataFrame([{c: r.get(c) for c in cols} for r in rows], infer_schema_length=None)
    else:
        df = pl.DataFrame({c: [] for c in cols})
    return df.to_pandas() if backend == "pandas" else df
