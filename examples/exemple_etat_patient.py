# Régénère data/xml_tests/etat_patient/00001.xml : diagnostics DP et DR.
from datetime import date, datetime, time

import polars as pl

import pyhprimxml as hx

entete = {
    "version": "2.00",                   # version HPRIM XML des messages
    "emetteur": "TEST",
    "destinataire": None,
    "acquittement_attendu": "non",
    "commentaire": "HPRIM-TEST",
    "date_heure_production": datetime(2024, 1, 1, 1, 1, 1),
}

# Une ligne par événement : patient, venue, intervention
# (ici, les colonnes-chemins sont relatives à la racine du message)
evenements = pl.DataFrame({
    "evt_id": ["00001_esep"],
    "ipp": ["123456789"], "ipp_recepteur": ["123456789"],
    "sexe": ["M"], "nom_usuel": ["SANDWICK"], "prenom": ["JOHN"],
    "date_naissance": [date(1970, 1, 1)],
    "nda": ["987654321"], "nda_recepteur": ["987654321"],
    "venue_date_entree": [date(2024, 1, 1)], "venue_heure_entree": [time(8, 0)],
    "venue_uf_responsable": ["4321"],
    "intervention_id": ["000000000001"], "intervention_uf": ["4321"],
    "patient/@confidentiel": ["non"], "venue/@prive": ["non"],
    "patient/identifiant/emetteur/@etat": ["permanent"],
    "patient/identifiant/emetteur/@portee": ["local"],
    "patient/identifiant/emetteur/@referent": ["non"],
    "patient/identifiant/recepteur/@etat": ["permanent"],
    "patient/identifiant/recepteur/@portee": ["local"],
    "patient/identifiant/recepteur/@referent": ["non"],
})

# Une ligne par diagnostic ; type dans dp, dr, da, ds, dd, fpc, mm, ae
diagnostics = pl.DataFrame({
    "evt_id": ["00001_esep", "00001_esep"],
    "type": ["dp", "dr"],
    "code": ["Z511", "C10"],
    "date_action": [datetime(2024, 1, 1, 8, 10)] * 2,
})

fichiers = hx.write_evenements_etat_patient(
    evenements, diagnostics,
    entete=entete,
    out_dir="sortie/etat_patient",   # -> sortie/etat_patient/00001_esep.xml
    validate_xsd="warn",
)
