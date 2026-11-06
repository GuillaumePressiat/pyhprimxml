import datetime as d
from pathlib import Path

import lxml.etree as ET
import pandas as pd
import polars as pl
import pytest
import xmltodict

import pyhprimxml as hx

DATA = Path(__file__).parents[1] / "data" / "xml_tests"
EXAMPLES = sorted(DATA.glob("*/00001.xml"))


def c14n(b: bytes) -> str:
    return ET.canonicalize(b.decode(), strip_text=True)


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.parent.name)
def test_aller_retour_exact(path):
    """XML -> dict -> XML redonne le fichier d'origine (vides conservés)."""
    src = path.read_bytes()
    out = hx.to_xml(xmltodict.parse(src), drop_empty=False)
    assert c14n(out) == c14n(src)


def test_drop_empty_supprime_les_vides():
    tree = xmltodict.parse((DATA / "pmsi" / "00001.xml").read_bytes())
    out = hx.to_xml(tree)
    assert b"<seance" not in out and b"radiotherapie" not in out
    # seule erreur restante : un défaut des données (agent destinataire sans code)
    errors = hx.validate(out)
    assert len(errors) == 1 and "agent" in errors[0]


@pytest.mark.parametrize("xmlns", [hx.HPRIM_NS, None, ""])
def test_variantes_xmlns(xmlns):
    tree = xmltodict.parse((DATA / "pmsi" / "00001.xml").read_bytes())
    out = hx.to_xml(tree, xmlns=xmlns)
    racine = out.split(b"\n")[1]
    if xmlns:
        assert b'xmlns="http://www.hprim.org/hprimXML"' in racine
    elif xmlns == "":
        assert b'xmlns=""' in racine
    else:
        assert b"xmlns" not in racine
    assert ET.fromstring(out) is not None


def test_cle_inconnue_strict():
    tree = xmltodict.parse((DATA / "pmsi" / "00001.xml").read_bytes())
    tree["evenementsPMSI"]["enteteMessage"]["champInvente"] = "x"
    with pytest.raises(hx.HprimWriteError, match="champInvente"):
        hx.to_xml(tree)


def tables():
    evt = pl.DataFrame({
        "evt_id": ["E1", "E2"], "ipp": ["123456789", "222"], "nda": ["987654321", "333"],
        "sexe": ["M", "F"], "date_naissance": [d.date(1970, 1, 1), d.date(1985, 5, 5)],
        "venue_date_entree": [d.date(2024, 1, 1), d.date(2024, 2, 1)], "rss_emetteur": ["0", "1"],
    })
    rum = pl.DataFrame({
        "evt_id": ["E1", "E1", "E2"], "rum_id": ["R1", "R2", "R3"], "um": ["4321", "5000", "4321"],
        "um_date_entree": [d.date(2024, 1, 1), d.date(2024, 1, 2), d.date(2024, 2, 1)],
        "um_mode_entree": ["8", "6", "8"], "um_provenance": [None, "1", None],
        "um_date_sortie": [d.date(2024, 1, 2), d.date(2024, 1, 3), None],
        "um_mode_sortie": ["6", "8", None], "um_destination": ["1", None, None],
    })
    diag = pl.DataFrame({
        "evt_id": ["E1"] * 4, "rum_id": ["R1", "R1", "R1", "R2"],
        "type": ["DP", "DR", "DAS", "DP"], "code": ["Z511", "C10", "E11.9", "Z743"],
    })
    act = pl.DataFrame({
        "evt_id": ["E1", "E1"], "rum_id": ["R1", "R1"], "code": ["EBLA003", "NFKA006"],
        "phase": [0, 0], "activite": [1, 1], "modificateurs": ["7J", None],
        "date_realisation": [d.datetime(2024, 1, 1, 8, 10), None],
    })
    return evt, rum, diag, act


ENTETE = {"emetteur": "DIM", "destinataire": "DPI"}


@pytest.mark.parametrize("xmlns", [hx.HPRIM_NS, None, ""])
def test_un_fichier_par_evenement_valide(tmp_path, xmlns):
    paths = hx.write_evenements_pmsi(*tables(), entete=ENTETE, out_dir=tmp_path, xmlns=xmlns)
    assert [p.name for p in paths] == ["E1.xml", "E2.xml"]
    for p in paths:
        assert hx.validate(p.read_bytes()) == []
    e1 = xmltodict.parse(paths[0].read_bytes())["evenementsPMSI"]["evenementPMSI"]["rss"]["rum"]
    assert len(e1) == 2
    assert e1[0]["diagnostics"]["diagnosticsSignificatifs"]["diagnosticSignificatif"]["codeCim10"] == "E119"


def test_entree_pandas(tmp_path):
    evt, rum, diag, act = (t.to_pandas() for t in tables())
    paths = hx.write_evenements_pmsi(evt, rum, diag, act, entete=ENTETE, out_dir=tmp_path)
    assert all(hx.validate(p.read_bytes()) == [] for p in paths)


def test_erreur_xsd_signalee(tmp_path):
    evt, rum, diag, act = tables()
    diag = diag.with_columns(pl.when(pl.col("type") == "DP").then(pl.lit("PASUNCODE"))
                             .otherwise(pl.col("code")).alias("code"))
    with pytest.raises(hx.HprimWriteError, match="E1"):
        hx.write_evenements_pmsi(evt, rum, diag, act, entete=ENTETE, out_dir=tmp_path)


def test_un_fichier_par_rum(tmp_path):
    paths = hx.write_evenements_pmsi(*tables(), entete=ENTETE, out_dir=tmp_path, par_rum=True)
    assert [p.name for p in paths] == ["E1_R1.xml", "E1_R2.xml", "E2_R3.xml"]
    t = hx.read_evenements_pmsi(tmp_path)
    assert all(hx.validate(p.read_bytes()) == [] for p in paths)
    # chaque message : un seul RUM, ses propres diagnostics, et le même séjour (RSS, venue)
    assert t["rum"]["rum_emetteur"].to_list() == ["R1", "R2", "R3"]
    assert t["evenements"]["identifiant_message"].to_list() == ["E1_R1", "E1_R2", "E2_R3"]
    assert t["evenements"]["rss_emetteur"].to_list() == ["0", "0", "1"]
    assert t["diagnostics"].filter(pl.col("evt_id") == "E1_R2")["code"].to_list() == ["Z743"]


def test_par_rum_un_fichier_par_rum(tmp_path):
    paths = hx.write_evenements_pmsi(*tables(), entete=ENTETE, out_dir=tmp_path, par_rum=True)
    assert [p.name for p in paths] == ["E1_R1.xml", "E1_R2.xml", "E2_R3.xml"]
    t = hx.read_evenements_pmsi(tmp_path)
    assert t["rum"]["rum_emetteur"].to_list() == ["R1", "R2", "R3"]
    # chaque message ne contient que son RUM, avec ses diagnostics et actes
    assert t["rum"].group_by("evt_id").len()["len"].to_list() == [1, 1, 1]
    diag = t["diagnostics"].filter(pl.col("evt_id") == "E1_R2")
    assert diag["code"].to_list() == ["Z743"]
    assert t["actes"]["evt_id"].unique().to_list() == ["E1_R1"]
    # le séjour reste identifiable : même identifiantRSS et même NDA
    assert t["evenements"]["rss_emetteur"].to_list() == ["0", "0", "1"]


def identifiant(path) -> str:
    return ET.fromstring(path.read_bytes()).findtext(".//{*}identifiantMessage")


def test_par_rum_gabarit(tmp_path):
    paths = hx.write_evenements_pmsi(*tables(), entete=ENTETE, out_dir=tmp_path, par_rum=True,
                                     filename="RUM_{rum_id}.xml")
    assert [p.name for p in paths] == ["RUM_R1.xml", "RUM_R2.xml", "RUM_R3.xml"]
    assert [identifiant(p) for p in paths] == ["RUM_R1", "RUM_R2", "RUM_R3"]


def test_identifiant_egal_nom_fichier(tmp_path):
    paths = hx.write_evenements_pmsi(*tables(), entete=ENTETE, out_dir=tmp_path, par_rum=True)
    assert all(identifiant(p) == p.stem for p in paths)


def test_identifiant_contradictoire(tmp_path):
    evt, rum, diag, act = tables()
    evt = evt.with_columns(pl.Series("identifiant_message", ["AUTRE1", "AUTRE2"]))
    with pytest.raises(hx.HprimWriteError, match="différent du nom de fichier"):
        hx.write_evenements_pmsi(evt, rum, diag, act, entete=ENTETE, out_dir=tmp_path)
    # règle désactivée : identifiant et nom de fichier indépendants
    paths = hx.write_evenements_pmsi(evt, rum, diag, act, entete=ENTETE, out_dir=tmp_path,
                                     identifiant_egal_nom_fichier=False)
    assert [(p.name, identifiant(p)) for p in paths] == [("E1.xml", "AUTRE1"), ("E2.xml", "AUTRE2")]


def test_nom_de_fichier_trop_long(tmp_path):
    with pytest.raises(hx.HprimWriteError, match="12 caractères"):
        hx.write_evenements_pmsi(*tables(), entete=ENTETE, out_dir=tmp_path, par_rum=True,
                                 filename="RUM_{nda}_{rum_id}.xml")


def test_noms_de_fichier_en_double(tmp_path):
    with pytest.raises(hx.HprimWriteError, match="deux événements"):
        hx.write_evenements_pmsi(*tables(), entete=ENTETE, out_dir=tmp_path, filename="RSS.xml")


def test_identifiant_message_trop_long(tmp_path):
    evt, rum, diag, act = tables()
    evt = evt.with_columns(pl.col("evt_id") + "_SEJOUR_LONG")
    rum = rum.with_columns(pl.col("evt_id") + "_SEJOUR_LONG")
    with pytest.raises(hx.HprimWriteError, match="12 caractères"):
        hx.write_evenements_pmsi(evt, rum, entete=ENTETE, out_dir=tmp_path)


def test_identifiant_message_par_rum(tmp_path):
    evt, rum, diag, act = tables()
    rum = rum.with_columns(pl.Series("identifiant_message", ["M001", "M002", "M003"]))
    # l'identifiant fourni par RUM nomme aussi le fichier
    paths = hx.write_evenements_pmsi(evt, rum, diag, act, entete=ENTETE, out_dir=tmp_path,
                                     par_rum=True, filename="{identifiant_message}.xml")
    assert [p.name for p in paths] == ["M001.xml", "M002.xml", "M003.xml"]
    t = hx.read_evenements_pmsi(paths)
    assert t["evenements"]["identifiant_message"].to_list() == ["M001", "M002", "M003"]
    assert t["evenements"]["evt_id"].to_list() == ["M001", "M002", "M003"]


def test_fichier_ok_depose_apres_le_xml(tmp_path):
    paths = hx.write_evenements_pmsi(*tables(), entete=ENTETE, out_dir=tmp_path, par_rum=True,
                                     fichier_ok=True)
    for p in paths:
        ok = p.with_suffix(".ok")
        assert ok.exists() and ok.read_bytes() == b""
        assert ok.stat().st_mtime_ns >= p.stat().st_mtime_ns     # .ok posé après le .xml
    assert not list(tmp_path.glob(".*.tmp"))                       # aucun temporaire restant


def test_sans_fichier_ok_par_defaut(tmp_path):
    hx.write_evenements_pmsi(*tables(), entete=ENTETE, out_dir=tmp_path)
    assert not list(tmp_path.glob("*.ok"))


def test_echec_de_validation_ne_depose_rien(tmp_path):
    evt, rum, diag, act = tables()
    diag = diag.with_columns(pl.when(pl.col("rum_id") == "R1").then(pl.lit("PASUNCODE"))
                             .otherwise(pl.col("code")).alias("code"))
    with pytest.raises(hx.HprimWriteError):
        hx.write_evenements_pmsi(evt, rum, diag, act, entete=ENTETE, out_dir=tmp_path,
                                 fichier_ok=True)
    assert not list(tmp_path.glob("E1*"))                           # ni .xml ni .ok


def test_suivi_depots_et_lecture_des_depots_complets(tmp_path):
    hx.write_evenements_pmsi(*tables(), entete=ENTETE, out_dir=tmp_path, par_rum=True,
                             fichier_ok=True)
    (tmp_path / "E1_R2.ok").unlink()                                # dépôt « en cours »
    (tmp_path / "ORPHELIN.ok").touch()
    suivi = hx.suivi_depots(tmp_path)
    assert dict(zip(suivi["evt_id"], suivi["complet"])) == {
        "E1_R1": True, "E1_R2": False, "E2_R3": True, "ORPHELIN": False}
    assert suivi.filter(pl.col("evt_id") == "ORPHELIN")["fichier"].to_list() == [None]
    # côté destinataire : ne lire que les dépôts terminés
    with pytest.warns(UserWarning, match="1 fichier"):
        t = hx.read_evenements_pmsi(tmp_path, exiger_ok=True)
    assert t["evenements"]["evt_id"].to_list() == ["E1_R1", "E2_R3"]


@pytest.mark.parametrize("encoding", ["UTF-8", "ISO-8859-1"])
def test_une_seule_declaration_xml(encoding):
    """lxml ajoute sa propre déclaration hors UTF-8 : il ne doit y en avoir qu'une."""
    tree = xmltodict.parse((DATA / "pmsi" / "00001.xml").read_bytes())
    tree["evenementsPMSI"]["enteteMessage"]["commentaireMessage"] = "é € œ"
    out = hx.to_xml(tree, encoding=encoding)
    assert out.count(b"<?xml") == 1
    root = ET.fromstring(out)  # XML bien formé
    assert root.find(".//{*}commentaireMessage").text == "é € œ"


def test_diagnostics_doublon_dp_refuse(tmp_path):
    evt, rum, diag, act = tables()
    rum = rum.with_columns(dp=pl.lit("I10"))          # DP aussi présent dans diagnostics
    with pytest.raises(hx.HprimWriteError, match="plusieurs DP"):
        hx.write_evenements_pmsi(evt, rum, diag, act, entete=ENTETE, out_dir=tmp_path)


def test_diagnostics_plusieurs_codes_dans_dp_refuse(tmp_path):
    evt, rum, _, act = tables()
    rum = rum.with_columns(dp=pl.lit("I10, I11"))
    with pytest.raises(hx.HprimWriteError, match="un seul DP"):
        hx.write_evenements_pmsi(evt, rum, None, act, entete=ENTETE, out_dir=tmp_path)


def test_diagnostics_liste_depuis_pandas(tmp_path):
    evt, rum, _, act = tables()
    rum_pd = rum.with_columns(dp=pl.lit("Z511"), das=pl.lit(["E11.9", "I10"])).to_pandas()
    paths = hx.write_evenements_pmsi(evt.to_pandas(), rum_pd, entete=ENTETE, out_dir=tmp_path)
    t = hx.read_evenements_pmsi(paths[0])
    assert t["diagnostics"]["code"].to_list() == ["Z511", "E119", "I10", "Z511", "E119", "I10"]


def test_etat_patient_2_4_valide(tmp_path):
    """En 2.4, <divers/> est obligatoire et un repère (ici dateObservation) aussi."""
    import datetime as d
    evt = pl.DataFrame({"evt_id": ["EP1"], "ipp": ["123"], "sexe": ["F"],
                        "date_naissance": [d.date(1970, 1, 1)],
                        "date_observation": [d.date(2024, 1, 2)]})
    diag = pl.DataFrame({"evt_id": ["EP1"], "type": ["dp"], "code": ["Z511"]})
    [p] = hx.write_evenements_etat_patient(evt, diag, entete=ENTETE, out_dir=tmp_path)
    xml = p.read_bytes()
    assert hx.validate(xml) == [] and b"<divers/>" in xml
    # en 2.00, divers est facultatif : il n'est pas écrit
    [p2] = hx.write_evenements_etat_patient(evt, diag, entete=ENTETE, out_dir=tmp_path / "v2",
                                            version="2.00")
    assert b"divers" not in p2.read_bytes() and hx.validate(p2.read_bytes()) == []
