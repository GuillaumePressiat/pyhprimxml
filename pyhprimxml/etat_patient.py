"""evenementsServeurEtatsPatient (diagnostics, IGS2…) — un fichier par événement.

``evenements`` (1 ligne = 1 fichier ; colonnes-chemins relatives à la racine du message)
    obligatoires : evt_id, ipp, sexe, date_naissance
    facultatives : patient, venue et intervention comme pour le serveur d'actes,
        date_observation, heure_observation (élément dateObservation),
        recueil_id, recueil_date, recueil_heure, recueil_uf (élément recueil : date et UF
        où les états ont été observés), identifiant_message, date_heure_production,
        commentaire

    Le XSD impose un repère, au choix : intervention (colonnes intervention_*),
    dateObservation (date_observation) ou recueil (colonnes recueil_*). Le recueil est le
    plus précis : il porte l'UF d'observation, qui permet au récepteur de retrouver le RUM.
    Le contenu est un choix exclusif : Diagnostics (table ``diagnostics``), ou igs2,
    dependances… (colonnes-chemins, par exemple ``igs2/@age``).

``diagnostics`` (1 ligne = 1 diagnostic ; colonnes-chemins relatives à ``diagnostic``)
    obligatoires : evt_id, type, code
    facultatives : date_action, action ("creation")
    ``type`` suit l'énumération du XSD : dp, dr, da, ds, dd, fpc, mm, ae
    (mis en minuscules ; DP et dp sont équivalents).
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterator

from pyhprimxml.common import (
    code,
    iter_sources_completes,
    pick,
    date_heure,
    Sources, Table,
    pick_list, extra_cols, entete_cols, patient_cols, venue_cols, intervention_cols, iter_sources, frame, ENTETE_KEYS,
    apply_paths, as_polars, entete_tree, g, intervention_tree, patient_tree,
    root_attrs, rows_by, to_datetime, venue_tree, write_trees,
)
from pyhprimxml.io.parse import parse_xml
from pyhprimxml.xsd import HPRIM_NS


def _recueil(e: dict) -> dict | None:
    """recueil : recueil_id, recueil_date, recueil_heure, recueil_uf."""
    if e.get("recueil_date") is None and e.get("recueil_id") is None:
        return None
    return {
        "identifiant": {"emetteur": e.get("recueil_id")},
        "date": e.get("recueil_date"),
        "heure": e.get("recueil_heure"),
        "uniteFonctionnelle": code(e.get("recueil_uf")),
    }


def _diagnostic(d: dict) -> dict:
    node = {
        "action": g(d, "action", "creation"),
        "type": str(d["type"]).lower(),
        "dateAction": to_datetime(d.get("date_action")),
        "codeCim10": str(d["code"]).replace(".", "").strip(),
    }
    return apply_paths(node, d)


def evenement_etat_patient_tree(evt: dict, diags: list[dict], entete: dict | None = None,
                                version: str | None = None) -> dict:
    contenu = {
        **root_attrs(entete, evt, version),
        "enteteMessage": entete_tree(entete, evt),
        "patient": patient_tree(evt),
        "venue": venue_tree(evt),
        "intervention": intervention_tree(evt),
        "dateObservation": date_heure(evt, "date_observation", "heure_observation"),
        "recueil": _recueil(evt),
        "Diagnostics": {"diagnostic": [_diagnostic(d) for d in diags]} if diags else None,
        # obligatoire (même vide) en 2.4, facultatif avant : supprimé s'il est vide et facultatif
        "divers": {},
    }
    return {"evenementsServeurEtatsPatient": apply_paths(contenu, evt)}


def iter_evenements_etat_patient(evenements: Table, diagnostics: Table, *, entete: dict | None = None, version: str | None = None,
                                 colmap: dict | None = None) -> Iterator[tuple[dict, dict]]:
    evt = as_polars(evenements, "evenements", ["evt_id", "ipp", "sexe", "date_naissance"], colmap)
    dia = as_polars(diagnostics, "diagnostics", ["evt_id", "type", "code"], colmap)
    dia_by = rows_by(dia, "evt_id")
    for e in evt.to_dicts():
        yield e, evenement_etat_patient_tree(e, dia_by.get(e["evt_id"], []), entete, version)


def write_evenements_etat_patient(evenements: Table, diagnostics: Table, *, entete: dict | None = None, out_dir: str | Path,
                                  filename: str | Callable[[dict], str] = "{evt_id}.xml",
                                  version: str | None = None, xmlns: str | None = HPRIM_NS,
                                  encoding: str = "UTF-8", validate_xsd: str | bool = "error",
                                  colmap: dict | None = None,
                                  identifiant_egal_nom_fichier: bool = True,
                          fichier_ok: bool = False) -> list[Path]:
    """Écrit des fichiers evenementsServeurEtatsPatient (diagnostics), un par événement.

    Args:
        evenements: une ligne par événement : patient, venue, intervention. Les
            colonnes-chemins sont relatives à la racine du message.
        diagnostics: une ligne par diagnostic (``type`` : dp, dr, da, ds, dd, fpc, mm, ae).
        entete: voir ``write_evenements_pmsi``.
        out_dir: dossier de sortie.
        filename: gabarit ou fonction.
        version: version du schéma.
        xmlns: voir ``write_evenements_pmsi``.
        encoding: encodage des fichiers.
        validate_xsd: ``"error"`` (défaut), ``"warn"`` ou ``False``.
        colmap: renommage de colonnes.
        identifiant_egal_nom_fichier: si vrai (défaut), l'identifiantMessage de chaque
            message est exactement le nom de son fichier sans extension (``evt_id``, ou
            ``{evt_id}_{rum_id}`` avec ``par_rum``, ou ce que donne ``filename``). Une colonne
            ``identifiant_message`` différente lève une erreur. ``False`` : identifiant et nom
            de fichier indépendants (utile pour réécrire des fichiers d'autres producteurs).
        fichier_ok: dépose un fichier ``.ok`` vide, de même nom, une fois chaque ``.xml``
            écrit intégralement (marqueur de dépôt complet pour le destinataire). Le
            ``.xml`` est toujours écrit de façon atomique (nom temporaire puis renommage).

    Returns:
        La liste des fichiers écrits.

    Examples:
        Script ``examples/exemple_etat_patient.py`` :

        ```python
        # Régénère data/xml_tests/etat_patient/00001.xml : diagnostics DP et DR.
        from datetime import date, datetime, time

        import polars as pl

        import pyhprimxml as hx

        entete = {
            "version": "2.00",                   # version HPRIM XML des messages
            "emetteur": "TEST",
            "destinataire": None,
            "acquittement_attendu": "non",
            "commentaire": "HPRIM-TEST",
            "date_heure_production": datetime(2024, 1, 1, 1, 1, 1),
        }

        # Une ligne par événement : patient, venue, intervention
        # (ici, les colonnes-chemins sont relatives à la racine du message)
        evenements = pl.DataFrame({
            "evt_id": ["00001_esep"],
            "ipp": ["123456789"], "ipp_recepteur": ["123456789"],
            "sexe": ["M"], "nom_usuel": ["SANDWICK"], "prenom": ["JOHN"],
            "date_naissance": [date(1970, 1, 1)],
            "nda": ["987654321"], "nda_recepteur": ["987654321"],
            "venue_date_entree": [date(2024, 1, 1)], "venue_heure_entree": [time(8, 0)],
            "venue_uf_responsable": ["4321"],
            "intervention_id": ["000000000001"], "intervention_uf": ["4321"],
            "patient/@confidentiel": ["non"], "venue/@prive": ["non"],
            "patient/identifiant/emetteur/@etat": ["permanent"],
            "patient/identifiant/emetteur/@portee": ["local"],
            "patient/identifiant/emetteur/@referent": ["non"],
            "patient/identifiant/recepteur/@etat": ["permanent"],
            "patient/identifiant/recepteur/@portee": ["local"],
            "patient/identifiant/recepteur/@referent": ["non"],
        })

        # Une ligne par diagnostic ; type dans dp, dr, da, ds, dd, fpc, mm, ae
        diagnostics = pl.DataFrame({
            "evt_id": ["00001_esep", "00001_esep"],
            "type": ["dp", "dr"],
            "code": ["Z511", "C10"],
            "date_action": [datetime(2024, 1, 1, 8, 10)] * 2,
        })

        fichiers = hx.write_evenements_etat_patient(
            evenements, diagnostics,
            entete=entete,
            out_dir="sortie/etat_patient",   # -> sortie/etat_patient/00001_esep.xml
            validate_xsd="warn",
        )
        ```
    """
    trees = iter_evenements_etat_patient(evenements, diagnostics, entete=entete, version=version,
                                         colmap=colmap)
    return write_trees(trees, out_dir=out_dir, filename=filename, xmlns=xmlns,
                       encoding=encoding, validate_xsd=validate_xsd, entete=entete,
                       identifiant_egal_nom_fichier=identifiant_egal_nom_fichier,
                       fichier_ok=fichier_ok)


# =============================================================================
# Lecture : fichiers evenementsServeurEtatsPatient -> tables
# =============================================================================
EVT_COLS = (["evt_id"] + ENTETE_KEYS
            + ["ipp", "ipp_recepteur", "sexe", "nom_usuel", "nom_naissance", "prenom", "date_naissance",
               "nda", "nda_recepteur", "venue_date_entree", "venue_heure_entree", "venue_mode_entree",
               "venue_uf_responsable", "venue_date_sortie", "venue_heure_sortie",
               "intervention_id", "intervention_date_debut", "intervention_heure_debut",
               "intervention_date_fin", "intervention_heure_fin", "intervention_uf",
               "demande_date", "demande_heure", "demande_uf",
               "date_observation", "heure_observation",
               "recueil_id", "recueil_date", "recueil_heure", "recueil_uf"])
DIAG_COLS = ["evt_id", "type", "code", "date_action", "action"]


def read_evenements_etat_patient(sources: Sources, *, extra: dict[str, list[str]] | None = None,
                                 version: str | None = None, backend: str = "polars",
                         exiger_ok: bool = False) -> dict[str, Table]:
    """Lit des fichiers evenementsServeurEtatsPatient vers des tables.

    Args:
        sources: fichier, dossier, motif glob, bytes ou liste.
        extra: colonnes-chemins supplémentaires, par table (``evenements`` : relatives
            à la racine du message).
        version: forcer une version de schéma.
        backend: ``"polars"`` ou ``"pandas"``.
        exiger_ok: ne lit que les ``.xml`` accompagnés de leur ``.ok`` (dépôt terminé) ;
            les autres sont ignorés, avec un avertissement.

    Returns:
        ``{"evenements", "diagnostics"}``.
    """
    extra = extra or {}
    evts, diags = [], []
    for evt_id, src in iter_sources_completes(sources, exiger_ok):
        root = parse_xml(src, version=version)["evenementsServeurEtatsPatient"]
        evts.append({"evt_id": evt_id, **entete_cols(root), **patient_cols(root),
                     **venue_cols(root), **intervention_cols(root),
                     "date_observation": pick(root, "dateObservation/date"),
                     "heure_observation": pick(root, "dateObservation/heure"),
                     "recueil_id": pick(root, "recueil/identifiant/emetteur"),
                     "recueil_date": pick(root, "recueil/date"),
                     "recueil_heure": pick(root, "recueil/heure"),
                     "recueil_uf": pick(root, "recueil/uniteFonctionnelle/code"),
                     **extra_cols(root, extra.get("evenements"))})
        for d in pick_list(root, "Diagnostics/diagnostic"):
            diags.append({"evt_id": evt_id, "type": d.get("type"), "code": d.get("codeCim10"),
                          "date_action": d.get("dateAction"), "action": d.get("action"),
                          **extra_cols(d, extra.get("diagnostics"))})
    return {"evenements": frame(evts, EVT_COLS, backend), "diagnostics": frame(diags, DIAG_COLS, backend)}
