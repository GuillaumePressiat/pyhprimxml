"""Atomicité : un message par unité atomique (RUM, acte, diagnostic)."""
import warnings
from datetime import date

import lxml.etree as ET
import polars as pl
import pytest

import pyhprimxml as hx
from pyhprimxml.etat_patient import iter_evenements_etat_patient
from pyhprimxml.serveur_actes import iter_evenements_serveur_actes

ENTETE = {"version": "2.00", "emetteur": "DIM", "destinataire": "DPI"}
PATIENT = {"ipp": ["1"], "sexe": ["F"], "date_naissance": [date(1958, 3, 12)], "nda": ["N1"],
           "venue_date_entree": [date(2024, 3, 4)]}


def actes_tables():
    evt = pl.DataFrame({"evt_id": ["A1"], **PATIENT, "intervention_id": ["INT1"]})
    act = pl.DataFrame({"evt_id": ["A1"] * 3, "acte_id": ["X1", "X2", "X3"],
                        "code": ["DEQP003", "ZBQK002", "YYYY033"], "activite": [1] * 3,
                        "phase": [0] * 3, "date_execution": [date(2024, 3, 4)] * 3,
                        "medecin": ["M1"] * 3})
    return evt, act


def diag_tables():
    evt = pl.DataFrame({"evt_id": ["D1"], **PATIENT, "recueil_id": ["R1"],
                        "recueil_date": [date(2024, 3, 4)], "recueil_uf": ["1201"]})
    dia = pl.DataFrame({"evt_id": ["D1", "D1"], "type": ["dp", "da"], "code": ["I21.0", "E11.9"]})
    return evt, dia


def identifiant(p):
    return ET.fromstring(p.read_bytes()).findtext(".//{*}identifiantMessage")


def test_par_acte_un_message_par_acte(tmp_path):
    paths = hx.write_evenements_serveur_actes(*actes_tables(), entete=ENTETE, out_dir=tmp_path,
                                              par_acte=True)
    assert [p.name for p in paths] == ["A1_1.xml", "A1_2.xml", "A1_3.xml"]
    for p in paths:
        x = p.read_text()
        assert x.count("<acteCCAM") == 1 and "<patient" in x and "<intervention" in x
        assert hx.validate(p.read_bytes()) == [] and identifiant(p) == p.stem
    # relecture : un événement par fichier, un acte chacun, contexte répété
    t = hx.read_evenements_serveur_actes(tmp_path)
    assert t["actes"]["acte_id"].to_list() == ["X1", "X2", "X3"]
    assert t["evenements"]["intervention_id"].to_list() == ["INT1"] * 3


def test_par_acte_ligne_enrichie_et_gabarit(tmp_path):
    lignes = [e for e, _ in iter_evenements_serveur_actes(*actes_tables(), entete=ENTETE, par_acte=True)]
    assert [(e["evt_id"], e["evt_origine"], e["rang"], e["acte_id"]) for e in lignes] == [
        ("A1_1", "A1", 1, "X1"), ("A1_2", "A1", 2, "X2"), ("A1_3", "A1", 3, "X3")]
    paths = hx.write_evenements_serveur_actes(*actes_tables(), entete=ENTETE, out_dir=tmp_path,
                                              par_acte=True, filename="{evt_origine}_{acte_id}.xml")
    assert [p.name for p in paths] == ["A1_X1.xml", "A1_X2.xml", "A1_X3.xml"]
    assert [identifiant(p) for p in paths] == ["A1_X1", "A1_X2", "A1_X3"]


def test_par_diagnostic_un_message_par_diagnostic(tmp_path):
    paths = hx.write_evenements_etat_patient(*diag_tables(), entete=ENTETE, out_dir=tmp_path,
                                             par_diagnostic=True)
    assert [p.name for p in paths] == ["D1_1.xml", "D1_2.xml"]
    for p in paths:
        x = p.read_text()
        assert x.count("<diagnostic ") == 1 and "<recueil>" in x
        assert hx.validate(p.read_bytes()) == []
    t = hx.read_evenements_etat_patient(tmp_path)
    assert t["diagnostics"]["code"].to_list() == ["I210", "E119"]
    assert t["evenements"]["recueil_uf"].to_list() == ["1201", "1201"]


def test_identifiant_message_porte_par_l_objet(tmp_path):
    evt, act = actes_tables()
    act = act.with_columns(pl.Series("identifiant_message", ["M1", "M2", "M3"]))
    paths = hx.write_evenements_serveur_actes(evt, act, entete=ENTETE, out_dir=tmp_path,
                                              par_acte=True, filename="{identifiant_message}.xml")
    assert [p.name for p in paths] == ["M1.xml", "M2.xml", "M3.xml"]


def test_evenement_sans_objet_en_mode_atomique(tmp_path):
    evt, act = actes_tables()
    evt = pl.concat([evt, evt.with_columns(pl.lit("A2").alias("evt_id"))])
    with pytest.warns(UserWarning, match="A2 : aucun objet"):
        paths = hx.write_evenements_serveur_actes(evt, act, entete=ENTETE, out_dir=tmp_path,
                                                  par_acte=True)
    assert len(paths) == 3


def test_par_rum_ligne_enrichie():
    from pyhprimxml.pmsi import iter_evenements_pmsi
    evt = pl.DataFrame({"evt_id": ["S1"], **PATIENT})
    rum = pl.DataFrame({"evt_id": ["S1", "S1"], "rum_id": [1, 2], "um": ["1201", "3405"],
                        "um_date_entree": [date(2024, 3, 4)] * 2, "um_mode_entree": ["8", "6"]})
    lignes = [e for e, _ in iter_evenements_pmsi(evt, rum, entete=ENTETE, par_rum=True)]
    assert [(e["evt_id"], e["evt_origine"], e["rss_id"], e["rum_id"]) for e in lignes] == [
        ("S1_1", "S1", "S1", 1), ("S1_2", "S1", "S1", 2)]


def test_par_defaut_un_message_par_evenement(tmp_path):
    paths = hx.write_evenements_serveur_actes(*actes_tables(), entete=ENTETE, out_dir=tmp_path)
    assert [p.name for p in paths] == ["A1.xml"] and paths[0].read_text().count("<acteCCAM") == 3
