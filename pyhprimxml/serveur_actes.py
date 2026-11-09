"""evenementsServeurActes / evenementServeurActe (actes CCAM) — un fichier par événement.

``evenements`` (1 ligne = 1 fichier ; colonnes-chemins relatives à ``evenementServeurActe``)
    obligatoires : evt_id, ipp, sexe, date_naissance
    facultatives : patient (ipp_recepteur, nom_usuel, nom_naissance, prenom),
        venue (nda, nda_recepteur, venue_date_entree, venue_heure_entree, venue_mode_entree,
        venue_uf_responsable, venue_date_sortie, venue_heure_sortie),
        intervention (intervention_id, intervention_date_debut, intervention_heure_debut,
        intervention_date_fin, intervention_heure_fin, intervention_uf,
        demande_date, demande_heure, demande_uf),
        identifiant_message, date_heure_production, commentaire

``actes`` (1 ligne = 1 acteCCAM ; colonnes-chemins relatives à ``acteCCAM``)
    obligatoires : evt_id, acte_id, code, activite, phase, date_execution, medecin
    facultatives : heure_execution, uf (UF exécutante), medecin_principal ("oui"),
        quantite, action ("creation"), facturable, valide, extension_pmsi,
        modificateurs (ex. "7J"), extension_documentaire, association_non_prevue
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterator

from pyhprimxml.common import (
    decouper,
    iter_sources_completes,
    Sources, Table,
    as_list, pick, pick_list, extra_cols, modificateurs_str, entete_cols, patient_cols, venue_cols, intervention_cols, iter_sources, frame, ENTETE_KEYS,
    apply_paths, as_polars, code, date_heure, entete_tree, g, intervention_tree,
    patient_tree, root_attrs, rows_by, venue_tree, write_trees,
)
from pyhprimxml.io.parse import parse_xml
from pyhprimxml.xsd import HPRIM_NS


def _acte_ccam(a: dict) -> dict:
    modifs = a.get("modificateurs")
    node = {
        "action": g(a, "action", "creation"),
        "facturable": a.get("facturable"),
        "valide": a.get("valide"),
        "identifiant": {"emetteur": a["acte_id"]},
        "codeActe": a["code"],
        "codeActeExtensionPMSI": a.get("extension_pmsi"),
        "codeActivite": a["activite"],
        "codePhase": a["phase"],
        "execute": date_heure(a, "date_execution", "heure_execution"),
        "executant": {
            "medecins": {"medecinExecutant": {
                "principal": g(a, "medecin_principal", "oui"),
                "medecin": {"identification": {"code": a["medecin"]}},
            }},
            "uniteFonctionnelle": code(a.get("uf")),
        },
        "modificateurs": {"modificateur": list(str(modifs))} if modifs else None,
        "codeAssociationNonPrevue": a.get("association_non_prevue"),
        "codeExtensionDocumentaire": a.get("extension_documentaire"),
        "quantite": a.get("quantite"),
    }
    return apply_paths(node, a)


def evenement_serveur_actes_tree(evt: dict, actes: list[dict], entete: dict | None = None,
                                 version: str | None = None) -> dict:
    evenement = {
        "patient": patient_tree(evt),
        "venue": venue_tree(evt),
        "intervention": intervention_tree(evt),
        "actesCCAM": {"acteCCAM": [_acte_ccam(a) for a in actes]} if actes else None,
    }
    return {"evenementsServeurActes": {
        **root_attrs(entete, evt, version),
        "enteteMessage": entete_tree(entete, evt),
        "evenementServeurActe": apply_paths(evenement, evt),
    }}


def iter_evenements_serveur_actes(evenements: Table, actes: Table, *, entete: dict | None = None, version: str | None = None,
                                  colmap: dict | None = None,
                                  par_acte: bool = False) -> Iterator[tuple[dict, dict]]:
    """Itère sur (ligne evenement, arbre) : un arbre par événement, ou par acte avec
    ``par_acte=True`` (unité atomique du serveur d'actes)."""
    evt = as_polars(evenements, "evenements", ["evt_id", "ipp", "sexe", "date_naissance"], colmap)
    act = as_polars(actes, "actes", ["evt_id", "acte_id", "code", "activite", "phase",
                                     "date_execution", "medecin"], colmap)
    act_by = rows_by(act, "evt_id")
    for e in evt.to_dicts():
        acts = act_by.get(e["evt_id"], [])
        if not par_acte:
            yield e, evenement_serveur_actes_tree(e, acts, entete, version)
            continue
        for e_a, a in decouper(e, acts, extra=lambda a: {"acte_id": a["acte_id"]}):
            yield e_a, evenement_serveur_actes_tree(e_a, [a], entete, version)


def write_evenements_serveur_actes(evenements: Table, actes: Table, *, entete: dict | None = None, out_dir: str | Path,
                                   filename: str | Callable[[dict], str] = "{evt_id}.xml",
                                   version: str | None = None, xmlns: str | None = HPRIM_NS,
                                   encoding: str = "UTF-8", validate_xsd: str | bool = "error",
                                   colmap: dict | None = None,
                                   identifiant_egal_nom_fichier: bool = True,
                          fichier_ok: bool = False,
                                   par_acte: bool = False) -> list[Path]:
    """Écrit des fichiers evenementsServeurActes (actes CCAM), un par événement.

    Unité atomique du serveur d'actes : l'**acte** (``acteCCAM``), porteur de l'attribut
    ``action`` et d'un identifiant. ``par_acte=True`` écrit un message par acte.

    Args:
        evenements: une ligne par événement : patient, venue, intervention.
        actes: une ligne par acte CCAM.
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
        par_acte: un message par acte (unité atomique) au lieu d'un par événement. Le
            contexte (patient, venue, intervention) est répété ; ``evt_id`` vaut
            ``{evt_id}_{rang}``, et le gabarit ``filename`` dispose aussi de
            ``{evt_origine}``, ``{rang}`` et ``{acte_id}``.

    Returns:
        La liste des fichiers écrits.

    Examples:
        Script ``examples/exemple_serveur_actes.py`` :

        ```python
        # Régénère data/xml_tests/actes/00001.xml : une intervention et quatre actes CCAM.
        from datetime import date, datetime, time

        import polars as pl

        import pyhprimxml as hx

        entete = {
            "version": "2.00",                   # version HPRIM XML des messages
            "emetteur": "TEST",
            "destinataire": None,
            "acquittement_attendu": "oui",
            "commentaire": "HPRIM-TEST",
            "date_heure_production": datetime(2024, 1, 1, 1, 1, 1),
        }

        # Une ligne par événement : patient, venue, intervention et demande
        evenements = pl.DataFrame({
            "evt_id": ["00001_acte"],
            "ipp": ["123456789"], "ipp_recepteur": ["123456789"],
            "sexe": ["M"], "nom_usuel": ["SANDWICK"], "prenom": ["JOHN"],
            "date_naissance": [date(1970, 1, 1)],
            "nda": ["987654321"], "nda_recepteur": ["987654321"],
            "venue_date_entree": [date(2024, 1, 1)], "venue_heure_entree": [time(8, 0)],
            "venue_uf_responsable": ["4321"],
            "venue/@prive": ["non"],
            "intervention_id": ["000000000001"],
            "intervention_date_debut": [date(2024, 1, 1)], "intervention_heure_debut": [time(8, 10)],
            "intervention_date_fin": [date(2024, 1, 1)], "intervention_heure_fin": [time(9, 0)],
            "intervention_uf": ["4321"],
            "demande_date": [date(2023, 12, 25)], "demande_heure": [time(2, 30)], "demande_uf": ["4321"],
        })

        # Une ligne par acte CCAM
        actes = pl.DataFrame({
            "evt_id": ["00001_acte"] * 4,
            "acte_id": ["121212", "121213", "121214", "121215"],
            "code": ["EBLA003", "YYYY033", "EPLF002", "NFKA006"],
            "activite": [1] * 4, "phase": [0] * 4,
            "date_execution": [date(2024, 1, 1)] * 4, "heure_execution": [time(8, 10)] * 4,
            "medecin": ["01234567"] * 4, "uf": ["4321"] * 4,
            "quantite": ["1"] * 4,           # nombre5 : chaîne de chiffres dans le XSD
            "facturable": ["oui"] * 4, "valide": ["oui"] * 4,
        })

        fichiers = hx.write_evenements_serveur_actes(
            evenements, actes,
            entete=entete,
            out_dir="sortie/actes",          # -> sortie/actes/00001_acte.xml
            validate_xsd="warn",
        )
        ```
    """
    trees = iter_evenements_serveur_actes(evenements, actes, entete=entete, version=version,
                                          colmap=colmap, par_acte=par_acte)
    return write_trees(trees, out_dir=out_dir, filename=filename, xmlns=xmlns,
                       encoding=encoding, validate_xsd=validate_xsd, entete=entete,
                       identifiant_egal_nom_fichier=identifiant_egal_nom_fichier,
                       fichier_ok=fichier_ok)


# =============================================================================
# Lecture : fichiers evenementsServeurActes -> tables
# =============================================================================
EVT_COLS = (["evt_id"] + ENTETE_KEYS
            + ["ipp", "ipp_recepteur", "sexe", "nom_usuel", "nom_naissance", "prenom", "date_naissance",
               "nda", "nda_recepteur", "venue_date_entree", "venue_heure_entree", "venue_mode_entree",
               "venue_uf_responsable", "venue_date_sortie", "venue_heure_sortie",
               "intervention_id", "intervention_date_debut", "intervention_heure_debut",
               "intervention_date_fin", "intervention_heure_fin", "intervention_uf",
               "demande_date", "demande_heure", "demande_uf"])
ACTE_COLS = ["evt_id", "acte_id", "code", "extension_pmsi", "activite", "phase", "date_execution",
             "heure_execution", "medecin", "medecin_principal", "uf", "quantite", "action",
             "facturable", "valide", "modificateurs", "association_non_prevue", "extension_documentaire"]


def read_evenements_serveur_actes(sources: Sources, *, extra: dict[str, list[str]] | None = None,
                                  version: str | None = None, backend: str = "polars",
                         exiger_ok: bool = False) -> dict[str, Table]:
    """Lit des fichiers evenementsServeurActes (actes CCAM) vers des tables.

    Args:
        sources: fichier, dossier, motif glob, bytes ou liste.
        extra: colonnes-chemins supplémentaires, par table.
        version: forcer une version de schéma.
        backend: ``"polars"`` ou ``"pandas"``.
        exiger_ok: ne lit que les ``.xml`` accompagnés de leur ``.ok`` (dépôt terminé) ;
            les autres sont ignorés, avec un avertissement.

    Returns:
        ``{"evenements", "actes"}``.
    """
    extra = extra or {}
    evts, actes = [], []
    for base, src in iter_sources_completes(sources, exiger_ok):
        root = parse_xml(src, version=version)["evenementsServeurActes"]
        head = entete_cols(root)
        events = as_list(root.get("evenementServeurActe"))
        for i, ev in enumerate(events):
            evt_id = base if len(events) == 1 else f"{base}_{i + 1}"
            evts.append({"evt_id": evt_id, **head, **patient_cols(ev), **venue_cols(ev),
                         **intervention_cols(ev), **extra_cols(ev, extra.get("evenements"))})
            for a in pick_list(ev, "actesCCAM/acteCCAM"):
                actes.append({
                    "evt_id": evt_id,
                    "acte_id": pick(a, "identifiant/emetteur"),
                    "code": a.get("codeActe"), "extension_pmsi": a.get("codeActeExtensionPMSI"),
                    "activite": a.get("codeActivite"), "phase": a.get("codePhase"),
                    "date_execution": pick(a, "execute/date"),
                    "heure_execution": pick(a, "execute/heure"),
                    "medecin": pick(a, "executant/medecins/medecinExecutant/medecin/identification/code"),
                    "medecin_principal": pick(a, "executant/medecins/medecinExecutant/@principal"),
                    "uf": pick(a, "executant/uniteFonctionnelle/code"),
                    "quantite": a.get("quantite"), "action": a.get("action"),
                    "facturable": a.get("facturable"), "valide": a.get("valide"),
                    "modificateurs": modificateurs_str(a),
                    "association_non_prevue": a.get("codeAssociationNonPrevue"),
                    "extension_documentaire": a.get("codeExtensionDocumentaire"),
                    **extra_cols(a, extra.get("actes")),
                })
    return {"evenements": frame(evts, EVT_COLS, backend), "actes": frame(actes, ACTE_COLS, backend)}
