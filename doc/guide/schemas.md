# Schémas XSD et validation

## Versions embarquées

Les XSD officiels d'Interop'Santé sont embarqués dans `pyhprimxml/schemas/`, pour les
versions 1.03a, 1.04, 1.05, 1.06, 1.07, 2.00, 2.1, 2.2, 2.3 et 2.4.

```python
hx.available_versions()
# ['1.03a', '1.04', '1.05', '1.06', '1.07', '2.00', '2.1', '2.2', '2.3', '2.4']
```

La version utilisée est celle de l'attribut `version` du message. Chaque XSD n'accepte
que sa propre version : un message `version="2.00"` est validé avec les schémas 2.00.

Chaque version existe en deux variantes : `ns/`, le XSD d'origine avec le namespace
`http://www.hprim.org/hprimXML`, et `nons/`, le même sans `targetNamespace`, utilisé pour
valider les messages sans namespace.

## Régénérer les schémas

Le script `tools/vendor_schemas.py` extrait les schémas de l'archive de spécification
publiée par Interop'Santé :

```bash
python tools/vendor_schemas.py hprimXmlVs2_4.zip
```

Il normalise les fichiers en UTF-8 avec des fins de ligne LF (les versions anciennes
peuvent être en cp1252) et produit les deux variantes.

## Valider un message

```python
erreurs = hx.validate(open("message.xml", "rb").read())
# [] si conforme, sinon : ["ligne 15 : Element 'agent': Missing child element(s)...", ...]
```

La variante de schéma (avec ou sans namespace) est choisie d'après le message lui-même.

## Fichiers réels et conformité

Les fichiers produits par les logiciels ne sont pas toujours conformes au XSD. Les
fichiers d'exemple contiennent par exemple :

- `<seance></seance>` vide, alors que `seance` est un entier positif ;
- `<radiotherapie nombreFaisceau="" typeDosimetrie="" typeMachine=""/>`, avec des
  attributs vides hors énumération ;
- un agent destinataire sans `code`, qui est obligatoire.

D'où deux choix du package : à l'écriture, les éléments et attributs vides sont supprimés
par défaut ; à la lecture, aucune validation n'est imposée, et une valeur non conforme
à son type est conservée telle quelle en texte.
