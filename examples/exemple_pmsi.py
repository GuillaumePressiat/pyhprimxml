# Régénère data/xml_tests/pmsi/00001.xml : un séjour (RSS) à deux RUM.
from datetime import date, datetime, time

import polars as pl

import pyhprimxml as hx

# En-tête du message (chaque clé peut aussi être une colonne de `evenements`)
entete = {
    "version": "2.00",                   # version HPRIM XML des messages
    "emetteur": "TEST",
    "destinataire": None,            # agent destinataire sans code, comme le fichier d'origine
    "mode_traitement": "reel",
    "acquittement_attendu": "oui",
    "commentaire": "HPRIM-TEST",
    "date_heure_production": datetime(2024, 1, 1, 1, 1, 1),
}

# Une ligne par séjour, donc par fichier : patient, venue, identifiant du RSS
evenements = pl.DataFrame({
    "evt_id": ["00001_pmsi"],    # -> fichier 00001_pmsi.xml, identifiantMessage 00001_pmsi
    "ipp": ["123456789"], "ipp_recepteur": ["123456789"],
    "sexe": ["M"], "nom_usuel": ["SANDWICK"], "nom_naissance": ["SANDWICK"], "prenom": ["JOHN"],
    "date_naissance": [date(1970, 1, 1)],
    "nda": ["987654321"], "nda_recepteur": ["987654321"],
    "venue_date_entree": [date(2024, 1, 1)], "venue_heure_entree": [time(8, 0)],
    "venue_mode_entree": ["8"], "venue_uf_responsable": ["4321"],
    "rss_emetteur": ["0"], "rss_recepteur": ["000"],
    # colonnes-chemins : attributs sans colonne dédiée
    "patient/@anonyme": ["non"], "patient/@confidentiel": ["non"], "venue/@prive": ["non"],
})

# Une ligne par RUM ; rum_id = rang du RUM dans le RSS (clé de jointure)
rum = pl.DataFrame({
    "evt_id": ["00001_pmsi", "00001_pmsi"],
    "rum_id": [1, 2],
    "rum_emetteur": ["pmsi_00001", "pmsi_00001"],     # identifiant XML du RUM
    "rum_recepteur": ["98765", "98766"],
    "date_action": [datetime(2024, 1, 1, 8, 10), datetime(2024, 1, 1, 9, 0)],
    "um": ["4321", "5000"],
    "um_date_entree": [date(2024, 1, 1)] * 2,
    "um_heure_entree": [time(8, 0), time(9, 0)],
    "um_mode_entree": ["8", "8"],
    "@classant": ["non", "non"],
    "@prestationInterEtablissementA": ["non", "non"],
    "medecinResponsable/identification/code": ["01234567"] * 2,
    "medecinResponsable/personne/nomUsuel": ["HOBBES"] * 2,
    "medecinResponsable/personne/prenoms/prenom": ["MARC-JACQUES"] * 2,
})

# Format long : une ligne par diagnostic, type dans DP, DR, DAS, DAD
diagnostics = pl.DataFrame({
    "evt_id": ["00001_pmsi"] * 3,
    "rum_id": [1, 1, 2],
    "type": ["DP", "DR", "DP"],
    "code": ["Z511", "C10", "Z743"],
})

# Une ligne par acte CCAM
actes = pl.DataFrame({
    "evt_id": ["00001_pmsi"] * 5,
    "rum_id": [1, 1, 1, 1, 2],
    "code": ["EBLA003", "EPLF002", "NFKA006", "YYYY033", "QZRP004"],
    "phase": [0] * 5, "activite": [1] * 5, "quantite": [1] * 5,
    "date_realisation": [datetime(2024, 1, 1, 8, 10)] * 4 + [datetime(2024, 1, 1, 9, 10)],
    "externe": ["non"] * 5, "remboursement_exceptionnel": ["non"] * 5,
})

fichiers = hx.write_evenements_pmsi(
    evenements, rum, diagnostics, actes,
    entete=entete,
    out_dir="sortie/pmsi",           # -> sortie/pmsi/00001_pmsi.xml
    validate_xsd="warn",             # destinataire sans code : non conforme au XSD
)
