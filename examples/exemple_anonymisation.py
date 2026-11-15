# Anonymiser des fichiers HPRIM XML pour des tests locaux : identifiants et noms
# pseudonymisés (même longueur, même nature de caractères), dates décalées d'un même nombre
# de jours, codes médicaux et attributs intacts.
from datetime import date, datetime

import polars as pl

import pyhprimxml as hx

entete = {
    "version": "2.00",                   # version HPRIM XML des messages
    "emetteur": "DIM",
    "destinataire": "DPI",
    "date_heure_production": datetime(2024, 3, 10, 8, 0),
}
evenements = pl.DataFrame({
    "evt_id": ["S240001"], "ipp": ["190101337"], "sexe": ["F"],
    "nom_usuel": ["MARTIN"], "prenom": ["JEANNE"], "date_naissance": [date(1958, 3, 12)],
    "nda": ["240000123"], "venue_date_entree": [date(2024, 3, 4)],
})
rum = pl.DataFrame({
    "evt_id": ["S240001"], "rum_id": [1], "rum_emetteur": ["S240001_1"], "um": ["1201"],
    "um_date_entree": [date(2024, 3, 4)], "um_mode_entree": ["8"], "dp": ["I21.0"],
    "medecinResponsable/noRPPS": ["10003456789"],
})
hx.write_evenements_pmsi(evenements, rum, entete=entete, out_dir="sortie/original", xmlns=None,
                         fichier_ok=True)

# Anonymisation : chaque fichier reçoit sa propre transformation aléatoire. La graine ne sert
# qu'à rendre cet exemple reproductible (doc, tests) ; en pratique, on l'omet.
anonymes = hx.anonymiser("sortie/original", "sortie/anonyme", graine="exemple")

# Avant / après, à partir des tables relues
extra = {"rum": ["medecinResponsable/noRPPS"]}
avant = hx.read_evenements_pmsi("sortie/original", extra=extra)
apres = hx.read_evenements_pmsi("sortie/anonyme", extra=extra)
champs = {
    "evenements": ["evt_id", "ipp", "nom_usuel", "prenom", "sexe", "date_naissance", "nda",
                   "venue_date_entree"],
    "rum": ["rum_emetteur", "um", "um_date_entree", "medecinResponsable/noRPPS"],
    "diagnostics": ["code"],
}
avant_apres = pl.DataFrame([
    {"champ": c, "original": str(avant[t][c][0]), "anonymise": str(apres[t][c][0])}
    for t, colonnes in champs.items() for c in colonnes
])
