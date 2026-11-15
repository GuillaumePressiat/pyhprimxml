"""Écriture et lecture dans toutes les versions : anciennes versions, XSD officiel invalide."""
import runpy
import warnings

import polars as pl
import pytest

import pyhprimxml as hx
from conftest import ROOT
from pyhprimxml.io.output import accorder_enumeration


@pytest.fixture(scope="module")
def exemples(tmp_path_factory):
    import os
    cwd = os.getcwd()
    os.chdir(tmp_path_factory.mktemp("ex"))
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return {n: runpy.run_path(str(ROOT / "examples" / f"exemple_{n}.py"))
                    for n in ["sejour", "serveur_actes"]}
    finally:
        os.chdir(cwd)


def entete(e):
    return {k: v for k, v in e.items() if k != "version"} | {"destinataire": "DPI"}


def test_accorder_enumeration():
    assert accorder_enumeration("creation", ["création", "modification"]) == "création"
    assert accorder_enumeration("réel", ["reel", "test"]) == "reel"
    assert accorder_enumeration("creation", ["création", "creation"]) == "creation"   # déjà autorisé
    assert accorder_enumeration("autre", ["création"]) == "autre"                     # rien à accorder
    assert accorder_enumeration("x", None) == "x"


@pytest.mark.parametrize("version", hx.available_versions())
def test_serveur_actes_toutes_versions(tmp_path, exemples, version):
    e = exemples["serveur_actes"]
    [p] = hx.write_evenements_serveur_actes(e["evenements"], e["actes_ccam"], entete=entete(e["entete"]),
                                            out_dir=tmp_path, version=version)
    assert hx.validate(p.read_bytes()) == []


@pytest.mark.parametrize("version", ["1.04", "1.05", "1.07"])
def test_pmsi_1_0x_action_accentuee(tmp_path, exemples, version):
    e = exemples["sejour"]
    evt = e["evenements"].with_columns(pl.lit("DUPONT").alias("nom_usuel"), pl.lit("ANNE").alias("prenom"))
    [p] = hx.write_evenements_pmsi(evt, e["rum"], e["diagnostics"], e["actes_ccam"], entete=entete(e["entete"]),
                                   out_dir=tmp_path, version=version)
    assert hx.validate(p.read_bytes()) == []
    assert '<rum action="création"' in p.read_text()


def test_pmsi_1_06_lecture_et_ecriture_sans_validation(tmp_path, exemples):
    e = exemples["sejour"]
    evt = e["evenements"].with_columns(pl.lit("DUPONT").alias("nom_usuel"), pl.lit("ANNE").alias("prenom"))
    args = (evt, e["rum"], e["diagnostics"], e["actes_ccam"])
    with pytest.raises(hx.HprimSchemaError):
        hx.write_evenements_pmsi(*args, entete=entete(e["entete"]), out_dir=tmp_path / "a", version="1.06")
    [p] = hx.write_evenements_pmsi(*args, entete=entete(e["entete"]), out_dir=tmp_path / "b",
                                   version="1.06", validate_xsd=False)
    t = hx.read_evenements_pmsi(p)
    assert t["evenements"]["version"][0] == "1.06" and t["rum"].height == 2


def test_cle_renseignee_hors_version_refusee(tmp_path, exemples):
    """Une valeur pour un élément absent de la version reste refusée (ici noRPPS en 1.03a)."""
    e = exemples["sejour"]
    with pytest.raises(hx.HprimWriteError, match="noRPPS"):
        hx.write_evenements_pmsi(e["evenements"], e["rum"], e["diagnostics"], e["actes_ccam"],
                                 entete=entete(e["entete"]), out_dir=tmp_path, version="1.03a")
