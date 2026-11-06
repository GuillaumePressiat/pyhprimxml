"""Les scripts d'examples/ s'exécutent et produisent les fichiers attendus."""
import warnings
from datetime import date

import lxml.etree as ET
import pytest

import pyhprimxml as hx
from conftest import REFERENCES, c14n, reference


def identifiant(path) -> str:
    return ET.fromstring(path.read_bytes()).findtext(".//{*}identifiantMessage")


@pytest.mark.parametrize("nom", REFERENCES)
def test_regenere_le_fichier_de_reference(tmp_path, executer, nom):
    script, dossier, _, _ = REFERENCES[nom]
    executer(script)
    [path] = (tmp_path / "sortie" / dossier).glob("*.xml")
    assert identifiant(path) == path.stem          # règle identifiant = nom de fichier
    assert c14n(path.read_bytes()) == reference(dossier)


@pytest.mark.parametrize("nom", REFERENCES)
def test_sans_namespace_seule_erreur_agent(tmp_path, executer, nom):
    script, _, ecrire, tables = REFERENCES[nom]
    ns = executer(script)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        [path] = ecrire(*[ns[t] for t in tables], entete=ns["entete"], version="2.00",
                        out_dir=tmp_path / "nons", xmlns=None, validate_xsd=False)
    data = path.read_bytes()
    assert b"xmlns" not in data.split(b"\n")[1]
    errors = hx.validate(data)
    assert len(errors) == 1 and "agent" in errors[0]


def test_sejour_realiste(tmp_path, executer):
    executer("exemple_sejour.py")
    sejour = sorted((tmp_path / "sortie" / "sejour").glob("*.xml"))
    par_rum = sorted((tmp_path / "sortie" / "rum").glob("*.xml"))
    assert [p.name for p in sejour] == ["S240001.xml"]
    assert [p.name for p in par_rum] == ["S240001_1.xml", "S240001_2.xml"]
    # RUM unitaires déposés avec leur marqueur .ok ; le fichier par séjour, sans
    assert sorted(p.name for p in (tmp_path / "sortie" / "rum").glob("*.ok")) == [
        "S240001_1.ok", "S240001_2.ok"]
    assert not list((tmp_path / "sortie" / "sejour").glob("*.ok"))
    for p in sejour + par_rum:
        assert hx.validate(p.read_bytes()) == []
        assert identifiant(p) == p.stem
        assert b"xmlns" not in p.read_bytes().split(b"\n")[1]


def test_diagnostics_trois_formes(tmp_path, executer):
    """Le script vérifie lui-même que les trois formes donnent le même fichier."""
    executer("exemple_diagnostics.py")
    xml = (tmp_path / "sortie" / "long" / "S240002.xml").read_bytes()
    assert hx.validate(xml) == []
    assert xml.count(b"<diagnosticSignificatif>") == 4


def test_igs2_detaille(tmp_path, executer):
    ns = executer("exemple_igs2.py")
    fichiers = sorted((tmp_path / "sortie" / "igs2").glob("*.xml"))
    assert [p.name for p in fichiers] == ["IGS240001.xml", "IGS240002.xml"]
    for p in fichiers:
        assert hx.validate(p.read_bytes()) == []
        assert b"<recueil>" in p.read_bytes() and b"<dateObservation>" not in p.read_bytes()
    assert ns["igs2"]["valeurGlobale"].to_list() == [54, 56]
    # relecture : les classes et le score se retrouvent par `extra`
    chemins = ["igs2/@age", "igs2/@paO2_FIO2", "igs2/@scoreGlasgow", "igs2/valeurGlobale"]
    t = hx.read_evenements_etat_patient(fichiers, extra={"evenements": chemins})
    evt = t["evenements"]
    assert evt["igs2/@age"].to_list() == ["60A69", "superieurEgalA80"]
    assert evt["igs2/@paO2_FIO2"].to_list() == ["100A199", "rien"]
    assert evt["igs2/valeurGlobale"].to_list() == [54, 56]
    assert evt["recueil_date"].to_list() == [date(2024, 3, 6)] * 2
    assert evt["recueil_uf"].to_list() == ["4501", "4501"]
    assert evt["recueil_id"].to_list() == ["REC240001", "REC240002"]


@pytest.mark.parametrize("script,ecrire,tables", [
    ("exemple_sejour.py", hx.write_evenements_pmsi, ["evenements", "rum", "diagnostics", "actes"]),
    ("exemple_diagnostics.py", hx.write_evenements_pmsi, ["evenements", "rum", "diagnostics"]),
    ("exemple_igs2.py", hx.write_evenements_etat_patient, ["evenements"]),
])
def test_exemples_aussi_valides_en_2_4(tmp_path, executer, script, ecrire, tables):
    """Les exemples sont en 2.00 ; le package écrit en 2.4 par défaut : on vérifie les deux."""
    ns = executer(script)
    args = [ns[t] for t in tables] + ([None] if ecrire is hx.write_evenements_etat_patient else [])
    fichiers = ecrire(*args, entete=ns["entete"], version="2.4", out_dir=tmp_path / "v24")
    for p in fichiers:
        xml = p.read_bytes()
        assert b'version="2.4"' in xml and hx.validate(xml) == []
