# Régénère data/xml_tests/actes/00001.xml : une intervention et quatre actes CCAM.
from datetime import date, datetime, time

import polars as pl

import pyhprimxml as hx

entete = {
    "version": "2.00",                   # version HPRIM XML des messages
    "emetteur": "TEST",
    "destinataire": None,
    "acquittement_attendu": "oui",
    "commentaire": "HPRIM-TEST",
    "date_heure_production": datetime(2024, 1, 1, 1, 1, 1),
}

# Une ligne par événement : patient, venue, intervention et demande
evenements = pl.DataFrame({
    "evt_id": ["00001_acte"],
    "ipp": ["123456789"], "ipp_recepteur": ["123456789"],
    "sexe": ["M"], "nom_usuel": ["SANDWICK"], "prenom": ["JOHN"],
    "date_naissance": [date(1970, 1, 1)],
    "nda": ["987654321"], "nda_recepteur": ["987654321"],
    "venue_date_entree": [date(2024, 1, 1)], "venue_heure_entree": [time(8, 0)],
    "venue_uf_responsable": ["4321"],
    "venue/@prive": ["non"],
    "intervention_id": ["000000000001"],
    "intervention_date_debut": [date(2024, 1, 1)], "intervention_heure_debut": [time(8, 10)],
    "intervention_date_fin": [date(2024, 1, 1)], "intervention_heure_fin": [time(9, 0)],
    "intervention_uf": ["4321"],
    "demande_date": [date(2023, 12, 25)], "demande_heure": [time(2, 30)], "demande_uf": ["4321"],
})

# Une ligne par acte CCAM
actes = pl.DataFrame({
    "evt_id": ["00001_acte"] * 4,
    "acte_id": ["121212", "121213", "121214", "121215"],
    "code": ["EBLA003", "YYYY033", "EPLF002", "NFKA006"],
    "activite": [1] * 4, "phase": [0] * 4,
    "date_execution": [date(2024, 1, 1)] * 4, "heure_execution": [time(8, 10)] * 4,
    "medecin": ["01234567"] * 4, "uf": ["4321"] * 4,
    "quantite": ["1"] * 4,           # nombre5 : chaîne de chiffres dans le XSD
    "facturable": ["oui"] * 4, "valide": ["oui"] * 4,
})

fichiers = hx.write_evenements_serveur_actes(
    evenements, actes,
    entete=entete,
    out_dir="sortie/actes",          # -> sortie/actes/00001_acte.xml
    validate_xsd="warn",
)
