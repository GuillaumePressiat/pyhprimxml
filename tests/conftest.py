import runpy
import warnings
from pathlib import Path

import lxml.etree as ET
import pytest
import xmltodict

import pyhprimxml as hx

ROOT = Path(__file__).parents[1]

# exemples qui régénèrent les fichiers de data/xml_tests
REFERENCES = {
    # nom : (script, dossier de référence, fonction d'écriture, tables dans l'ordre d'appel)
    "pmsi": ("exemple_pmsi.py", "pmsi", hx.write_evenements_pmsi,
             ["evenements", "rum", "diagnostics", "actes"]),
    "actes": ("exemple_serveur_actes.py", "actes", hx.write_evenements_serveur_actes,
              ["evenements", "actes"]),
    "etat_patient": ("exemple_etat_patient.py", "etat_patient", hx.write_evenements_etat_patient,
                     ["evenements", "diagnostics"]),
}


def c14n(b: bytes) -> str:
    return ET.canonicalize(b.decode(), strip_text=True)


def reference(dossier: str) -> str:
    """Fichier de référence, débarrassé de ses éléments vides (non conformes au XSD)."""
    src = (ROOT / "data" / "xml_tests" / dossier / "00001.xml").read_bytes()
    return c14n(hx.to_xml(xmltodict.parse(src)))


@pytest.fixture
def executer(tmp_path, monkeypatch):
    """Exécute un script d'examples/ dans tmp_path ; renvoie ses variables."""
    def run(script: str) -> dict:
        monkeypatch.chdir(tmp_path)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # agent destinataire sans code : voulu
            return runpy.run_path(str(ROOT / "examples" / script))
    return run
