"""Actes NGAP du serveur d'actes : écriture, lecture, mélange avec la CCAM, atomicité."""
from datetime import date, time

import polars as pl
import pytest
from polars.testing import assert_frame_equal

import pyhprimxml as hx
from pyhprimxml.serveur_actes import iter_evenements_serveur_actes

ENTETE = {"version": "2.00", "emetteur": "DIM", "destinataire": "DPI"}
EVT = pl.DataFrame({"evt_id": ["E1"], "ipp": ["1"], "sexe": ["F"], "date_naissance": [date(1958, 3, 12)],
                    "nda": ["N1"], "venue_date_entree": [date(2024, 3, 8)]})
NGAP = pl.DataFrame({
    "evt_id": ["E1"] * 3, "acte_id": ["NG01", "NG02", "NG03"],
    "lettre_cle": ["CS", "FTN", "B"], "coefficient": ["1", "1", "26"],
    "date_execution": [date(2024, 3, 8)] * 3, "heure_execution": [time(9, 30), time(10, 15), time(11, 0)],
    "medecin": ["M1"] * 3, "uf": ["2101", "3301", "5201"],
    "numero_forfait_technique": [None, "1", None], "nabm": [None, None, [1104, 593]],
})
CCAM = pl.DataFrame({"evt_id": ["E1"], "acte_id": ["CC01"], "code": ["DEQP003"], "activite": [1],
                     "phase": [0], "date_execution": [date(2024, 3, 8)], "medecin": ["M1"]})


@pytest.mark.parametrize("version", ["2.00", "2.4"])
def test_ngap_valide(tmp_path, version):
    [p] = hx.write_evenements_serveur_actes(EVT, actes_ngap=NGAP, entete=ENTETE, out_dir=tmp_path,
                                            version=version)
    assert hx.validate(p.read_bytes()) == [] and p.read_text().count("<acteNGAP") == 3


def test_ngap_tables_xml_tables(tmp_path):
    hx.write_evenements_serveur_actes(EVT, actes_ngap=NGAP, entete=ENTETE, out_dir=tmp_path)
    relu = hx.read_evenements_serveur_actes(tmp_path)
    assert_frame_equal(relu["actes_ngap"].select(NGAP.columns), NGAP)
    assert relu["actes_ccam"].height == 0


def test_nabm_en_chaine(tmp_path):
    ngap = NGAP.with_columns(pl.Series("nabm", [None, None, "1104, 593"]))
    [a] = hx.write_evenements_serveur_actes(EVT, actes_ngap=ngap, entete=ENTETE, out_dir=tmp_path / "a")
    [b] = hx.write_evenements_serveur_actes(EVT, actes_ngap=NGAP, entete=ENTETE, out_dir=tmp_path / "b")
    assert a.read_bytes() == b.read_bytes()


def test_ccam_et_ngap_dans_un_message(tmp_path):
    [p] = hx.write_evenements_serveur_actes(EVT, CCAM, NGAP, entete=ENTETE, out_dir=tmp_path)
    x = p.read_text()
    assert hx.validate(p.read_bytes()) == []
    assert x.index("<actesCCAM>") < x.index("<actesNGAP>")         # ordre du XSD
    relu = hx.read_evenements_serveur_actes(p)
    assert relu["actes_ccam"]["acte_id"].to_list() == ["CC01"]
    assert relu["actes_ngap"]["acte_id"].to_list() == ["NG01", "NG02", "NG03"]


def test_par_acte_ccam_puis_ngap(tmp_path):
    lignes = [e for e, _ in iter_evenements_serveur_actes(EVT, CCAM, NGAP, entete=ENTETE, par_acte=True)]
    assert [(e["evt_id"], e["acte_id"]) for e in lignes] == [
        ("E1_1", "CC01"), ("E1_2", "NG01"), ("E1_3", "NG02"), ("E1_4", "NG03")]
    paths = hx.write_evenements_serveur_actes(EVT, CCAM, NGAP, entete=ENTETE, out_dir=tmp_path,
                                              par_acte=True)
    contenus = [(p.read_text().count("<acteCCAM"), p.read_text().count("<acteNGAP")) for p in paths]
    assert contenus == [(1, 0), (0, 1), (0, 1), (0, 1)]
    assert all(hx.validate(p.read_bytes()) == [] for p in paths)


def test_ngap_colonne_obligatoire():
    with pytest.raises(hx.HprimWriteError, match="lettre_cle"):
        list(iter_evenements_serveur_actes(EVT, actes_ngap=NGAP.drop("lettre_cle"), entete=ENTETE))


def test_ancien_nom_actes_accepte_avec_avertissement(tmp_path):
    with pytest.warns(FutureWarning, match="actes_ccam"):
        [a] = hx.write_evenements_serveur_actes(EVT, actes=CCAM, entete=ENTETE, out_dir=tmp_path / "a")
    [b] = hx.write_evenements_serveur_actes(EVT, actes_ccam=CCAM, entete=ENTETE, out_dir=tmp_path / "b")
    assert a.read_bytes() == b.read_bytes()
    with pytest.raises(ValueError, match="même table"), pytest.warns(FutureWarning):
        hx.write_evenements_serveur_actes(EVT, actes_ccam=CCAM, actes=CCAM, entete=ENTETE, out_dir=tmp_path / "c")
