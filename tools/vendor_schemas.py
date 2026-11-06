"""Vendorise les XSD HPRIM XML depuis l'archive de spécification Interop'Santé.

Usage : python tools/vendor_schemas.py chemin/vers/hprimXmlVs2_4.zip

Pour chaque version (1.03a ... 2.4), écrit deux variantes dans
pyhprimxml/schemas/<version>/ :
  - ns/   : XSD d'origine (namespace http://www.hprim.org/hprimXML)
  - nons/ : même XSD sans targetNamespace, pour valider des XML à xmlns vide
Les fichiers sont normalisés en UTF-8 / LF (certaines versions anciennes sont en cp1252).
"""
import io
import re
import sys
import zipfile
from pathlib import Path

NS = "http://www.hprim.org/hprimXML"
DEST = Path(__file__).resolve().parents[1] / "pyhprimxml" / "schemas"


def decode(b: bytes) -> str:
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("cp1252")


def main(spec_zip: str) -> None:
    outer = zipfile.ZipFile(spec_zip)
    for name in sorted(n for n in outer.namelist() if re.search(r"schema/schemaHprimV.*\.zip$", n)):
        version = re.search(r"V(\d+_\w+)\.zip$", name).group(1).replace("_", ".")
        inner = zipfile.ZipFile(io.BytesIO(outer.read(name)))
        for variant in ("ns", "nons"):
            (DEST / version / variant).mkdir(parents=True, exist_ok=True)
        for f in inner.namelist():
            if not f.endswith(".xsd"):
                continue
            txt = decode(inner.read(f)).replace("\r\n", "\n")
            txt = re.sub(r'encoding="[^"]+"', 'encoding="UTF-8"', txt, count=1)
            base = Path(f).name
            (DEST / version / "ns" / base).write_text(txt, encoding="utf-8")
            nons = txt.replace(f' targetNamespace="{NS}"', "").replace(f' xmlns="{NS}"', "")
            (DEST / version / "nons" / base).write_text(nons, encoding="utf-8")
        print(version, "ok")


if __name__ == "__main__":
    main(sys.argv[1])
