# pyhprimxml

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

<br>

### Contexte / exemple de fichiers

Le contenu des fichiers nous intéresse. Leur lecture n'est pas des plus aisée puisque le contenu est très hiérarchique, voire dynamique en fonction de la prise en charge du patient.