"""La documentation affiche exactement le code des scripts d'examples/ et ce qu'il produit.

Source unique : examples/exemple_*.py. tools/exemples_doc.py injecte leur code dans le
README et les docstrings, et génère les tableaux et extraits XML à partir de leur
exécution ; la doc MkDocs les inclut à la construction. Ce test échoue si quelque chose
n'est plus synchronisé : lancer alors ``python tools/exemples_doc.py``.
"""
import importlib.util
import inspect
import re
import textwrap

import pytest

import pyhprimxml as hx
from conftest import ROOT

spec = importlib.util.spec_from_file_location("exemples_doc", ROOT / "tools" / "exemples_doc.py")
exemples_doc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exemples_doc)

DOCSTRINGS = {"pmsi": hx.write_evenements_pmsi, "actes": hx.write_evenements_serveur_actes,
              "etat_patient": hx.write_evenements_etat_patient}


def test_readme_doc_et_docstrings_a_jour():
    assert exemples_doc.main(check=True) == [], "lancer : python tools/exemples_doc.py"


@pytest.mark.parametrize("nom", exemples_doc.SCRIPTS)
def test_readme_affiche_le_script(nom):
    readme = (ROOT / "README.md").read_text()
    m = re.search(rf"<!-- exemple:{nom} -->\n```python\n(.*?)\n```\n<!-- /exemple:{nom} -->",
                  readme, re.S)
    assert m and m.group(1) == exemples_doc.code(nom)


@pytest.mark.parametrize("nom", DOCSTRINGS)
def test_docstring_affiche_le_script(nom):
    doc = inspect.getdoc(DOCSTRINGS[nom])
    m = re.search(r"Examples:.*?```python\n(.*?)\n\s*```", doc, re.S)
    assert m and textwrap.dedent(m.group(1)) == exemples_doc.code(nom)


@pytest.mark.parametrize("page", ["doc/index.md", "doc/guide/ecriture.md",
                                  "doc/guide/autres-messages.md", "doc/exemples.md"])
def test_doc_contient_le_code_en_clair(page):
    """Le code est écrit dans les fichiers .md eux-mêmes (pas d'inclusion à la construction)."""
    texte = (ROOT / page).read_text()
    assert "--8<--" not in texte
    for nom in re.findall(r"<!-- exemple:(\w+) -->", texte):
        m = re.search(rf"<!-- exemple:{nom} -->\n```python\n(.*?)\n```\n<!-- /exemple:{nom} -->",
                      texte, re.S)
        assert m and m.group(1) == exemples_doc.code(nom), (page, nom)


def test_tous_les_scripts_sont_dans_la_page_exemples():
    texte = (ROOT / "doc" / "exemples.md").read_text()
    for nom in exemples_doc.SCRIPTS:
        assert f"<!-- exemple:{nom} -->" in texte, nom


def test_presentation_commune_readme_et_accueil():
    """Le README et la page d'accueil de la doc partagent le même texte de présentation."""
    fragment = (ROOT / "tools" / "fragments" / "presentation.md").read_text().rstrip("\n")
    for page in ["README.md", "doc/index.md"]:
        assert fragment in (ROOT / page).read_text(), page


def test_accueil_montre_l_exemple_reel():
    texte = (ROOT / "doc" / "index.md").read_text()
    assert "<!-- exemple:sejour -->" in texte and "S240001_2" in texte
