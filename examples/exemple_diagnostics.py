# Trois façons équivalentes de fournir les diagnostics d'un RUM avec plusieurs DAS.
# Les trois écritures produisent exactement le même fichier XML.
from datetime import date, datetime
from pathlib import Path

import polars as pl

import pyhprimxml as hx

entete = {
    "version": "2.00",                   # version HPRIM XML des messages
    "emetteur": "DIM",
    "destinataire": "DPI",
    "date_heure_production": datetime(2024, 3, 10, 8, 0),
}

evenements = pl.DataFrame({
    "evt_id": ["S240002"], "ipp": ["190101338"], "sexe": ["M"],
    "date_naissance": [date(1951, 7, 2)], "nda": ["240000124"],
    "venue_date_entree": [date(2024, 3, 4)], "rss_emetteur": ["240000124"],
})

rum = pl.DataFrame({
    "evt_id": ["S240002"], "rum_id": [1], "um": ["1201"],
    "um_date_entree": [date(2024, 3, 4)], "um_mode_entree": ["8"],
})

# 1. Format long : une table `diagnostics`, une ligne par code
diagnostics = pl.DataFrame({
    "evt_id": ["S240002"] * 5,
    "rum_id": [1] * 5,
    "type": ["DP", "DAS", "DAS", "DAS", "DAS"],
    "code": ["I21.0", "E11.9", "I10", "E78.0", "N18.3"],
})
hx.write_evenements_pmsi(evenements, rum, diagnostics, entete=entete, out_dir="sortie/long")

# 2. Colonnes dans `rum`, DAS en liste (type List de polars)
rum_liste = rum.with_columns(
    dp=pl.lit("I21.0"),
    das=pl.lit(["E11.9", "I10", "E78.0", "N18.3"]),
)
hx.write_evenements_pmsi(evenements, rum_liste, entete=entete, out_dir="sortie/liste")

# 3. Colonnes dans `rum`, DAS en chaîne séparée par des virgules
rum_chaine = rum.with_columns(
    dp=pl.lit("I21.0"),
    das=pl.lit("E11.9, I10, E78.0, N18.3"),
)
hx.write_evenements_pmsi(evenements, rum_chaine, entete=entete, out_dir="sortie/chaine")

# Une chaîne se convertit aussi en liste d'une ligne : pl.col("das").str.split(", ")
fichiers = {f: Path("sortie", f, "S240002.xml").read_bytes() for f in ("long", "liste", "chaine")}
assert fichiers["long"] == fichiers["liste"] == fichiers["chaine"]
