# Relire vers des tables

Les fonctions `read_*` sont l'inverse exact des fonctions `write_*` : elles renvoient les
mêmes tables, avec les mêmes noms de colonnes.

```python
import pyhprimxml as hx

t = hx.read_evenements_pmsi("dossier/")
t["evenements"], t["rum"], t["diagnostics"], t["actes"]

hx.read_evenements_serveur_actes("actes/")   # {"evenements", "actes"}
hx.read_evenements_etat_patient("etats/")    # {"evenements", "diagnostics"}
```

`sources` accepte un fichier, un dossier (tous ses `*.xml`), un motif glob
(`"arrivee/*_2024*.xml"`), un contenu `bytes`, ou une liste de tout cela.

## Lecture guidée par le XSD

**Les éléments répétables sont toujours des listes.** Un RUM avec un seul acte donne bien
une ligne dans `actes` : pas de cas particulier « un seul élément » à gérer.

**Les colonnes sont typées d'après le XSD.**

| type XSD | colonne |
|---|---|
| `xsd:date` | `Date` |
| `xsd:dateTime` | `Datetime` |
| `xsd:time` | `Time` |
| types entiers (`xsd:integer`, `nombre2`…) | `Int64` |
| le reste, et tous les attributs | `String` |

!!! note "Particularités du XSD"
    `nombre2` est un entier, mais `nombre5` est une chaîne de chiffres (`[0-9]{0,5}`).
    La `quantite` des actes du serveur d'actes (`nombre5`) est donc relue en texte, celle
    des RUM (`nombre2`) en entier. Le package suit le XSD plutôt que de deviner.

**Le namespace est indifférent.** Un fichier avec namespace, sans namespace ou à `xmlns`
vide se relit à l'identique.

## Clés absentes du XML

Le XML ne contient pas les clés de jointure ; elles sont reconstruites.

- `evt_id` est le nom du fichier sans extension. Si un fichier contient plusieurs
  événements, ils sont suffixés `_1`, `_2`…
- `rum_id` est le rang du RUM dans le RSS (1, 2…). L'identifiant XML du RUM est dans
  `rum_emetteur`.

## En-tête

L'en-tête du message est relu dans des colonnes de `evenements` : `version`,
`acquittement_attendu`, `mode_traitement`, `identifiant_message`, `date_heure_production`,
`emetteur`, `emetteur_categorie`, `destinataire`, `destinataire_categorie`, `commentaire`.

À l'écriture, ces colonnes priment sur le dictionnaire `entete`. On peut donc réécrire
directement ce qu'on a lu :

```python
t = hx.read_evenements_pmsi("arrivee/")
# ... corrections ...
hx.write_evenements_pmsi(*t.values(), out_dir="renvoi/")
```

## Extraire des chemins supplémentaires : `extra`

`extra` est le symétrique des [colonnes-chemins](ecriture.md#colonnes-chemins) : il liste,
par table, les chemins à extraire en plus des colonnes métier. Les chemins sont relatifs
au même nœud qu'à l'écriture.

```python
t = hx.read_evenements_pmsi(
    "dossier/",
    extra={
        "evenements": ["patient/@anonyme", "venue/@prive"],
        "rum": ["@classant", "medecinResponsable/identification/code"],
        "actes": ["CCAM/@remboursementExceptionnel"],
    },
)
```

Les colonnes obtenues portent le nom du chemin : elles sont réécrites telles quelles par
`write_evenements_pmsi`.

## Diagnostics en colonnes : `format_diagnostics`

Par défaut, les diagnostics sont renvoyés au format long, dans la table `diagnostics`.
`format_diagnostics="colonnes"` les place plutôt dans `rum` : `dp` et `dr` (un code), `das`
et `dad` (listes). La table `diagnostics` est alors vide.

```python
t = hx.read_evenements_pmsi("dossier/", format_diagnostics="colonnes")
t["rum"].select("rum_id", "dp", "das")
# rum_id | dp   | das
# 1      | I210 | ["E119", "I10", "E780"]
# 2      | I501 | ["N183", "E119"]
```

Les deux formes se réécrivent telles quelles avec `write_evenements_pmsi` (voir
[Diagnostics : format long, liste ou chaîne](ecriture.md#diagnostics-format-long-liste-ou-chaine)).

## Dépôts inachevés : `exiger_ok`

`exiger_ok=True` ne lit que les `.xml` accompagnés de leur marqueur `.ok`, déposé par
l'émetteur une fois le fichier complet. Les autres sont ignorés, avec un avertissement
(voir [dépôts `.ok`](rum-unitaires.md#cote-destinataire-ne-lire-que-les-depots-termines)).

## pandas

`backend="pandas"` renvoie des DataFrames pandas (nécessite `pyarrow`).

## Performances et limites

Débit indicatif : environ 3 000 fichiers par seconde.

- PMSI : seul le RSS MCO est lu. Les `rhss`, `rpsss`, `rimp` et `rssGhs` sont signalés
  par un avertissement.
- Serveur d'actes : seuls les actes CCAM sont lus.
- Les actes CDAM d'un RUM ne sont pas repris dans la table `actes`.
