# pyhprimxml


## Lecture de fichiers hprimXML avec python


> **"Projet en cours de développement"**

> **À ce stade sans garantie, ce code n'engage que celui qui l'utilise.**

> Ce projet a également une visée documentaire / bloc-notes. Enfin il ne cherche pas à répondre à un besoin particulier mais propose des pistes pour exploiter ces données dans divers contextes en les dénaturant le moins possible.

L'objectif de ce projet est de lire les fichiers au format [hprimXML](https://www.interopsante.org/hprim), un standard interop français.


###### Bibliothèques utilisées

- lxml : pour enlever le namespace xmlns avec un script xslt
- xmltodict : pour convertir le xml en dict python 
- json : pour encapsuler le dict en json pour la lecture avec pl.read_json
- polars : pour les étapes de déstructuration de la donnée hiérarchique issue des XML
- io, os, glob : pour les étapes de manipulations de fichiers dans le système


###### Ressources

- Le script pour le namespace xslt est issu de la ressource [ici](https://wiki.tei-c.org/index.php/Remove-Namespaces.xsl)
- La fonction d'applatissement récursif des struct/list en polars est issue d'[ici](https://github.com/pola-rs/polars/issues/7078#issuecomment-2258225305)



## Contexte

Il existe plusieurs manières de lire les données d'un fichier XML.

La plus rapide en temps est certainement d'utiliser les chemins xpath.
Néanmoins cet accès rapide fait souvent l'impasse sur la structure hiérarchique du fichier qui en tant que telle est une information importante.


### Utilisation de xpath pour interroger des éléments xml

Trois exemples sont réalisés autour des fichiers hprimXML utilisant xpath :

- le [premier](https://guillaumepressiat.github.io/pyhprimxml/xpath_xml.html) utilise le package python xml en spécifiant le namespace xmlns d'hprim au travers d'un alias dans les définitions de xpath.
- le [deuxième](https://guillaumepressiat.github.io/pyhprimxml/xpath_lxml.html) utilise le package python lxml en supprimant le namespace xmlns avant d'utiliser xpath.

- le [troisième](https://guillaumepressiat.github.io/pyhprimxml/xpath_xml_r.html) utilise R et le package xml2 en supprimant le namespace xmlns avant d'utiliser xpath.

### Récupération des éléments XML complets


L'utilisation du package [pyhprimxml](https://guillaumepressiat.github.io/pyhprimxml/) dans le contexte de la lecture de fichiers hprimXML (v1.07 et v2 testés) est présentée [ici](https://guillaumepressiat.github.io/pyhprimxml/).

Ainsi, on récupère les tables et les liens hiérarchiques entre les éléments du XML (parents/enfants).

#### Exemple

```python
from pyhprimxml import read_hprimxml
from pyhprimxml import recursively_flatten
from pyhprimxml import flatten
from pyhprimxml import unpack
import polars as pl

input_file = 'pyhprimxml/data/xml_tests/actes/00001.xml'
read_hprimxml(input_file)
```

```text
{'type_evenement': ['evenementsServeurActes'],
 'message': shape: (1, 5)
 ┌─────────────────────┬─────────┬───────────────────────────┬──────────────────────────┬───────────┐
 │ acquittementAttendu ┆ version ┆ enteteMessage             ┆ evenementServeurActe     ┆ source_id │
 │ ---                 ┆ ---     ┆ ---                       ┆ ---                      ┆ ---       │
 │ str                 ┆ str     ┆ struct[5]                 ┆ struct[4]                ┆ str       │
 ╞═════════════════════╪═════════╪═══════════════════════════╪══════════════════════════╪═══════════╡
 │ oui                 ┆ 2.00    ┆ {"00001_acte","2024-01-01 ┆ {{{{"123456789"},{"12345 ┆ 00001.xml │
 │                     ┆         ┆ T01:0…                    ┆ 6789"}…                  ┆           │
 └─────────────────────┴─────────┴───────────────────────────┴──────────────────────────┴───────────┘}
```

```python
(
    read_hprimxml(input_file)['message']
    .select('source_id', 'evenementServeurActe')
    .pipe(unpack, 'evenementServeurActe')
)
```

```text
shape: (1, 5)
┌───────────┬─────────────────────┬─────────────────────┬─────────────────────┬────────────────────┐
│ source_id ┆ patient             ┆ venue               ┆ intervention        ┆ actesCCAM          │
│ ---       ┆ ---                 ┆ ---                 ┆ ---                 ┆ ---                │
│ str       ┆ struct[2]           ┆ struct[3]           ┆ struct[5]           ┆ struct[1]          │
╞═══════════╪═════════════════════╪═════════════════════╪═════════════════════╪════════════════════╡
│ 00001.xml ┆ {{{"123456789"},{"1 ┆ {"non",{{"987654321 ┆ {{"000000000001"},{ ┆ {[{"creation","oui │
│           ┆ 23456789"}},{"M","S ┆ "},{"987654321"}},{ ┆ "2024-01-01","08:10 ┆ ","oui",{"121212"} │
│           ┆ ANDWICK",{"J…       ┆ {"2024-01-01…       ┆ :00"},{"2024…       ┆ ,"EBLA003","1"…    │
└───────────┴─────────────────────┴─────────────────────┴─────────────────────┴────────────────────┘
```

```python
recursively_flatten(
    read_hprimxml(input_file)['message']
    .select('source_id', 'evenementServeurActe')
    .unnest('evenementServeurActe')
    .select('source_id', 'patient')
    ).unpivot(index = 'source_id', variable_name = 'element_name', value_name = 'value')
```

```text
shape: (6, 3)
┌───────────┬─────────────────────────────────────────────┬────────────┐
│ source_id ┆ element_name                                ┆ value      │
│ ---       ┆ ---                                         ┆ ---        │
│ str       ┆ str                                         ┆ str        │
╞═══════════╪═════════════════════════════════════════════╪════════════╡
│ 00001.xml ┆ patient.identifiant.emetteur.valeur         ┆ 123456789  │
│ 00001.xml ┆ patient.identifiant.recepteur.valeur        ┆ 123456789  │
│ 00001.xml ┆ patient.personnePhysique.sexe               ┆ M          │
│ 00001.xml ┆ patient.personnePhysique.nomUsuel           ┆ SANDWICK   │
│ 00001.xml ┆ patient.personnePhysique.prenoms.prenom     ┆ JOHN       │
│ 00001.xml ┆ patient.personnePhysique.dateNaissance.date ┆ 1970-01-01 │
└───────────┴─────────────────────────────────────────────┴────────────┘
```

```python
recursively_flatten(
    read_hprimxml(input_file)['message']
    .select('source_id', 'evenementServeurActe')
    .unnest('evenementServeurActe')
    .select('source_id', 'intervention')
    ).unpivot(index = 'source_id', variable_name = 'element_name', value_name = 'value')
```

```text
shape: (9, 3)
┌───────────┬──────────────────────────────────────────────┬──────────────┐
│ source_id ┆ element_name                                 ┆ value        │
│ ---       ┆ ---                                          ┆ ---          │
│ str       ┆ str                                          ┆ str          │
╞═══════════╪══════════════════════════════════════════════╪══════════════╡
│ 00001.xml ┆ intervention.identifiant.emetteur            ┆ 000000000001 │
│ 00001.xml ┆ intervention.debut.date                      ┆ 2024-01-01   │
│ 00001.xml ┆ intervention.debut.heure                     ┆ 08:10:00     │
│ 00001.xml ┆ intervention.fin.date                        ┆ 2024-01-01   │
│ 00001.xml ┆ intervention.fin.heure                       ┆ 09:00:00     │
│ 00001.xml ┆ intervention.uniteFonctionnelle.code         ┆ 4321         │
│ 00001.xml ┆ intervention.demande.datePrescription.date   ┆ 2023-12-25   │
│ 00001.xml ┆ intervention.demande.datePrescription.heure  ┆ 02:30:00     │
│ 00001.xml ┆ intervention.demande.uniteFonctionnelle.code ┆ 4321         │
└───────────┴──────────────────────────────────────────────┴──────────────┘
```


