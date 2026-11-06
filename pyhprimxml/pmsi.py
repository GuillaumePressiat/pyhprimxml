"""evenementsPMSI / RSS MCO depuis des tables — un fichier par événement.

``evenements`` (1 ligne = 1 fichier ; colonnes-chemins relatives à ``evenementPMSI``)
    obligatoires : evt_id, ipp, sexe, date_naissance, nda, venue_date_entree
    facultatives : ipp_recepteur, nom_usuel, nom_naissance, prenom, nda_recepteur,
        venue_heure_entree, venue_mode_entree, venue_uf_responsable, venue_date_sortie,
        venue_heure_sortie, rss_emetteur, rss_recepteur, rss_version, numero_finess,
        identifiant_message, date_heure_production, commentaire

``rum`` (1 ligne = 1 RUM ; colonnes-chemins relatives à ``rum``)
    obligatoires : evt_id, rum_id, um, um_date_entree, um_mode_entree
    facultatives : rum_emetteur (défaut rum_id), rum_recepteur, action (creation),
        date_action (défaut um_date_entree), um_heure_entree, um_provenance,
        um_date_sortie, um_heure_sortie, um_mode_sortie, um_destination, igs2, nb_seances

``diagnostics`` (format long ; colonnes-chemins relatives au diagnostic)
    evt_id, rum_id, type ∈ {DP, DR, DAS, DAD}, code

    Alternative : colonnes ``dp``, ``dr``, ``das``, ``dad`` dans ``rum``. ``das`` et ``dad``
    acceptent une liste (type List de polars) ou une chaîne séparée par des virgules
    (``"E11.9, I10"``). Les deux formes peuvent se combiner, sans doublon de DP ou de DR.

``actes`` (1 ligne = 1 acte CCAM ; colonnes-chemins relatives à ``acte``)
    obligatoires : evt_id, rum_id, code, phase, activite
    facultatives : quantite (1), extension_pmsi, date_realisation, extension_documentaire,
        modificateurs (ex. "7J"), association_non_prevue, remboursement_exceptionnel, externe

``rum_id`` n'est qu'une clé de jointure : l'identifiant XML du RUM est ``rum_emetteur``
(deux RUM d'un même RSS peuvent partager le même émetteur).
"""
from __future__ import annotations

import warnings
from pathlib import Path
from typing import Callable, Iterator

from pyhprimxml.common import (
    iter_sources_completes,
    Sources, Table,
    as_list, pick, pick_list, extra_cols, modificateurs_str, entete_cols, patient_cols, venue_cols, iter_sources, frame, ENTETE_KEYS,
    apply_paths, as_polars, entete_tree, g, patient_tree, root_attrs, rows_by,
    to_datetime, venue_tree, write_trees,
)
from pyhprimxml.io.output import HprimWriteError
from pyhprimxml.io.parse import parse_xml
from pyhprimxml.xsd import HPRIM_NS

_DIAG_SLOTS = {"DP": "diagnosticPrincipal", "DR": "diagnosticRelie"}
#: Colonnes de diagnostics acceptées dans la table ``rum`` (alternative au format long)
DIAG_COLONNES = {"dp": "DP", "dr": "DR", "das": "DAS", "dad": "DAD"}


def _codes(v) -> list:
    """Codes d'une cellule : liste (List polars), chaîne séparée par des virgules, ou code seul."""
    if v is None:
        return []
    if isinstance(v, str):
        return [c.strip() for c in v.split(",") if c.strip()]
    if hasattr(v, "tolist"):  # tableau numpy venu de pandas
        v = v.tolist()
    if isinstance(v, (list, tuple)):
        return [c for c in v if c is not None and str(c).strip()]
    return [v]


def diagnostics_depuis_rum(rum: "pl.DataFrame") -> list[dict]:
    """Diagnostics au format long à partir des colonnes dp, dr, das, dad de ``rum``."""
    cols = [c for c in DIAG_COLONNES if c in rum.columns]
    lignes = []
    for r in rum.select(["evt_id", "rum_id", *cols]).to_dicts():
        for c in cols:
            codes = _codes(r[c])
            if c in ("dp", "dr") and len(codes) > 1:
                raise HprimWriteError(f"RUM {r['rum_id']} : un seul {DIAG_COLONNES[c]} attendu, "
                                      f"{len(codes)} reçus ({codes})")
            lignes += [{"evt_id": r["evt_id"], "rum_id": r["rum_id"], "type": DIAG_COLONNES[c],
                        "code": code} for code in codes]
    return lignes


def _diagnostics(diags: list[dict]) -> dict:
    out: dict = {}
    das, dad = [], []
    for d in diags:
        t = str(d["type"]).upper()
        node = apply_paths({"codeCim10": str(d["code"]).replace(".", "").strip()}, d)
        if t in _DIAG_SLOTS:
            if _DIAG_SLOTS[t] in out:
                raise HprimWriteError(f"RUM {d.get('rum_id')} : plusieurs {t}")
            out[_DIAG_SLOTS[t]] = node
        elif t == "DAS":
            das.append(node)
        elif t == "DAD":
            dad.append(node)
        else:
            raise HprimWriteError(f"Type de diagnostic inconnu : {t!r} (DP, DR, DAS, DAD)")
    if das:
        out["diagnosticsSignificatifs"] = {"diagnosticSignificatif": das}
    if dad:
        out["diagnosticsDocumentaires"] = {"diagnosticDocumentaire": dad}
    return out


def _acte(a: dict) -> dict:
    modifs = a.get("modificateurs")
    node = {
        "externe": a.get("externe"),
        "CCAM": {
            "remboursementExceptionnel": a.get("remboursement_exceptionnel"),
            "codeActe": a["code"],
            "codeActeExtensionPMSI": a.get("extension_pmsi"),
            "codePhase": a["phase"],
            "codeActivite": a["activite"],
            "quantite": g(a, "quantite", 1),
            "dateRealisation": to_datetime(a.get("date_realisation")),
            "codeExtensionDocumentaire": a.get("extension_documentaire"),
            "modificateurs": {"modificateur": list(str(modifs))} if modifs else None,
            "codeAssociationNonPrevue": a.get("association_non_prevue"),
        },
    }
    return apply_paths(node, a)


def _rum(r: dict, diags: list[dict], actes: list[dict]) -> dict:
    sortie = None
    if r.get("um_date_sortie") is not None:
        sortie = {"mode": r.get("um_mode_sortie"), "complementMode": r.get("um_destination"),
                  "date": r["um_date_sortie"], "heure": r.get("um_heure_sortie")}
    node = {
        "action": g(r, "action", "creation"),
        "dateAction": to_datetime(g(r, "date_action", r["um_date_entree"])),
        "identifiant": {"emetteur": g(r, "rum_emetteur", r["rum_id"]),
                        "recepteur": r.get("rum_recepteur")},
        "uniteMedicale": {
            "code": r["um"],
            "entree": {"mode": r["um_mode_entree"], "complementMode": r.get("um_provenance"),
                       "date": r["um_date_entree"], "heure": r.get("um_heure_entree")},
            "sortie": sortie,
        },
        "diagnostics": _diagnostics(diags),  # obligatoire dans le XSD, même vide
        "actes": {"acte": [_acte(a) for a in actes]} if actes else None,
        "igs2": r.get("igs2"),
        "seance": r.get("nb_seances"),
    }
    return apply_paths(node, r)


def evenement_pmsi_tree(evt: dict, rums: list[dict], diags: dict, actes: dict,
                        entete: dict | None = None, version: str | None = None) -> dict:
    """Arbre (format xmltodict) d'un message evenementsPMSI à un seul événement RSS."""
    evenement = {
        "patient": patient_tree(evt),
        "venue": venue_tree(evt),
        "rss": {
            "version": evt.get("rss_version"),
            "identifiantRSS": {"emetteur": evt.get("rss_emetteur"),
                               "recepteur": evt.get("rss_recepteur")},
            "rum": [_rum(r, diags.get(r["rum_id"], []), actes.get(r["rum_id"], [])) for r in rums],
        },
        "numeroFiness": evt.get("numero_finess"),
    }
    return {"evenementsPMSI": {
        **root_attrs(entete, evt, version),
        "enteteMessage": entete_tree(entete, evt),
        "evenementPMSI": apply_paths(evenement, evt),
    }}


def iter_evenements_pmsi(evenements: Table, rum: Table, diagnostics: Table | None = None, actes: Table | None = None, *, entete: dict | None = None,
                         version: str | None = None, colmap: dict | None = None,
                         par_rum: bool = False) -> Iterator[tuple[dict, dict]]:
    """Itère sur (ligne evenement, arbre xmltodict) — un arbre par événement.

    par_rum : un message par RUM au lieu d'un message par séjour. L'événement
        ``evt_id`` devient ``{evt_id}_{rum_id}`` (donc le nom de fichier par défaut aussi) ;
        patient, venue et identifiantRSS sont répétés dans chaque message.
    """
    evt = as_polars(evenements, "evenements",
                    ["evt_id", "ipp", "nda", "sexe", "date_naissance", "venue_date_entree"], colmap)
    rum = as_polars(rum, "rum", ["evt_id", "rum_id", "um", "um_date_entree", "um_mode_entree"], colmap)
    dia = as_polars(diagnostics, "diagnostics", ["evt_id", "rum_id", "type", "code"], colmap)
    act = as_polars(actes, "actes", ["evt_id", "rum_id", "code", "phase", "activite"], colmap)

    rum_by, dia_by, act_by = rows_by(rum, "evt_id"), rows_by(dia, "evt_id"), rows_by(act, "evt_id")
    # diagnostics fournis en colonnes de rum (dp, dr, das, dad) : ajoutés au format long
    for d in diagnostics_depuis_rum(rum):
        dia_by.setdefault(d["evt_id"], []).append(d)
    for e in evt.to_dicts():
        k = e["evt_id"]
        if k not in rum_by:
            raise HprimWriteError(f"Événement {k} : aucun RUM")
        diags, acts = {}, {}
        for d in dia_by.get(k, []):
            diags.setdefault(d["rum_id"], []).append(d)
        for a in act_by.get(k, []):
            acts.setdefault(a["rum_id"], []).append(a)
        if not par_rum:
            yield e, evenement_pmsi_tree(e, rum_by[k], diags, acts, entete, version)
            continue
        for r in rum_by[k]:
            e_rum = {**e, "rss_id": k, "rum_id": r["rum_id"], "evt_id": f"{k}_{r['rum_id']}"}
            if r.get("identifiant_message") is not None:
                e_rum["identifiant_message"] = r["identifiant_message"]
            yield e_rum, evenement_pmsi_tree(e_rum, [r], diags, acts, entete, version)


def write_evenements_pmsi(evenements: Table, rum: Table, diagnostics: Table | None = None, actes: Table | None = None, *, entete: dict | None = None,
                          out_dir: str | Path, filename: str | Callable[[dict], str] = "{evt_id}.xml",
                          version: str | None = None, xmlns: str | None = HPRIM_NS,
                          encoding: str = "UTF-8", validate_xsd: str | bool = "error",
                          colmap: dict | None = None, par_rum: bool = False,
                          identifiant_egal_nom_fichier: bool = True,
                          fichier_ok: bool = False) -> list[Path]:
    """Écrit des fichiers evenementsPMSI (RSS MCO) depuis des tables.

    Les tables sont décrites en tête du module. Toute colonne dont le nom contient ``/``
    ou commence par ``@`` est une colonne-chemin.

    Args:
        evenements: une ligne par séjour (polars ou pandas).
        rum: une ligne par RUM.
        diagnostics: format long, ``type`` dans DP, DR, DAS, DAD.
        actes: une ligne par acte CCAM.
        entete: ``emetteur``, ``destinataire`` et en option ``emetteur_categorie``,
            ``destinataire_categorie``, ``mode_traitement``, ``acquittement_attendu``,
            ``commentaire``, ``date_heure_production``. Chaque clé peut aussi être une
            colonne de ``evenements`` (prioritaire).
        out_dir: dossier de sortie (créé si besoin).
        filename: gabarit formaté avec la ligne evenement, ou fonction ligne -> nom.
        version: version du schéma ; sinon colonne ``version``, sinon 2.4.
        xmlns: ``HPRIM_NS`` (défaut), ``None`` (pas de namespace) ou ``""`` (``xmlns=""``).
        encoding: encodage des fichiers.
        validate_xsd: ``"error"`` (défaut), ``"warn"`` ou ``False``.
        colmap: renommage de colonnes ``{ancien: nouveau}``.
        par_rum: un fichier par RUM au lieu d'un par séjour. ``evt_id`` vaut alors
            ``{evt_id}_{rum_id}`` ; le gabarit dispose aussi de ``{rss_id}`` et
            ``{rum_id}``. Une colonne ``identifiant_message`` dans ``rum`` fixe
            l'identifiant de chaque message (12 caractères max).
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

    Raises:
        HprimWriteError: colonne obligatoire manquante, identifiantMessage invalide,
            ou message non conforme au XSD (avec ``validate_xsd="error"``).

    Examples:
        Script ``examples/exemple_pmsi.py`` :

        ```python
        # Régénère data/xml_tests/pmsi/00001.xml : un séjour (RSS) à deux RUM.
        from datetime import date, datetime, time

        import polars as pl

        import pyhprimxml as hx

        # En-tête du message (chaque clé peut aussi être une colonne de `evenements`)
        entete = {
            "version": "2.00",                   # version HPRIM XML des messages
            "emetteur": "TEST",
            "destinataire": None,            # agent destinataire sans code, comme le fichier d'origine
            "mode_traitement": "reel",
            "acquittement_attendu": "oui",
            "commentaire": "HPRIM-TEST",
            "date_heure_production": datetime(2024, 1, 1, 1, 1, 1),
        }

        # Une ligne par séjour, donc par fichier : patient, venue, identifiant du RSS
        evenements = pl.DataFrame({
            "evt_id": ["00001_pmsi"],    # -> fichier 00001_pmsi.xml, identifiantMessage 00001_pmsi
            "ipp": ["123456789"], "ipp_recepteur": ["123456789"],
            "sexe": ["M"], "nom_usuel": ["SANDWICK"], "nom_naissance": ["SANDWICK"], "prenom": ["JOHN"],
            "date_naissance": [date(1970, 1, 1)],
            "nda": ["987654321"], "nda_recepteur": ["987654321"],
            "venue_date_entree": [date(2024, 1, 1)], "venue_heure_entree": [time(8, 0)],
            "venue_mode_entree": ["8"], "venue_uf_responsable": ["4321"],
            "rss_emetteur": ["0"], "rss_recepteur": ["000"],
            # colonnes-chemins : attributs sans colonne dédiée
            "patient/@anonyme": ["non"], "patient/@confidentiel": ["non"], "venue/@prive": ["non"],
        })

        # Une ligne par RUM ; rum_id = rang du RUM dans le RSS (clé de jointure)
        rum = pl.DataFrame({
            "evt_id": ["00001_pmsi", "00001_pmsi"],
            "rum_id": [1, 2],
            "rum_emetteur": ["pmsi_00001", "pmsi_00001"],     # identifiant XML du RUM
            "rum_recepteur": ["98765", "98766"],
            "date_action": [datetime(2024, 1, 1, 8, 10), datetime(2024, 1, 1, 9, 0)],
            "um": ["4321", "5000"],
            "um_date_entree": [date(2024, 1, 1)] * 2,
            "um_heure_entree": [time(8, 0), time(9, 0)],
            "um_mode_entree": ["8", "8"],
            "@classant": ["non", "non"],
            "@prestationInterEtablissementA": ["non", "non"],
            "medecinResponsable/identification/code": ["01234567"] * 2,
            "medecinResponsable/personne/nomUsuel": ["HOBBES"] * 2,
            "medecinResponsable/personne/prenoms/prenom": ["MARC-JACQUES"] * 2,
        })

        # Format long : une ligne par diagnostic, type dans DP, DR, DAS, DAD
        diagnostics = pl.DataFrame({
            "evt_id": ["00001_pmsi"] * 3,
            "rum_id": [1, 1, 2],
            "type": ["DP", "DR", "DP"],
            "code": ["Z511", "C10", "Z743"],
        })

        # Une ligne par acte CCAM
        actes = pl.DataFrame({
            "evt_id": ["00001_pmsi"] * 5,
            "rum_id": [1, 1, 1, 1, 2],
            "code": ["EBLA003", "EPLF002", "NFKA006", "YYYY033", "QZRP004"],
            "phase": [0] * 5, "activite": [1] * 5, "quantite": [1] * 5,
            "date_realisation": [datetime(2024, 1, 1, 8, 10)] * 4 + [datetime(2024, 1, 1, 9, 10)],
            "externe": ["non"] * 5, "remboursement_exceptionnel": ["non"] * 5,
        })

        fichiers = hx.write_evenements_pmsi(
            evenements, rum, diagnostics, actes,
            entete=entete,
            out_dir="sortie/pmsi",           # -> sortie/pmsi/00001_pmsi.xml
            validate_xsd="warn",             # destinataire sans code : non conforme au XSD
        )
        ```
    """
    trees = iter_evenements_pmsi(evenements, rum, diagnostics, actes, entete=entete,
                                 version=version, colmap=colmap, par_rum=par_rum)
    return write_trees(trees, out_dir=out_dir, filename=filename, xmlns=xmlns,
                       encoding=encoding, validate_xsd=validate_xsd, entete=entete,
                       identifiant_egal_nom_fichier=identifiant_egal_nom_fichier,
                       fichier_ok=fichier_ok)


# =============================================================================
# Lecture : fichiers evenementsPMSI -> tables (inverse de write_evenements_pmsi)
# =============================================================================
EVT_COLS = (["evt_id"] + ENTETE_KEYS
            + ["ipp", "ipp_recepteur", "sexe", "nom_usuel", "nom_naissance", "prenom", "date_naissance",
               "nda", "nda_recepteur", "venue_date_entree", "venue_heure_entree", "venue_mode_entree",
               "venue_uf_responsable", "venue_date_sortie", "venue_heure_sortie",
               "rss_emetteur", "rss_recepteur", "rss_version", "numero_finess"])
RUM_COLS = ["evt_id", "rum_id", "rum_emetteur", "rum_recepteur", "action", "date_action", "um",
            "um_date_entree", "um_heure_entree", "um_mode_entree", "um_provenance",
            "um_date_sortie", "um_heure_sortie", "um_mode_sortie", "um_destination", "igs2", "nb_seances"]
DIAG_COLS = ["evt_id", "rum_id", "type", "code"]
ACTE_COLS = ["evt_id", "rum_id", "code", "phase", "activite", "quantite", "extension_pmsi",
             "date_realisation", "extension_documentaire", "modificateurs", "association_non_prevue",
             "remboursement_exceptionnel", "externe"]

_DIAG_READ = [("DP", "diagnostics/diagnosticPrincipal"), ("DR", "diagnostics/diagnosticRelie"),
              ("DAS", "diagnostics/diagnosticsSignificatifs/diagnosticSignificatif"),
              ("DAD", "diagnostics/diagnosticsDocumentaires/diagnosticDocumentaire")]


def read_evenements_pmsi(sources: Sources, *, extra: dict[str, list[str]] | None = None,
                         version: str | None = None, backend: str = "polars",
                         exiger_ok: bool = False,
                         format_diagnostics: str = "long") -> dict[str, Table]:
    """Lit des fichiers evenementsPMSI (RSS MCO) vers les tables de ``write_evenements_pmsi``.

    ``evt_id`` est le nom du fichier sans extension (suffixé ``_1``, ``_2``… si un fichier
    contient plusieurs événements) ; ``rum_id`` est le rang du RUM dans le RSS.

    Args:
        sources: fichier, dossier, motif glob, bytes ou liste.
        extra: colonnes-chemins supplémentaires à extraire, par table, par exemple
            ``{"evenements": ["patient/@anonyme"], "rum": ["@classant"]}``.
        version: forcer une version de schéma (sinon celle de chaque fichier).
        backend: ``"polars"`` (défaut) ou ``"pandas"``.
        format_diagnostics: ``"long"`` (défaut) : table ``diagnostics``, une ligne par code.
            ``"colonnes"`` : colonnes ``dp``, ``dr`` (texte) et ``das``, ``dad`` (listes)
            dans ``rum`` ; la table ``diagnostics`` est alors vide. Les deux formes se
            réécrivent telles quelles avec ``write_evenements_pmsi``.
        exiger_ok: ne lit que les ``.xml`` accompagnés de leur ``.ok`` (dépôt terminé) ;
            les autres sont ignorés, avec un avertissement.

    Returns:
        ``{"evenements", "rum", "diagnostics", "actes"}``.
    """
    extra = extra or {}
    evts, rums, diags, actes = [], [], [], []
    for base, src in iter_sources_completes(sources, exiger_ok):
        root = parse_xml(src, version=version)["evenementsPMSI"]
        head = entete_cols(root)
        events = as_list(root.get("evenementPMSI"))
        for i, ev in enumerate(events):
            evt_id = base if len(events) == 1 else f"{base}_{i + 1}"
            rss = ev.get("rss")
            if rss is None:
                warnings.warn(f"{evt_id} : seul le RSS (MCO) est lu pour l'instant "
                              f"({[k for k in ('rhss', 'rpsss', 'rimp', 'rssGhs') if k in ev]})")
            evts.append({
                "evt_id": evt_id, **head, **patient_cols(ev), **venue_cols(ev),
                "rss_emetteur": pick(rss, "identifiantRSS/emetteur"),
                "rss_recepteur": pick(rss, "identifiantRSS/recepteur"),
                "rss_version": pick(rss, "@version"),
                "numero_finess": ev.get("numeroFiness"),
                **extra_cols(ev, extra.get("evenements")),
            })
            for n, r in enumerate(as_list((rss or {}).get("rum")), start=1):
                rums.append({
                    "evt_id": evt_id, "rum_id": n,
                    "rum_emetteur": pick(r, "identifiant/emetteur"),
                    "rum_recepteur": pick(r, "identifiant/recepteur"),
                    "action": r.get("action"), "date_action": r.get("dateAction"),
                    "um": pick(r, "uniteMedicale/code"),
                    "um_date_entree": pick(r, "uniteMedicale/entree/date"),
                    "um_heure_entree": pick(r, "uniteMedicale/entree/heure"),
                    "um_mode_entree": pick(r, "uniteMedicale/entree/@mode"),
                    "um_provenance": pick(r, "uniteMedicale/entree/@complementMode"),
                    "um_date_sortie": pick(r, "uniteMedicale/sortie/date"),
                    "um_heure_sortie": pick(r, "uniteMedicale/sortie/heure"),
                    "um_mode_sortie": pick(r, "uniteMedicale/sortie/@mode"),
                    "um_destination": pick(r, "uniteMedicale/sortie/@complementMode"),
                    "igs2": r.get("igs2"), "nb_seances": r.get("seance"),
                    **extra_cols(r, extra.get("rum")),
                })
                for t, path in _DIAG_READ:
                    for d in pick_list(r, path):
                        diags.append({"evt_id": evt_id, "rum_id": n, "type": t,
                                      "code": pick(d, "codeCim10"),
                                      **extra_cols(d, extra.get("diagnostics"))})
                for a in pick_list(r, "actes/acte"):
                    c = a.get("CCAM")
                    if c is None:  # acte CDAM : non repris dans la table CCAM
                        continue
                    actes.append({
                        "evt_id": evt_id, "rum_id": n,
                        "code": c.get("codeActe"), "phase": c.get("codePhase"),
                        "activite": c.get("codeActivite"), "quantite": c.get("quantite"),
                        "extension_pmsi": c.get("codeActeExtensionPMSI"),
                        "date_realisation": c.get("dateRealisation"),
                        "extension_documentaire": c.get("codeExtensionDocumentaire"),
                        "modificateurs": modificateurs_str(c),
                        "association_non_prevue": c.get("codeAssociationNonPrevue"),
                        "remboursement_exceptionnel": c.get("remboursementExceptionnel"),
                        "externe": a.get("externe"),
                        **extra_cols(a, extra.get("actes")),
                    })
    out = {
        "evenements": frame(evts, EVT_COLS),
        "rum": frame(rums, RUM_COLS),
        "diagnostics": frame(diags, DIAG_COLS),
        "actes": frame(actes, ACTE_COLS),
    }
    if format_diagnostics == "colonnes":
        out["rum"], out["diagnostics"] = diagnostics_en_colonnes(out["rum"], out["diagnostics"])
    elif format_diagnostics != "long":
        raise ValueError("format_diagnostics : 'long' ou 'colonnes'")
    if backend == "pandas":
        out = {k: v.to_pandas() for k, v in out.items()}
    return out


def diagnostics_en_colonnes(rum: "pl.DataFrame", diagnostics: "pl.DataFrame"):
    """Format long -> colonnes dp, dr, das, dad de ``rum`` ; renvoie (rum, diagnostics vide)."""
    import polars as pl

    cles = ["evt_id", "rum_id"]
    def codes(t):
        return pl.col("code").filter(pl.col("type") == t)
    larges = diagnostics.group_by(cles, maintain_order=True).agg(
        codes("DP").first().alias("dp"), codes("DR").first().alias("dr"),
        codes("DAS").alias("das"), codes("DAD").alias("dad"))
    rum = rum.join(larges, on=cles, how="left").with_columns(
        pl.col("das").fill_null([]), pl.col("dad").fill_null([]))
    return rum, diagnostics.clear()
