# Séjour avec mutation : entrée par les urgences en cardiologie (UM 1201), puis mutation
# en médecine (UM 3405), sortie au domicile. Un RSS de deux RUM, écrit sans namespace,
# d'abord en un fichier par séjour, puis en RUM unitaires (un fichier par RUM).
from datetime import date, datetime, time

import polars as pl

import pyhprimxml as hx

entete = {
    "version": "2.00",                   # version HPRIM XML des messages
    "emetteur": "DIM",
    "destinataire": "DPI",
    "date_heure_production": datetime(2024, 3, 10, 8, 0),   # par défaut : maintenant
}

# Une ligne par séjour
evenements = pl.DataFrame({
    "evt_id": ["S240001"],              # -> S240001.xml, identifiantMessage S240001
    "ipp": ["190101337"],
    "sexe": ["F"],
    "date_naissance": [date(1958, 3, 12)],
    "nda": ["240000123"],
    "venue_date_entree": [date(2024, 3, 4)],
    "venue_heure_entree": [time(10, 20)],
    "venue_date_sortie": [date(2024, 3, 9)],
    "rss_emetteur": ["240000123"],
})

# Une ligne par RUM
rum = pl.DataFrame({
    "evt_id": ["S240001", "S240001"],
    "rum_id": [1, 2],
    "rum_emetteur": ["S240001_1", "S240001_2"],   # identifiant XML du RUM
    "um": ["1201", "3405"],
    "um_date_entree": [date(2024, 3, 4), date(2024, 3, 6)],
    "um_heure_entree": [time(10, 20), time(14, 0)],
    "um_mode_entree": ["8", "6"],       # domicile, puis mutation
    "um_provenance": ["5", "1"],        # urgences, puis MCO
    "um_date_sortie": [date(2024, 3, 6), date(2024, 3, 9)],
    "um_mode_sortie": ["6", "8"],       # mutation, puis domicile
    "um_destination": ["1", None],      # vers MCO
    "medecinResponsable/noRPPS": ["10003456789", "10009876543"],
})

# Une ligne par diagnostic (le point des codes CIM-10 est retiré à l'écriture)
diagnostics = pl.DataFrame({
    "evt_id": ["S240001"] * 7,
    "rum_id": [1, 1, 1, 1, 2, 2, 2],
    "type": ["DP", "DAS", "DAS", "DAS", "DP", "DAS", "DAS"],
    "code": ["I21.0", "E11.9", "I10", "E78.0", "I50.1", "N18.3", "E11.9"],
})

# Une ligne par acte CCAM
actes = pl.DataFrame({
    "evt_id": ["S240001"] * 3,
    "rum_id": [1, 1, 2],
    "code": ["DEQP003", "ZBQK002", "DEQP003"],
    "phase": [0, 0, 0],
    "activite": [1, 1, 1],
    "date_realisation": [datetime(2024, 3, 4, 10, 45), datetime(2024, 3, 4, 11, 30),
                         datetime(2024, 3, 6, 15, 0)],
})

# Un fichier par séjour : sortie/sejour/S240001.xml
hx.write_evenements_pmsi(
    evenements, rum, diagnostics, actes,
    entete=entete, out_dir="sortie/sejour", xmlns=None,
)

# RUM unitaires, avec marqueur de dépôt complet :
# sortie/rum/S240001_1.xml puis S240001_1.ok, sortie/rum/S240001_2.xml puis S240001_2.ok
hx.write_evenements_pmsi(
    evenements, rum, diagnostics, actes,
    entete=entete, out_dir="sortie/rum", xmlns=None, par_rum=True, fichier_ok=True,
)

# Relecture : les mêmes tables (ici, diagnostics en colonnes de `rum`)
relu = hx.read_evenements_pmsi("sortie/sejour", format_diagnostics="colonnes")
rum_relu = relu["rum"].select("evt_id", "rum_id", "rum_emetteur", "um", "dp", "das")
