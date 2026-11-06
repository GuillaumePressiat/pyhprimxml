"""Synchronise le code et les tables d'exemple affichés dans la documentation.

Source unique : les scripts examples/exemple_*.py.

- README.md : le code de chaque script est injecté entre <!-- exemple:NOM --> et
  <!-- /exemple:NOM --> ; les tables entre <!-- tables:NOM:TABLE --> et
  <!-- /tables:NOM:TABLE --> sont générées à partir des DataFrames que le script construit,
  et le contenu des fichiers produits entre <!-- fichier:NOM:CHEMIN --> et
  <!-- /fichier:NOM:CHEMIN --> (chemin relatif au dossier sortie/ du script).
- Docstrings de write_evenements_* : le code du script est injecté dans « Examples ».
- Textes communs (présentation…) : tools/fragments/NOM.md, injecté entre
  <!-- fragment:NOM --> et <!-- /fragment:NOM --> dans le README et la doc.
- doc/ (MkDocs) : mêmes marqueurs que dans le README. Le code, les tables et les extraits
  XML sont donc écrits en clair dans les fichiers .md (lisibles dans un éditeur ou sur
  GitHub), et pas seulement dans le site construit.

Usage :
    python tools/exemples_doc.py           # met à jour README, doc et docstrings
    python tools/exemples_doc.py --check   # échoue si quelque chose n'est pas à jour
tests/test_code_documente.py lance la vérification.
"""
from __future__ import annotations

import ast
import datetime as dt
import os
import re
import runpy
import sys
import tempfile
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCRIPTS = {
    "pmsi": "examples/exemple_pmsi.py",
    "actes": "examples/exemple_serveur_actes.py",
    "etat_patient": "examples/exemple_etat_patient.py",
    "sejour": "examples/exemple_sejour.py",
    "diagnostics": "examples/exemple_diagnostics.py",
    "igs2": "examples/exemple_igs2.py",
}
# exemple montré dans la docstring de chaque fonction d'écriture
DOCSTRINGS = {
    "pmsi": ("pyhprimxml/pmsi.py", "write_evenements_pmsi"),
    "actes": ("pyhprimxml/serveur_actes.py", "write_evenements_serveur_actes"),
    "etat_patient": ("pyhprimxml/etat_patient.py", "write_evenements_etat_patient"),
}
PAGES = ["README.md", "doc/index.md", "doc/guide/ecriture.md", "doc/guide/lecture.md",
         "doc/guide/autres-messages.md", "doc/exemples.md"]
FRAGMENTS = ROOT / "tools" / "fragments"


def code(nom: str) -> str:
    return (ROOT / SCRIPTS[nom]).read_text().rstrip("\n")


def executer(nom: str) -> dict:
    """Exécute le script dans un dossier temporaire et renvoie ses variables, plus les
    fichiers qu'il a écrits (clé ``__fichiers__`` : chemin relatif -> contenu)."""
    sys.path.insert(0, str(ROOT))
    cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as d, warnings.catch_warnings():
        warnings.simplefilter("ignore")
        os.chdir(d)
        try:
            ns = runpy.run_path(str(ROOT / SCRIPTS[nom]))
            sortie = Path(d) / "sortie"
            ns["__fichiers__"] = {str(f.relative_to(sortie)): f.read_text(encoding="utf-8")
                                  for f in sorted(sortie.rglob("*.xml"))}
            return ns
        finally:
            os.chdir(cwd)
            sys.path.remove(str(ROOT))


def cellule(v) -> str:
    if v is None:
        return ""
    if isinstance(v, list):  # colonne List : entre crochets
        return "[" + ", ".join(cellule(x) for x in v) + "]"
    if isinstance(v, str) and "," in v:  # chaîne à virgules : entre guillemets
        return '"' + v + '"'
    if isinstance(v, dt.datetime):
        return v.strftime("%Y-%m-%d %H:%M")
    if isinstance(v, dt.time):
        return v.strftime("%H:%M")
    return str(v)


def markdown(df) -> str:
    cols = df.columns
    lignes = ["| " + " | ".join(f"`{c}`" if ("/" in c or c.startswith("@")) else c for c in cols) + " |",
              "|" + "|".join("---" for _ in cols) + "|"]
    for row in df.iter_rows():
        lignes.append("| " + " | ".join(cellule(v) for v in row) + " |")
    return "\n".join(lignes)


def remplacer(texte: str, debut: str, fin: str, contenu: str) -> str:
    motif = re.escape(debut) + r".*?" + re.escape(fin)
    return re.sub(motif, lambda m: f"{debut}\n{contenu}\n{fin}", texte, flags=re.S)


def page_a_jour(path: Path, cache: dict) -> str:
    s = path.read_text()
    for nom in re.findall(r"<!-- fragment:([\w-]+) -->", s):
        texte = (FRAGMENTS / f"{nom}.md").read_text().rstrip("\n")
        s = remplacer(s, f"<!-- fragment:{nom} -->", f"<!-- /fragment:{nom} -->", texte)
    for nom in SCRIPTS:
        if f"<!-- exemple:{nom} -->" in s:
            s = remplacer(s, f"<!-- exemple:{nom} -->", f"<!-- /exemple:{nom} -->",
                          f"```python\n{code(nom)}\n```")
    for nom, table in re.findall(r"<!-- tables:(\w+):(\w+) -->", s):
        if nom not in cache:
            cache[nom] = executer(nom)
        s = remplacer(s, f"<!-- tables:{nom}:{table} -->", f"<!-- /tables:{nom}:{table} -->",
                      markdown(cache[nom][table]))
    for nom, fichier in re.findall(r"<!-- fichier:(\w+):([\w/.-]+) -->", s):
        if nom not in cache:
            cache[nom] = executer(nom)
        s = remplacer(s, f"<!-- fichier:{nom}:{fichier} -->", f"<!-- /fichier:{nom}:{fichier} -->",
                      f"```xml\n{cache[nom]['__fichiers__'][fichier]}\n```")
    return s


def docstring_a_jour(nom: str) -> tuple[Path, str]:
    path_rel, fn = DOCSTRINGS[nom]
    p = ROOT / path_rel
    src = p.read_text()
    node = next(n for n in ast.walk(ast.parse(src))
                if isinstance(n, ast.FunctionDef) and n.name == fn)
    ds = node.body[0]
    lines = src.splitlines(keepends=True)
    doc = ast.get_docstring(node, clean=False)
    doc = re.sub(r"\n\s*Examples:.*$", "", doc, flags=re.S).rstrip()
    ind = " " * (node.col_offset + 4)
    corps = "\n".join((ind + "    " + l) if l else "" for l in code(nom).splitlines())
    doc += (f"\n\n{ind}Examples:\n"
            f"{ind}    Script ``{SCRIPTS[nom]}`` :\n\n"
            f"{ind}    ```python\n{corps}\n{ind}    ```")
    lines[ds.lineno - 1:ds.end_lineno] = [f'{ind}"""{doc}\n{ind}"""\n']
    return p, "".join(lines)


def cibles() -> dict[Path, str]:
    """Contenu attendu de chaque fichier synchronisé."""
    cache: dict = {}
    out = {ROOT / p: page_a_jour(ROOT / p, cache) for p in PAGES}
    for nom in DOCSTRINGS:
        p, s = docstring_a_jour(nom)
        out[p] = s
    return out


def main(check: bool = False) -> list[str]:
    perimes = []
    for p, attendu in cibles().items():
        if p.read_text() != attendu:
            perimes.append(str(p.relative_to(ROOT)))
            if not check:
                p.write_text(attendu)
    return perimes


if __name__ == "__main__":
    check = "--check" in sys.argv
    perimes = main(check=check)
    if check and perimes:
        print("Pas à jour (lancer python tools/exemples_doc.py) :", ", ".join(perimes))
        sys.exit(1)
    print("à jour" if check else f"mis à jour : {', '.join(perimes) or 'rien'}")
