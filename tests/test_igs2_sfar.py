"""Le barème IGS2 de examples/exemple_igs2.py est conforme à la grille de la SFAR.

Source : https://sfar.org/scores/igs2.php (grille et définitions), d'après Le Gall JR et
coll., JAMA 1993; 270: 2957-2963. Les points ci-dessous sont recopiés de cette page.
"""
import polars as pl
import pytest

# item XSD : (seuils, points par classe), dans l'ordre croissant de la mesure
SFAR = {
    "age": ([40, 60, 70, 75, 80], [0, 7, 12, 15, 16, 18]),
    "frequenceCardiaque": ([40, 70, 120, 160], [11, 2, 0, 4, 7]),
    "tensionArterielleSystolique": ([70, 100, 200], [13, 5, 0, 2]),
    "temperature": ([39], [0, 3]),
    "paO2_FIO2": ([100, 200], [11, 9, 6]),          # si ventilé ou sous CPAP
    "diurese": ([0.5, 1.0], [11, 4, 0]),            # L/24 h
    "ureeSanguine": ([10, 30], [0, 6, 10]),         # mmol/L
    "leucocytes": ([1, 20], [12, 0, 3]),            # 10³/mm³
    "kaliemie": ([3, 5], [3, 0, 3]),
    "natremie": ([125, 145], [5, 0, 1]),
    "HCO3": ([15, 20], [6, 3, 0]),
    "bilirubine": ([68.4, 102.6], [0, 4, 9]),       # µmol/L, si ictère
    "scoreGlasgow": ([6, 9, 11, 14], [26, 13, 7, 5, 0]),
}
SFAR_QUALITATIFS = {
    "modeAdmission": {"chirUrgente": 8, "medecine": 6, "chirProgrammee": 0},
    "maladieChronique": {"aucune": 0, "cancerMetastatique": 9,
                         "maladieHematologiqueMaligne": 10, "sida": 17},
}


@pytest.fixture(scope="module")
def igs2_ns(tmp_path_factory):
    import os
    import runpy
    from conftest import ROOT
    cwd = os.getcwd()
    os.chdir(tmp_path_factory.mktemp("igs2"))
    try:
        return runpy.run_path(str(ROOT / "examples" / "exemple_igs2.py"))
    finally:
        os.chdir(cwd)


@pytest.mark.parametrize("item", SFAR)
def test_seuils_et_points_conformes_a_la_sfar(igs2_ns, item):
    _, bornes, classes = igs2_ns["BAREME"][item]
    seuils, points = SFAR[item]
    assert bornes == seuils
    assert [p for _, p in classes] == points


@pytest.mark.parametrize("item", SFAR_QUALITATIFS)
def test_items_qualitatifs_conformes_a_la_sfar(igs2_ns, item):
    assert igs2_ns["POINTS_QUALITATIFS"][item][1] == SFAR_QUALITATIFS[item]


def test_valeurs_aux_seuils(igs2_ns):
    """Une valeur égale au seuil tombe dans la classe supérieure (bornes fermées à gauche)."""
    mesure, bornes, classes = igs2_ns["BAREME"]["age"]
    df = pl.DataFrame({mesure: [39, 40, 59, 60, 79, 80, None]})
    s = df.select(igs2_ns["classer"](mesure, bornes, [c for c, _ in classes]))[:, 0]
    assert s.to_list() == ["inferieurA40", "40A59", "40A59", "60A69", "75A79",
                           "superieurEgalA80", None]


def test_regles_conditionnelles(igs2_ns):
    """PaO2/FiO2 sans ventilation et bilirubine sans ictère : 0 point (définitions SFAR)."""
    igs2 = igs2_ns["igs2"]
    p2 = igs2.filter(pl.col("evt_id") == "IGS240002")      # non ventilé, ictérique
    assert p2["paO2_FIO2"].item() == "rien" and p2["points_paO2_FIO2"].item() == 0
    assert p2["bilirubine"].item() == "superieurA102,6" and p2["points_bilirubine"].item() == 9
    p1 = igs2.filter(pl.col("evt_id") == "IGS240001")      # ventilé, non ictérique
    assert p1["points_paO2_FIO2"].item() == 9 and p1["points_bilirubine"].item() == 0
