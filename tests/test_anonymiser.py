"""Anonymisation locale de fichiers HPRIM XML : transformation aléatoire par fichier, faker."""
import datetime as dt
import runpy
import shutil
import warnings

import lxml.etree as ET
import pytest

import pyhprimxml as hx
from conftest import ROOT
from pyhprimxml.faker_noms import NOMS, PRENOMS_F, PRENOMS_M

GRAINE = "graine-de-test"


@pytest.fixture
def sources(tmp_path, monkeypatch):
    """Fichiers de l'exemple de séjour (avec .ok) et les trois fichiers de référence."""
    monkeypatch.chdir(tmp_path)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        runpy.run_path(str(ROOT / "examples" / "exemple_sejour.py"))
    src = tmp_path / "sources"
    src.mkdir()
    for f in (tmp_path / "sortie").rglob("*"):
        if f.is_file():
            shutil.copy(f, src / f.name)
    for d in ["pmsi", "actes", "etat_patient"]:
        shutil.copy(ROOT / "data" / "xml_tests" / d / "00001.xml", src / f"ref_{d}.xml")
    return src


def cle(src):
    return f"{GRAINE}|{src.name}"


def test_pseudonyme_longueur_et_nature():
    p = hx.pseudonyme("AB-12 cd é", "k")
    assert len(p) == len("AB-12 cd é")
    assert p[0].isupper() and p[1].isupper() and p[2] == "-" and p[3:5].isdigit()
    assert p[5] == " " and p[6:8].islower() and p[9] == "X"


def test_faker_listes_et_sexe():
    assert hx.faux_nom("MARTIN", "k") in NOMS
    assert hx.faux_prenom("JEANNE", "k", "F") in PRENOMS_F
    assert hx.faux_prenom("JEAN", "k", "M") in PRENOMS_M
    assert hx.faux_prenom("X", "k") in PRENOMS_F + PRENOMS_M
    assert hx.faux_nom("MARTIN", "k") == hx.faux_nom("MARTIN", "k")      # cohérent dans un fichier


def test_aucune_valeur_identifiante_ne_subsiste(sources, tmp_path):
    sortis = hx.anonymiser(sources, tmp_path / "anonymes")
    texte = "".join(p.read_text() for p in sortis)
    for valeur in ["123456789", "987654321", "SANDWICK", "JOHN", "HOBBES", "190101337",
                   "240000123", "S240001", "1958-03-12", "10003456789"]:
        assert valeur not in texte, valeur


def test_conformite_regle_ok_et_attributs(sources, tmp_path):
    sortis = hx.anonymiser(sources, tmp_path / "anonymes", graine=GRAINE)
    for src in sorted(sources.glob("*.xml")):
        a = tmp_path / "anonymes" / f"{hx.pseudonyme(src.stem, cle(src))}.xml"
        assert a in sortis
        assert len(hx.validate(a.read_bytes())) == len(hx.validate(src.read_bytes()))
        assert a.with_suffix(".ok").exists() == src.with_suffix(".ok").exists()
        if not src.stem.startswith("ref_"):      # fichiers qui respectaient la règle
            assert ET.fromstring(a.read_bytes()).findtext(".//{*}identifiantMessage") == a.stem
        sexe = lambda p: ET.fromstring(p.read_bytes()).find(".//{*}personnePhysique").get("sexe")
        assert sexe(a) == sexe(src)


def test_faker_dates_et_coherence_dans_un_fichier(sources, tmp_path):
    src = sources / "ref_pmsi.xml"          # nomUsuel = nomNaissance = SANDWICK, sexe M
    [a] = hx.anonymiser(src, tmp_path / "anonymes", graine=GRAINE)
    t0, t1 = hx.read_evenements_pmsi(src), hx.read_evenements_pmsi(a)
    e = t1["evenements"]
    assert e["nom_usuel"][0] in NOMS and e["nom_usuel"][0] == e["nom_naissance"][0]
    assert e["prenom"][0] in PRENOMS_M
    j = dt.timedelta(days=hx.decalage_jours(cle(src)))
    assert e["date_naissance"][0] == t0["evenements"]["date_naissance"][0] + j
    assert t1["rum"]["date_action"].to_list() == [d + j for d in t0["rum"]["date_action"].to_list()]
    assert t1["rum"]["um_heure_entree"].to_list() == t0["rum"]["um_heure_entree"].to_list()
    assert t1["diagnostics"]["code"].to_list() == t0["diagnostics"]["code"].to_list()
    # même IPP émetteur et récepteur à l'origine -> même pseudonyme dans le fichier
    assert e["ipp"][0] == e["ipp_recepteur"][0] == hx.pseudonyme(t0["evenements"]["ipp"][0], cle(src))


def test_graine_reproductible_sans_graine_aleatoire(sources, tmp_path):
    a = hx.anonymiser(sources, tmp_path / "a", graine=GRAINE)
    b = hx.anonymiser(sources, tmp_path / "b", graine=GRAINE)
    assert [p.read_bytes() for p in a] == [p.read_bytes() for p in b]
    c = hx.anonymiser(sources, tmp_path / "c")
    d = hx.anonymiser(sources, tmp_path / "d")
    assert [p.read_bytes() for p in c] != [p.read_bytes() for p in d]


def test_fichiers_independants(sources, tmp_path):
    """Un même IPP dans deux fichiers reçoit deux pseudonymes différents."""
    a = hx.anonymiser([sources / "S240001.xml", sources / "S240001_1.xml"], tmp_path / "x", graine=GRAINE)
    ipp = [hx.read_evenements_pmsi(p)["evenements"]["ipp"][0] for p in a]
    assert ipp[0] != ipp[1]
