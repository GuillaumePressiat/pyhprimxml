# Écrire et lire un dictionnaire

Sous les couches tabulaires, deux fonctions génériques fonctionnent pour **tout message
HPRIM XML**, sans code spécifique : `parse_xml` lit un message en dictionnaire, `to_xml`
l'écrit. C'est la voie à utiliser pour un message ou un élément que les tables ne couvrent
pas encore.

```python
import pyhprimxml as hx

msg = hx.parse_xml("data/xml_tests/actes/00001.xml")
evt = msg["evenementsServeurActes"]["evenementServeurActe"][0]
evt["actesCCAM"]["acteCCAM"][0]["codeActe"]           # 'EBLA003'

hx.write_xml(msg, "copie.xml", xmlns=None)
```

## Format du dictionnaire

C'est le format de xmltodict.

- Le dictionnaire a une seule clé : l'élément racine.
- Attributs et éléments enfants sont des clés du même dictionnaire ; le préfixe `@` est
  accepté mais facultatif, c'est le XSD qui tranche.
- Un élément répété est une liste.
- Un élément à contenu simple portant des attributs utilise la clé `#text`.
- L'ordre des clés n'a pas d'importance : les enfants sont émis dans l'ordre du XSD.

Un dictionnaire produit par `xmltodict.parse` est donc accepté tel quel par `to_xml`.

## `parse_xml`

Par rapport à xmltodict, `parse_xml` s'appuie sur le XSD : les éléments répétables sont
toujours des listes, et les valeurs sont typées (`date`, `datetime`, `time`, `int`).
`typed=False` garde tout en texte. Le namespace est ignoré.

## `to_xml` et `write_xml`

Options propres au dictionnaire, en plus de `xmlns`, `version`, `encoding` et `validate_xsd` :

| option | défaut | effet |
|---|---|---|
| `drop_empty` | `True` | supprime éléments et attributs vides, sauf les éléments complexes obligatoires |
| `strict` | `True` | une clé inconnue du XSD lève une erreur (sinon : avertissement) |
| `pretty` | `True` | indentation par tabulations |

Avec `drop_empty=False`, l'aller-retour `parse_xml` → `to_xml` reproduit les fichiers
d'exemple à l'identique, éléments vides compris.

La déclaration XML est écrite avec des guillemets doubles
(`<?xml version="1.0" encoding="UTF-8" standalone="yes"?>`), comme dans les fichiers
produits par les DPI.
