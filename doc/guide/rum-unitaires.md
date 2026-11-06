# RUM unitaires et dépôts `.ok`

## Un fichier par RUM

Par défaut, un message `evenementsPMSI` porte un séjour : un RSS avec tous ses RUM.
`par_rum=True` écrit plutôt un message par RUM.

```python
hx.write_evenements_pmsi(
    evenements, rum, diagnostics, actes,
    entete={"emetteur": "DIM", "destinataire": "DPI"},
    out_dir="sortie/",
    par_rum=True,
)
# sortie/S001_1.xml, sortie/S001_2.xml
```

Chaque fichier reprend le patient, la venue et l'`identifiantRSS` du séjour, avec un seul
RUM, ses diagnostics et ses actes.

L'intérêt est la logique événementielle : un rejet porte sur un seul RUM, qu'on corrige
et renvoie seul. L'attribut `action` du RUM (colonne `action` : `creation`, `modification`,
`suppression`) indique au récepteur ce qu'il doit faire.

## Nom de fichier et identifiant de message

En mode RUM unitaire, `evt_id` vaut `{evt_id}_{rum_id}` : c'est le nom de fichier par défaut,
et donc l'`identifiantMessage`. Le gabarit `filename` dispose de toutes les colonnes de
`evenements`, plus `rss_id` (l'`evt_id` du séjour) et `rum_id` :

```python
hx.write_evenements_pmsi(..., par_rum=True, filename="R{rss_id}_{rum_id}.xml")
```

L'identifiant du message étant le nom du fichier sans extension, ce nom doit faire 12
caractères au plus. Pour fixer un identifiant par RUM, mettre une colonne
`identifiant_message` dans la table `rum` et s'en servir pour nommer les fichiers :
`filename="{identifiant_message}.xml"`.

## Relecture

À la relecture, chaque fichier redonne un événement à un seul RUM (`rum_id` = 1).
Le séjour se retrouve par `rss_emetteur` ou `nda`.

## Dépôt complet : les fichiers `.ok`

L'émetteur dépose d'abord le `.xml`, puis, une fois celui-ci écrit intégralement, un fichier
`.ok` vide de même nom. Le destinataire ne traite un `.xml` qu'une fois son `.ok` présent :
il ne lit jamais un fichier en cours de copie.

Avec `fichier_ok=True`, les fonctions d'écriture appliquent ce protocole :

```python
hx.write_evenements_pmsi(..., out_dir="depot/", par_rum=True, fichier_ok=True)
# depot/S240001_1.xml, depot/S240001_1.ok, depot/S240001_2.xml, depot/S240001_2.ok
```

Pour chaque fichier :

1. un `.ok` déjà présent (renvoi d'un message) est supprimé d'abord : pendant le
   remplacement, le fichier n'est jamais signalé comme complet ;
2. le `.xml` est écrit sous un nom temporaire caché (`.S240001_1.xml.tmp`), puis renommé :
   il n'apparaît sous son nom définitif qu'une fois complet ;
3. le `.ok` vide est créé en dernier.

L'écriture atomique (étapes 2) s'applique toujours, même sans `fichier_ok`. Un message qui
échoue à la validation XSD n'est pas déposé du tout : ni `.xml`, ni `.ok`.

## Côté destinataire : ne lire que les dépôts terminés

```python
t = hx.read_evenements_pmsi("depot/", exiger_ok=True)
```

Les `.xml` sans `.ok` sont ignorés, avec un avertissement qui en donne le nombre.

## État des dépôts : `suivi_depots`

`suivi_depots` liste les `.xml` d'un dossier et indique lesquels ont leur `.ok` :

```python
suivi = hx.suivi_depots("depot/")
```

| evt_id | fichier | date_xml | complet | date_ok |
|---|---|---|---|---|
| S240001_1 | depot/S240001_1.xml | 2024-03-10 08:00:01 | true | 2024-03-10 08:00:01 |
| S240001_2 | depot/S240001_2.xml | 2024-03-10 08:00:01 | false | |

Les dates sont les dates de modification des fichiers. Un `.ok` sans `.xml` correspondant
est listé avec `fichier` nul. Côté émetteur, la table vérifie que tout a été déposé ;
côté destinataire, elle indique ce qui est prêt à être traité.

`evt_id` est la même clé que celle des tables de lecture, ce qui permet par exemple de
retrouver les RUM dont le dépôt n'est pas terminé :

```python
import polars as pl

rum = hx.read_evenements_pmsi("depot/")["rum"]
incomplets = rum.join(suivi.filter(~pl.col("complet")), on="evt_id")
```
