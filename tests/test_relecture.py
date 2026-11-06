"""Relecture vers tables et allers-retours dans les deux sens."""
import sys
import warnings
from pathlib import Path

import polars as pl
import pytest
import xmltodict
from polars.testing import assert_frame_equal

import pyhprimxml as hx
from conftest import REFERENCES, ROOT, c14n
from pyhprimxml.common import is_path


def extra_depuis(ns: dict, tables: list[str]) -> dict:
    """Les colonnes-chemins utilisées à l'écriture deviennent ``extra`` à la lecture."""
    return {t: [c for c in ns[t].columns if is_path(c)] for t in tables}


LECTURES = {"pmsi": hx.read_evenements_pmsi, "actes": hx.read_evenements_serveur_actes,
            "etat_patient": hx.read_evenements_etat_patient}


@pytest.mark.parametrize("nom", REFERENCES)
def test_tables_xml_tables(tmp_path, executer, nom):
    """tables -> XML -> tables : on retrouve exactement les tables d'origine."""
    script, dossier, _, tables = REFERENCES[nom]
    ns = executer(script)
    relu = LECTURES[nom](tmp_path / "sortie" / dossier, extra=extra_depuis(ns, tables))
    for t in tables:
        assert_frame_equal(relu[t].select(ns[t].columns), ns[t])


def test_sejour_tables_xml_tables(tmp_path, executer):
    ns = executer("exemple_sejour.py")
    tables = ["evenements", "rum", "diagnostics", "actes"]
    relu = hx.read_evenements_pmsi(tmp_path / "sortie" / "sejour", extra=extra_depuis(ns, tables))
    for t in tables:
        attendu = ns[t]
        if t == "diagnostics":  # le point des codes CIM-10 est retiré à l'écriture
            attendu = attendu.with_columns(pl.col("code").str.replace(".", "", literal=True))
        assert_frame_equal(relu[t].select(attendu.columns), attendu, check_dtypes=False)


@pytest.mark.parametrize("nom", REFERENCES)
def test_xml_tables_xml(tmp_path, executer, nom):
    """XML -> tables -> XML : on retrouve le fichier de référence (sans ses éléments vides).
    Aucun ``entete`` n'est passé : l'en-tête est porté par les colonnes de ``evenements``.
    Les fichiers de référence ne respectent pas la règle identifiantMessage = nom de fichier
    (00001.xml contient 00001_pmsi) : on la désactive pour les réécrire à l'identique."""
    script, dossier, ecrire, tables = REFERENCES[nom]
    ns = executer(script)
    src = ROOT / "data" / "xml_tests" / dossier / "00001.xml"
    relu = LECTURES[nom](src, extra=extra_depuis(ns, tables))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        [path] = ecrire(*[relu[t] for t in tables], out_dir=tmp_path / "relu",
                        validate_xsd="warn", identifiant_egal_nom_fichier=False)
    assert c14n(path.read_bytes()) == c14n(hx.to_xml(xmltodict.parse(src.read_bytes())))


def test_lecture_typee():
    t = hx.read_evenements_pmsi(ROOT / "data" / "xml_tests" / "pmsi" / "00001.xml")
    assert t["evenements"].schema["date_naissance"] == pl.Date
    assert t["rum"].schema["date_action"] == pl.Datetime("us")
    assert t["rum"].schema["um_heure_entree"] == pl.Time
    assert t["actes"].schema["phase"] == pl.Int64
    assert t["rum"]["rum_id"].to_list() == [1, 2]
    assert t["diagnostics"]["type"].to_list() == ["DP", "DR", "DP"]


def test_acte_unique_reste_une_liste():
    """Un RUM avec un seul acte : le XSD dit répétable, on obtient bien 1 ligne d'acte."""
    t = hx.read_evenements_pmsi(ROOT / "data" / "xml_tests" / "pmsi" / "00001.xml")
    assert t["actes"].filter(pl.col("rum_id") == 2)["code"].to_list() == ["QZRP004"]


def test_namespace_indifferent(tmp_path, executer):
    """Un fichier sans namespace se relit comme un fichier avec."""
    ns = executer("exemple_sejour.py")
    avec = hx.write_evenements_pmsi(ns["evenements"], ns["rum"], ns["diagnostics"], ns["actes"],
                                    entete=ns["entete"], out_dir=tmp_path / "ns")
    ta, tb = hx.read_evenements_pmsi(avec), hx.read_evenements_pmsi(tmp_path / "sortie" / "sejour")
    for t in ta:
        assert_frame_equal(ta[t], tb[t])


def test_plusieurs_fichiers_et_pandas(tmp_path):
    sys.path.insert(0, str(ROOT / "tests"))
    from test_write import ENTETE, tables
    hx.write_evenements_pmsi(*tables(), entete=ENTETE, out_dir=tmp_path)
    t = hx.read_evenements_pmsi(tmp_path, backend="pandas")
    assert list(t["evenements"]["evt_id"]) == ["E1", "E2"]
    assert len(t["rum"]) == 3 and list(t["rum"]["rum_emetteur"]) == ["R1", "R2", "R3"]
    assert sorted(t["diagnostics"]["code"]) == ["C10", "E119", "Z511", "Z743"]


def test_diagnostics_en_colonnes_aller_retour(tmp_path, executer):
    """format_diagnostics='colonnes' : dp/dr/das/dad dans rum, réécrits à l'identique."""
    executer("exemple_sejour.py")
    src = tmp_path / "sortie" / "sejour"
    t = hx.read_evenements_pmsi(src, format_diagnostics="colonnes",
                                extra={"rum": ["medecinResponsable/noRPPS"]})
    assert t["diagnostics"].height == 0
    assert t["rum"]["das"].to_list() == [["E119", "I10", "E780"], ["N183", "E119"]]
    assert t["rum"]["dp"].to_list() == ["I210", "I501"]
    [a] = sorted(src.glob("*.xml"))
    [b] = hx.write_evenements_pmsi(*t.values(), out_dir=tmp_path / "reecrit", xmlns=None)
    assert a.read_bytes() == b.read_bytes()
