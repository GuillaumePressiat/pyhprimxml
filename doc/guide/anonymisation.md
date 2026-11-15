# Anonymiser des fichiers

Pour tester sur de vrais fichiers sans manipuler de données identifiantes, `anonymiser`
réécrit un lot de fichiers HPRIM XML sous une forme pseudonymisée, conforme au XSD comme
l'original :

- **chaque fichier reçoit sa propre transformation aléatoire** : rien ne relie deux fichiers
  anonymisés. À l'intérieur d'un fichier, tout reste cohérent : une même valeur donne le même
  remplacement partout dans le fichier ;
- **noms et prénoms** (patient, professionnels de santé) sont remplacés par des noms français
  plausibles, tirés de listes de noms courants (faker), le prénom selon le sexe du patient ;
  `nomNaissance` reste égal à `nomUsuel` quand ils l'étaient ;
- **les identifiants** (patient, venue, RSS, RUM, actes, intervention, recueil, message), les
  adresses et les commentaires sont remplacés par des valeurs de même longueur et de même
  nature (chiffre par chiffre, lettre par lettre) ;
- **toutes les dates** d'un fichier sont décalées d'un même nombre de jours, tiré au hasard :
  durées et âges sont conservés ; les heures ne changent pas ;
- **les codes et les attributs** ne sont pas touchés (CIM-10, CCAM, NGAP, UM, sexe, modes,
  actions…) : c'est le XSD qui dit ce qui est un attribut ;
- **le nom de fichier** est pseudonymisé comme l'identifiant du message, et un `.ok` présent
  à côté du fichier source est reproduit.

```python
hx.anonymiser("arrivee/", "anonymes/")
```

## Exemple

Un message PMSI écrit, anonymisé, puis relu (script `examples/exemple_anonymisation.py`) :

<!-- exemple:anonymisation -->
```python
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
```
<!-- /exemple:anonymisation -->

Avant et après :

<!-- tables:anonymisation:avant_apres -->
| champ | original | anonymise |
|---|---|---|
| evt_id | S240001 | H574920 |
| ipp | 190101337 | 714992668 |
| nom_usuel | MARTIN | DUPONT |
| prenom | JEANNE | CAROLINE |
| sexe | F | F |
| date_naissance | 1958-03-12 | 1958-11-10 |
| nda | 240000123 | 487868840 |
| venue_date_entree | 2024-03-04 | 2024-11-02 |
| rum_emetteur | S240001_1 | M252453_2 |
| um | 1201 | 1201 |
| um_date_entree | 2024-03-04 | 2024-11-02 |
| medecinResponsable/noRPPS | 10003456789 | 43527999314 |
| code | I210 | I210 |
<!-- /tables:anonymisation:avant_apres -->

## Reproductibilité

Sans argument particulier, chaque appel donne un résultat différent. L'argument `graine` rend
le résultat reproductible (même graine et même fichier source donnent le même fichier
anonymisé) : il sert à la documentation et aux tests, comme dans l'exemple ci-dessus.

Les fonctions de base sont aussi disponibles : `hx.anonymiser_message(hx.parse_xml(f), cle)`
anonymise un message déjà lu en dictionnaire, avec la clé de transformation `cle` ;
`hx.pseudonyme`, `hx.faux_nom`, `hx.faux_prenom` et `hx.decalage_jours` donnent les
remplacements correspondants.

## Limites

!!! warning "Pseudonymisation, pas anonymisation au sens du RGPD"
    Les fichiers produits restent des données de santé : codes rares, durées, unités
    médicales ou combinaisons de diagnostics peuvent permettre des recoupements. Ils sont
    destinés à des tests locaux, pas à une diffusion. Un faux nom plausible peut, par hasard,
    être celui d'une vraie personne : rien ne le relie pour autant à la personne d'origine.

Le package R `hprimxml` produit les mêmes fichiers, octet pour octet, avec `hprim_anonymiser()`.
