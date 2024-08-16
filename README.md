# pyhprimxml

**"Projet en cours de développement"**

**À ce stade sans garantie, ce code n'engage que celui qui l'utilise.**

Ce projet a également une visée documentaire / bloc-notes. Enfin il ne cherche pas à répondre à un besoin particulier mais propose des pistes pour exploiter ces données dans diverses contextes en les dénaturant le moins possible.

## Lecture de fichiers hprimXML avec python


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

Deux exemples sont réalisés autour des fichiers hprimXML utilisant xpath :

- le [premier](https://guillaumepressiat.github.io/pyhprimxml/xpath_xml.html) utilise le package python xml en spécifiant le namespace xmlns d'hprim au travers d'un alias dans les définitions de xpath.
- le [deuxième](https://guillaumepressiat.github.io/pyhprimxml/xpath_lxml.html) utilise le package python lxml en supprimant le namespace xmlns avant d'utiliser xpath.


### Récupération des éléments XML complets


L'utilisation du package [pyhprimxml](https://guillaumepressiat.github.io/pyhprimxml/) dans le contexte de la lecture de fichiers hprimXML (v1.07 et v2 testés) est présentée [ici](https://guillaumepressiat.github.io/pyhprimxml/).

Ainsi, on récupère les tables et les liens hiérarchiques entre les éléments du XML (parents/enfants).


