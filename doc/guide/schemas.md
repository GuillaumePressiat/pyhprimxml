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

## Anciennes versions

Les dix versions embarquées (1.03a à 2.4) s'écrivent et se lisent avec les mêmes fonctions,
via l'argument `version`. Quelques particularités :

- **Valeurs énumérées et accents.** Les versions 1.0x n'admettent que `création` (accentué),
  les versions 2.x acceptent aussi `creation`. À l'écriture, une valeur absente de
  l'énumération du XSD est remplacée par la forme du XSD quand une seule valeur autorisée lui
  correspond aux accents près : `creation` devient `création` en 1.0x, et `réel`, lu dans un
  vieux fichier, devient `reel` dans une version qui n'admet que cette forme.
- **Champs propres à une version.** Certains champs sont obligatoires dans certaines versions
  seulement (nom usuel et prénom en PMSI 1.0x, `venue/@projetTherapeutique` et
  `divers/@litDedie` en états patient 2.1 à 2.3), d'autres n'existent pas encore dans les
  anciennes (`medecinResponsable/noRPPS` en 1.03a). La validation et le mode strict le
  signalent ; une colonne facultative laissée vide n'est jamais un obstacle.
- **XSD PMSI 1.06.** Le XSD officiel PMSI de la version 1.06 est lui-même invalide : il ne
  peut pas être compilé. Les fichiers 1.06 se lisent normalement, mais leur validation est
  impossible (`HprimSchemaError`) : pour écrire en 1.06, passer `validate_xsd=False`.

### Fichiers d'une version sans XSD

Un fichier qui déclare une version absente (1.0, par exemple) se lit avec le XSD d'une version
proche, en forçant `version` :

```python
x = open("message_v1.xml", "rb").read()
for v in hx.available_versions():            # quelle version est la plus proche ?
    try:
        erreurs = [e for e in hx.validate(x, version=v) if "'version'" not in e]
        print(v, len(erreurs), erreurs[:3])
    except hx.HprimSchemaError:
        print(v, "XSD officiel invalide")

t = hx.read_evenements_pmsi("message_v1.xml", version="1.03a")   # lecture
```

Les tables relues se réécrivent ensuite dans une autre version (`version="2.00"`), avec
validation : c'est une façon de convertir des fichiers anciens. Pour une conversion
exhaustive, passer par le dictionnaire (`parse_xml(f, version=...)` puis `to_xml(...,
version="2.00")`) : le mode strict signale chaque élément qui n'existe plus dans la version
cible. Des feuilles XSL de montée de version (serveur d'actes, 1.03a et suivantes) sont aussi
publiées par Frédéric Laurent : <https://github.com/flrt/hprimxml>.
