# Actes NGAP dans un message serveur d'actes : une consultation, un forfait technique et un
# acte de biologie avec ses codes NABM. Lettres-clés, coefficients, codes et montants sont
# illustratifs : à remplacer par ceux de vos référentiels.
from datetime import date, datetime, time

import polars as pl

import pyhprimxml as hx

entete = {
    "version": "2.00",                   # version HPRIM XML des messages
    "emetteur": "DIM",
    "destinataire": "DPI",
    "date_heure_production": datetime(2024, 3, 10, 8, 0),
}

# Contexte : une ligne par événement (patient, venue)
evenements = pl.DataFrame({
    "evt_id": ["EXT0001"],
    "ipp": ["190101337"], "sexe": ["F"], "date_naissance": [date(1958, 3, 12)],
    "nda": ["240000125"], "venue_date_entree": [date(2024, 3, 8)],
})

# Actes NGAP : une ligne par acte
actes_ngap = pl.DataFrame({
    "evt_id": ["EXT0001"] * 3,
    "acte_id": ["NG01", "NG02", "NG03"],
    "lettre_cle": ["CS", "FTN", "B"],               # consultation, forfait technique, biologie
    "coefficient": ["1", "1", "26"],
    "date_execution": [date(2024, 3, 8)] * 3,
    "heure_execution": [time(9, 30), time(10, 15), time(11, 0)],
    "medecin": ["10003456789"] * 3,
    "uf": ["2101", "3301", "5201"],
    "montant_total": ["30.00", "70.00", "7.02"],    # montants en euros (illustratifs)
    "numero_forfait_technique": [None, "1", None],  # forfait technique
    "numero_agrement_appareil": [None, "12345678901234", None],
    "nabm": [None, None, [1104, 593]],              # codes NABM de l'acte de biologie
})

# Un message avec les trois actes : sortie/ngap/EXT0001.xml
hx.write_evenements_serveur_actes(evenements, actes_ngap=actes_ngap, entete=entete,
                                  out_dir="sortie/ngap")

# Un message par acte (unité atomique) : sortie/ngap_atomique/EXT0001_1.xml… _3.xml
hx.write_evenements_serveur_actes(evenements, actes_ngap=actes_ngap, entete=entete,
                                  out_dir="sortie/ngap_atomique", par_acte=True)

# Relecture : la table actes_ngap, codes NABM compris
relu = hx.read_evenements_serveur_actes("sortie/ngap")["actes_ngap"]
