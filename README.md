# pyhprimxml


<!-- fragment:presentation -->
Écriture et lecture de fichiers [HPRIM XML](https://www.interopsante.org/hprim), standard
d'interopérabilité français, depuis et vers des DataFrames **polars** ou **pandas**, guidées
par les schémas XSD officiels (versions 1.03a à 2.4, embarqués dans le package).

> **Projet en cours de développement.** À ce stade sans garantie : ce code n'engage que
> celui qui l'utilise.

| Message | Écriture | Lecture |
|---|---|---|
| `evenementsPMSI` (RSS MCO) | `write_evenements_pmsi` | `read_evenements_pmsi` |
| `evenementsServeurActes` (actes CCAM) | `write_evenements_serveur_actes` | `read_evenements_serveur_actes` |
| `evenementsServeurEtatsPatient` (diagnostics) | `write_evenements_etat_patient` | `read_evenements_etat_patient` |
| Tout message HPRIM XML, sous forme de dictionnaire | `to_xml`, `write_xml` | `parse_xml` |

Et aussi : `validate` (contrôle d'un message contre son XSD) et `suivi_depots` (état des
dépôts : quels `.xml` ont leur marqueur `.ok`).

Ce que permet le package :

- **un fichier par séjour, ou par RUM** (`par_rum=True`), pour traiter, corriger et renvoyer
  chaque RUM séparément ;
- **dépôt sécurisé** : chaque `.xml` est écrit de façon atomique, et un marqueur `.ok` vide est
  déposé une fois le fichier complet (`fichier_ok=True`) ; à la lecture, `exiger_ok=True` ignore
  les dépôts inachevés ;
- **identifiant du message = nom du fichier**, règle contrôlée à l'écriture ;
- **diagnostics** au choix en format long (une ligne par code), en liste ou en chaîne
  séparée par des virgules ;
- **namespace** HPRIM, absent (`xmlns=None`) ou vide (`xmlns=""`), et encodage UTF-8 ou
  ISO-8859-1 ;
- **validation XSD** de chaque fichier écrit, en mode erreur par défaut ;
- **colonnes-chemins** (`patient/@anonyme`, `medecinResponsable/noRPPS`…) pour atteindre
  n'importe quel élément du XSD ;
- **relecture** vers les mêmes tables, avec des colonnes typées (dates, heures, entiers).

Un portage R, `hprimxml`, couvre la couche de base (liste R ↔ XML) et produit des fichiers
identiques octet pour octet.

## Installation

```bash
pip install git+https://github.com/GuillaumePressiat/pyhprimxml
```

Dépendances : `polars`, `lxml`, `xmltodict`. Pour utiliser des DataFrames pandas,
installer aussi `pandas` et `pyarrow`.
<!-- /fragment:presentation -->

## Sommaire

1. [Écriture : des tables vers HPRIM XML](#1-écriture--des-tables-vers-hprim-xml)
2. [Lecture : des fichiers HPRIM XML vers les tables](#2-lecture--des-fichiers-hprim-xml-vers-les-tables)
3. [Autres façons de lire : xpath et structs polars](#3-autres-façons-de-lire--xpath-et-structs-polars)
4. [Documentation](#documentation)

## 1. Écriture : des tables vers HPRIM XML

L'écriture s'appuie sur les XSD officiels (versions 1.03a à 2.4, vendorisés dans
`pyhprimxml/schemas/`, voir `tools/vendor_schemas.py`). Le XSD fournit l'ordre des
éléments, la distinction attribut / élément, les éléments obligatoires et le format
des dates. Il sert aussi à valider chaque fichier produit.

### Exemples complets : DataFrames polars → les 3 fichiers HPRIM XML

Les trois blocs ci-dessous sont complets et exécutables tels quels. Ils régénèrent les trois
fichiers d'exemple de `data/xml_tests` : un message PMSI (RSS à deux RUM), un message serveur
d'actes et un message états patient. Un exemple réaliste (séjour avec mutation, écrit par
séjour puis en RUM unitaires) suit dans la section [Depuis des tables](#depuis-des-tables-evenementspmsi--rss-mco-un-fichier-par-événement).

Tous les exemples écrivent en **version 2.00**, déclarée une fois dans l'en-tête
(`entete = {"version": "2.00", ...}`). Sans précision, le package écrit en 2.4, la dernière
version publiée ; le paramètre `version=` d'un appel l'emporte sur l'en-tête.

Tout le code, les tableaux et les extraits XML de ce README proviennent des scripts
`examples/exemple_*.py` : `python tools/exemples_doc.py` les recopie ici, dans les docstrings
et dans la doc MkDocs, et les tests échouent si l'un d'eux n'est plus à jour.

Deux différences avec les originaux. D'abord, les fichiers produits s'appellent
`00001_pmsi.xml`, `00001_acte.xml` et `00001_esep.xml` : la règle
[identifiant du message = nom du fichier](#règle--identifiant-du-message--nom-du-fichier)
s'applique, alors que les originaux s'appellent tous `00001.xml` mais contiennent ces
identifiants. Ensuite, les éléments vides des originaux (`<seance></seance>`,
`radiotherapie` aux attributs vides), non conformes au XSD, ne sont pas reproduits.
L'agent destinataire sans `code`, lui, est reproduit tel quel ; comme il n'est pas conforme
au XSD, les exemples utilisent `validate_xsd="warn"`. Avec un vrai destinataire, on garderait
la validation par défaut (`"error"`).

#### 1. PMSI : `evenementsPMSI`, un séjour avec deux RUM

Quatre tables : `evenements` (une ligne par séjour), `rum`, `diagnostics` (format long)
et `actes`. Le médecin responsable et les attributs `oui`/`non` passent par des
colonnes-chemins.

<!-- exemple:pmsi -->
```python
# Régénère data/xml_tests/pmsi/00001.xml : un séjour (RSS) à deux RUM.
from datetime import date, datetime, time

import polars as pl

import pyhprimxml as hx

# En-tête du message (chaque clé peut aussi être une colonne de `evenements`)
entete = {
    "version": "2.00",                   # version HPRIM XML des messages
    "emetteur": "TEST",
    "destinataire": None,            # agent destinataire sans code, comme le fichier d'origine
    "mode_traitement": "reel",
    "acquittement_attendu": "oui",
    "commentaire": "HPRIM-TEST",
    "date_heure_production": datetime(2024, 1, 1, 1, 1, 1),
}

# Une ligne par séjour, donc par fichier : patient, venue, identifiant du RSS
evenements = pl.DataFrame({
    "evt_id": ["00001_pmsi"],    # -> fichier 00001_pmsi.xml, identifiantMessage 00001_pmsi
    "ipp": ["123456789"], "ipp_recepteur": ["123456789"],
    "sexe": ["M"], "nom_usuel": ["SANDWICK"], "nom_naissance": ["SANDWICK"], "prenom": ["JOHN"],
    "date_naissance": [date(1970, 1, 1)],
    "nda": ["987654321"], "nda_recepteur": ["987654321"],
    "venue_date_entree": [date(2024, 1, 1)], "venue_heure_entree": [time(8, 0)],
    "venue_mode_entree": ["8"], "venue_uf_responsable": ["4321"],
    "rss_emetteur": ["0"], "rss_recepteur": ["000"],
    # colonnes-chemins : attributs sans colonne dédiée
    "patient/@anonyme": ["non"], "patient/@confidentiel": ["non"], "venue/@prive": ["non"],
})

# Une ligne par RUM ; rum_id = rang du RUM dans le RSS (clé de jointure)
rum = pl.DataFrame({
    "evt_id": ["00001_pmsi", "00001_pmsi"],
    "rum_id": [1, 2],
    "rum_emetteur": ["pmsi_00001", "pmsi_00001"],     # identifiant XML du RUM
    "rum_recepteur": ["98765", "98766"],
    "date_action": [datetime(2024, 1, 1, 8, 10), datetime(2024, 1, 1, 9, 0)],
    "um": ["4321", "5000"],
    "um_date_entree": [date(2024, 1, 1)] * 2,
    "um_heure_entree": [time(8, 0), time(9, 0)],
    "um_mode_entree": ["8", "8"],
    "@classant": ["non", "non"],
    "@prestationInterEtablissementA": ["non", "non"],
    "medecinResponsable/identification/code": ["01234567"] * 2,
    "medecinResponsable/personne/nomUsuel": ["HOBBES"] * 2,
    "medecinResponsable/personne/prenoms/prenom": ["MARC-JACQUES"] * 2,
})

# Format long : une ligne par diagnostic, type dans DP, DR, DAS, DAD
diagnostics = pl.DataFrame({
    "evt_id": ["00001_pmsi"] * 3,
    "rum_id": [1, 1, 2],
    "type": ["DP", "DR", "DP"],
    "code": ["Z511", "C10", "Z743"],
})

# Une ligne par acte CCAM
actes = pl.DataFrame({
    "evt_id": ["00001_pmsi"] * 5,
    "rum_id": [1, 1, 1, 1, 2],
    "code": ["EBLA003", "EPLF002", "NFKA006", "YYYY033", "QZRP004"],
    "phase": [0] * 5, "activite": [1] * 5, "quantite": [1] * 5,
    "date_realisation": [datetime(2024, 1, 1, 8, 10)] * 4 + [datetime(2024, 1, 1, 9, 10)],
    "externe": ["non"] * 5, "remboursement_exceptionnel": ["non"] * 5,
})

fichiers = hx.write_evenements_pmsi(
    evenements, rum, diagnostics, actes,
    entete=entete,
    out_dir="sortie/pmsi",           # -> sortie/pmsi/00001_pmsi.xml
    validate_xsd="warn",             # destinataire sans code : non conforme au XSD
)
```
<!-- /exemple:pmsi -->

#### 2. Serveur d'actes : `evenementsServeurActes`, une intervention et quatre actes CCAM

Deux tables : `evenements` (patient, venue, intervention, demande) et `actes`.

<!-- exemple:actes -->
```python
# Régénère data/xml_tests/actes/00001.xml : une intervention et quatre actes CCAM.
from datetime import date, datetime, time

import polars as pl

import pyhprimxml as hx

entete = {
    "version": "2.00",                   # version HPRIM XML des messages
    "emetteur": "TEST",
    "destinataire": None,
    "acquittement_attendu": "oui",
    "commentaire": "HPRIM-TEST",
    "date_heure_production": datetime(2024, 1, 1, 1, 1, 1),
}

# Une ligne par événement : patient, venue, intervention et demande
evenements = pl.DataFrame({
    "evt_id": ["00001_acte"],
    "ipp": ["123456789"], "ipp_recepteur": ["123456789"],
    "sexe": ["M"], "nom_usuel": ["SANDWICK"], "prenom": ["JOHN"],
    "date_naissance": [date(1970, 1, 1)],
    "nda": ["987654321"], "nda_recepteur": ["987654321"],
    "venue_date_entree": [date(2024, 1, 1)], "venue_heure_entree": [time(8, 0)],
    "venue_uf_responsable": ["4321"],
    "venue/@prive": ["non"],
    "intervention_id": ["000000000001"],
    "intervention_date_debut": [date(2024, 1, 1)], "intervention_heure_debut": [time(8, 10)],
    "intervention_date_fin": [date(2024, 1, 1)], "intervention_heure_fin": [time(9, 0)],
    "intervention_uf": ["4321"],
    "demande_date": [date(2023, 12, 25)], "demande_heure": [time(2, 30)], "demande_uf": ["4321"],
})

# Une ligne par acte CCAM
actes = pl.DataFrame({
    "evt_id": ["00001_acte"] * 4,
    "acte_id": ["121212", "121213", "121214", "121215"],
    "code": ["EBLA003", "YYYY033", "EPLF002", "NFKA006"],
    "activite": [1] * 4, "phase": [0] * 4,
    "date_execution": [date(2024, 1, 1)] * 4, "heure_execution": [time(8, 10)] * 4,
    "medecin": ["01234567"] * 4, "uf": ["4321"] * 4,
    "quantite": ["1"] * 4,           # nombre5 : chaîne de chiffres dans le XSD
    "facturable": ["oui"] * 4, "valide": ["oui"] * 4,
})

fichiers = hx.write_evenements_serveur_actes(
    evenements, actes,
    entete=entete,
    out_dir="sortie/actes",          # -> sortie/actes/00001_acte.xml
    validate_xsd="warn",
)
```
<!-- /exemple:actes -->

#### 3. États patient : `evenementsServeurEtatsPatient`, DP et DR

Deux tables : `evenements` et `diagnostics`.

<!-- exemple:etat_patient -->
```python
# Régénère data/xml_tests/etat_patient/00001.xml : diagnostics DP et DR.
from datetime import date, datetime, time

import polars as pl

import pyhprimxml as hx

entete = {
    "version": "2.00",                   # version HPRIM XML des messages
    "emetteur": "TEST",
    "destinataire": None,
    "acquittement_attendu": "non",
    "commentaire": "HPRIM-TEST",
    "date_heure_production": datetime(2024, 1, 1, 1, 1, 1),
}

# Une ligne par événement : patient, venue, intervention
# (ici, les colonnes-chemins sont relatives à la racine du message)
evenements = pl.DataFrame({
    "evt_id": ["00001_esep"],
    "ipp": ["123456789"], "ipp_recepteur": ["123456789"],
    "sexe": ["M"], "nom_usuel": ["SANDWICK"], "prenom": ["JOHN"],
    "date_naissance": [date(1970, 1, 1)],
    "nda": ["987654321"], "nda_recepteur": ["987654321"],
    "venue_date_entree": [date(2024, 1, 1)], "venue_heure_entree": [time(8, 0)],
    "venue_uf_responsable": ["4321"],
    "intervention_id": ["000000000001"], "intervention_uf": ["4321"],
    "patient/@confidentiel": ["non"], "venue/@prive": ["non"],
    "patient/identifiant/emetteur/@etat": ["permanent"],
    "patient/identifiant/emetteur/@portee": ["local"],
    "patient/identifiant/emetteur/@referent": ["non"],
    "patient/identifiant/recepteur/@etat": ["permanent"],
    "patient/identifiant/recepteur/@portee": ["local"],
    "patient/identifiant/recepteur/@referent": ["non"],
})

# Une ligne par diagnostic ; type dans dp, dr, da, ds, dd, fpc, mm, ae
diagnostics = pl.DataFrame({
    "evt_id": ["00001_esep", "00001_esep"],
    "type": ["dp", "dr"],
    "code": ["Z511", "C10"],
    "date_action": [datetime(2024, 1, 1, 8, 10)] * 2,
})

fichiers = hx.write_evenements_etat_patient(
    evenements, diagnostics,
    entete=entete,
    out_dir="sortie/etat_patient",   # -> sortie/etat_patient/00001_esep.xml
    validate_xsd="warn",
)
```
<!-- /exemple:etat_patient -->

Les mêmes exemples existent sous forme de scripts dans `examples/` (par exemple
`python examples/exemple_pmsi.py`), et figurent dans les docstrings des fonctions
`write_evenements_*` (`help(hx.write_evenements_pmsi)`).

### Depuis des tables (evenementsPMSI / RSS MCO, un fichier par événement)

Quatre tables, en polars ou pandas, reliées par `evt_id` (le séjour, donc le fichier)
et `rum_id` (le RUM, dans l'ordre du RSS). Exemple : une patiente entre par les urgences en
cardiologie (UM 1201), est mutée en médecine (UM 3405), puis rentre à domicile. C'est un RSS
de deux RUM, avec de vrais codes CIM-10 et CCAM.

Les tableaux ci-dessous sont générés à partir des DataFrames du script
`examples/exemple_sejour.py`, donné en entier plus bas : ils ne peuvent pas diverger du code.

**`evenements`** : une ligne par séjour, donc par fichier.

<!-- tables:sejour:evenements -->
| evt_id | ipp | sexe | date_naissance | nda | venue_date_entree | venue_heure_entree | venue_date_sortie | rss_emetteur |
|---|---|---|---|---|---|---|---|---|
| S240001 | 190101337 | F | 1958-03-12 | 240000123 | 2024-03-04 | 10:20 | 2024-03-09 | 240000123 |
<!-- /tables:sejour:evenements -->

**`rum`** : une ligne par RUM. `rum_id` est la clé de jointure ; `rum_emetteur` est
l'identifiant XML du RUM. La colonne `medecinResponsable/noRPPS` est une
[colonne-chemin](#colonnes-chemins--atteindre-nimporte-quel-élément-du-xsd).

<!-- tables:sejour:rum -->
| evt_id | rum_id | rum_emetteur | um | um_date_entree | um_heure_entree | um_mode_entree | um_provenance | um_date_sortie | um_mode_sortie | um_destination | `medecinResponsable/noRPPS` |
|---|---|---|---|---|---|---|---|---|---|---|---|
| S240001 | 1 | S240001_1 | 1201 | 2024-03-04 | 10:20 | 8 | 5 | 2024-03-06 | 6 | 1 | 10003456789 |
| S240001 | 2 | S240001_2 | 3405 | 2024-03-06 | 14:00 | 6 | 1 | 2024-03-09 | 8 |  | 10009876543 |
<!-- /tables:sejour:rum -->

**`diagnostics`** : format long, une ligne par code. `type` vaut `DP`, `DR`, `DAS` ou `DAD`.
Le point des codes CIM-10 est retiré à l'écriture (`I21.0` devient `I210`).

<!-- tables:sejour:diagnostics -->
| evt_id | rum_id | type | code |
|---|---|---|---|
| S240001 | 1 | DP | I21.0 |
| S240001 | 1 | DAS | E11.9 |
| S240001 | 1 | DAS | I10 |
| S240001 | 1 | DAS | E78.0 |
| S240001 | 2 | DP | I50.1 |
| S240001 | 2 | DAS | N18.3 |
| S240001 | 2 | DAS | E11.9 |
<!-- /tables:sejour:diagnostics -->

**`actes`** : une ligne par acte CCAM. `quantite` vaut 1 par défaut ; `modificateurs` est une
chaîne, un caractère par modificateur (par exemple `"7J"`).

<!-- tables:sejour:actes -->
| evt_id | rum_id | code | phase | activite | date_realisation |
|---|---|---|---|---|---|
| S240001 | 1 | DEQP003 | 0 | 1 | 2024-03-04 10:45 |
| S240001 | 1 | ZBQK002 | 0 | 1 | 2024-03-04 11:30 |
| S240001 | 2 | DEQP003 | 0 | 1 | 2024-03-06 15:00 |
<!-- /tables:sejour:actes -->

Le script complet construit ces tables et écrit le séjour deux fois : en un fichier par séjour
(`S240001.xml`), puis en RUM unitaires (`S240001_1.xml`, `S240001_2.xml`). Les fichiers sont
écrits sans namespace, en version 2.00, et validés contre le XSD correspondant.

<!-- exemple:sejour -->
```python
# Séjour avec mutation : entrée par les urgences en cardiologie (UM 1201), puis mutation
# en médecine (UM 3405), sortie au domicile. Un RSS de deux RUM, écrit sans namespace,
# d'abord en un fichier par séjour, puis en RUM unitaires (un fichier par RUM).
from datetime import date, datetime, time

import polars as pl

import pyhprimxml as hx

entete = {
    "version": "2.00",                   # version HPRIM XML des messages
    "emetteur": "DIM",
    "destinataire": "DPI",
    "date_heure_production": datetime(2024, 3, 10, 8, 0),   # par défaut : maintenant
}

# Une ligne par séjour
evenements = pl.DataFrame({
    "evt_id": ["S240001"],              # -> S240001.xml, identifiantMessage S240001
    "ipp": ["190101337"],
    "sexe": ["F"],
    "date_naissance": [date(1958, 3, 12)],
    "nda": ["240000123"],
    "venue_date_entree": [date(2024, 3, 4)],
    "venue_heure_entree": [time(10, 20)],
    "venue_date_sortie": [date(2024, 3, 9)],
    "rss_emetteur": ["240000123"],
})

# Une ligne par RUM
rum = pl.DataFrame({
    "evt_id": ["S240001", "S240001"],
    "rum_id": [1, 2],
    "rum_emetteur": ["S240001_1", "S240001_2"],   # identifiant XML du RUM
    "um": ["1201", "3405"],
    "um_date_entree": [date(2024, 3, 4), date(2024, 3, 6)],
    "um_heure_entree": [time(10, 20), time(14, 0)],
    "um_mode_entree": ["8", "6"],       # domicile, puis mutation
    "um_provenance": ["5", "1"],        # urgences, puis MCO
    "um_date_sortie": [date(2024, 3, 6), date(2024, 3, 9)],
    "um_mode_sortie": ["6", "8"],       # mutation, puis domicile
    "um_destination": ["1", None],      # vers MCO
    "medecinResponsable/noRPPS": ["10003456789", "10009876543"],
})

# Une ligne par diagnostic (le point des codes CIM-10 est retiré à l'écriture)
diagnostics = pl.DataFrame({
    "evt_id": ["S240001"] * 7,
    "rum_id": [1, 1, 1, 1, 2, 2, 2],
    "type": ["DP", "DAS", "DAS", "DAS", "DP", "DAS", "DAS"],
    "code": ["I21.0", "E11.9", "I10", "E78.0", "I50.1", "N18.3", "E11.9"],
})

# Une ligne par acte CCAM
actes = pl.DataFrame({
    "evt_id": ["S240001"] * 3,
    "rum_id": [1, 1, 2],
    "code": ["DEQP003", "ZBQK002", "DEQP003"],
    "phase": [0, 0, 0],
    "activite": [1, 1, 1],
    "date_realisation": [datetime(2024, 3, 4, 10, 45), datetime(2024, 3, 4, 11, 30),
                         datetime(2024, 3, 6, 15, 0)],
})

# Un fichier par séjour : sortie/sejour/S240001.xml
hx.write_evenements_pmsi(
    evenements, rum, diagnostics, actes,
    entete=entete, out_dir="sortie/sejour", xmlns=None,
)

# RUM unitaires, avec marqueur de dépôt complet :
# sortie/rum/S240001_1.xml puis S240001_1.ok, sortie/rum/S240001_2.xml puis S240001_2.ok
hx.write_evenements_pmsi(
    evenements, rum, diagnostics, actes,
    entete=entete, out_dir="sortie/rum", xmlns=None, par_rum=True, fichier_ok=True,
)

# Relecture : les mêmes tables (ici, diagnostics en colonnes de `rum`)
relu = hx.read_evenements_pmsi("sortie/sejour", format_diagnostics="colonnes")
rum_relu = relu["rum"].select("evt_id", "rum_id", "rum_emetteur", "um", "dp", "das")
```
<!-- /exemple:sejour -->

#### Diagnostics : format long, liste ou chaîne

Les diagnostics d'un RUM se donnent au choix sous trois formes, qui produisent exactement le
même fichier XML (script `examples/exemple_diagnostics.py`, un RUM avec un DP et quatre DAS).

**1. Format long**, table `diagnostics` : une ligne par code.

<!-- tables:diagnostics:diagnostics -->
| evt_id | rum_id | type | code |
|---|---|---|---|
| S240002 | 1 | DP | I21.0 |
| S240002 | 1 | DAS | E11.9 |
| S240002 | 1 | DAS | I10 |
| S240002 | 1 | DAS | E78.0 |
| S240002 | 1 | DAS | N18.3 |
<!-- /tables:diagnostics:diagnostics -->

**2. Colonnes dans `rum`, DAS en liste** (type `List` de polars).

<!-- tables:diagnostics:rum_liste -->
| evt_id | rum_id | um | um_date_entree | um_mode_entree | dp | das |
|---|---|---|---|---|---|---|
| S240002 | 1 | 1201 | 2024-03-04 | 8 | I21.0 | [E11.9, I10, E78.0, N18.3] |
<!-- /tables:diagnostics:rum_liste -->

**3. Colonnes dans `rum`, DAS en chaîne séparée par des virgules** (les espaces sont ignorés).

<!-- tables:diagnostics:rum_chaine -->
| evt_id | rum_id | um | um_date_entree | um_mode_entree | dp | das |
|---|---|---|---|---|---|---|
| S240002 | 1 | 1201 | 2024-03-04 | 8 | I21.0 | "E11.9, I10, E78.0, N18.3" |
<!-- /tables:diagnostics:rum_chaine -->

Les colonnes de `rum` sont `dp` et `dr` (un code) et `das` et `dad` (liste ou chaîne). Les deux
approches se combinent, par exemple DP et DR en colonnes et DAS en format long, à condition de
ne pas donner deux fois le DP ou le DR d'un même RUM. À la relecture,
`format_diagnostics="colonnes"` renvoie la forme 2 ; par défaut, c'est le format long.

Le code complet :

<!-- exemple:diagnostics -->
```python
# Trois façons équivalentes de fournir les diagnostics d'un RUM avec plusieurs DAS.
# Les trois écritures produisent exactement le même fichier XML.
from datetime import date, datetime
from pathlib import Path

import polars as pl

import pyhprimxml as hx

entete = {
    "version": "2.00",                   # version HPRIM XML des messages
    "emetteur": "DIM",
    "destinataire": "DPI",
    "date_heure_production": datetime(2024, 3, 10, 8, 0),
}

evenements = pl.DataFrame({
    "evt_id": ["S240002"], "ipp": ["190101338"], "sexe": ["M"],
    "date_naissance": [date(1951, 7, 2)], "nda": ["240000124"],
    "venue_date_entree": [date(2024, 3, 4)], "rss_emetteur": ["240000124"],
})

rum = pl.DataFrame({
    "evt_id": ["S240002"], "rum_id": [1], "um": ["1201"],
    "um_date_entree": [date(2024, 3, 4)], "um_mode_entree": ["8"],
})

# 1. Format long : une table `diagnostics`, une ligne par code
diagnostics = pl.DataFrame({
    "evt_id": ["S240002"] * 5,
    "rum_id": [1] * 5,
    "type": ["DP", "DAS", "DAS", "DAS", "DAS"],
    "code": ["I21.0", "E11.9", "I10", "E78.0", "N18.3"],
})
hx.write_evenements_pmsi(evenements, rum, diagnostics, entete=entete, out_dir="sortie/long")

# 2. Colonnes dans `rum`, DAS en liste (type List de polars)
rum_liste = rum.with_columns(
    dp=pl.lit("I21.0"),
    das=pl.lit(["E11.9", "I10", "E78.0", "N18.3"]),
)
hx.write_evenements_pmsi(evenements, rum_liste, entete=entete, out_dir="sortie/liste")

# 3. Colonnes dans `rum`, DAS en chaîne séparée par des virgules
rum_chaine = rum.with_columns(
    dp=pl.lit("I21.0"),
    das=pl.lit("E11.9, I10, E78.0, N18.3"),
)
hx.write_evenements_pmsi(evenements, rum_chaine, entete=entete, out_dir="sortie/chaine")

# Une chaîne se convertit aussi en liste d'une ligne : pl.col("das").str.split(", ")
fichiers = {f: Path("sortie", f, "S240002.xml").read_bytes() for f in ("long", "liste", "chaine")}
assert fichiers["long"] == fichiers["liste"] == fichiers["chaine"]
```
<!-- /exemple:diagnostics -->

### RUM unitaires : un fichier par RUM

`par_rum=True` écrit un message par RUM au lieu d'un message par séjour. Chaque fichier
reprend le patient, la venue et l'`identifiantRSS` du séjour, avec un seul RUM, ses
diagnostics et ses actes. Un rejet porte alors sur un seul RUM, qu'on corrige et renvoie
seul ; l'attribut `action` du RUM (`creation`, `modification`, `suppression`) porte la
logique événementielle.

```python
hx.write_evenements_pmsi(
    evenements, rum, diagnostics, actes,
    entete={"emetteur": "DIM", "destinataire": "DPI"},
    out_dir="sortie/",
    par_rum=True,
    filename="{rss_id}_{rum_id}.xml",   # défaut : "{evt_id}.xml", avec evt_id = "{evt_id}_{rum_id}"
)
# sortie/S001_1.xml, sortie/S001_2.xml
```

Le gabarit `filename` dispose de toutes les colonnes de `evenements`, plus `rss_id` (l'`evt_id`
du séjour) et `rum_id`. Le nom de fichier sert de clé (le marqueur `.ok` porte le même nom) :
il doit désigner le RUM sans ambiguïté.

#### Règle : identifiant du message = nom du fichier

L'identifiant du message est **exactement le nom du fichier sans extension**. Par défaut, le
fichier s'appelle `{evt_id}.xml` (`{evt_id}_{rum_id}.xml` avec `par_rum=True`), et
l'`identifiantMessage` vaut donc `evt_id`. Avec un gabarit `filename` personnalisé, c'est le nom
produit par le gabarit qui sert d'identifiant. C'est ce qui permet de rapprocher un fichier, son
contenu et son marqueur `.ok`.

- Une colonne `identifiant_message` (dans `evenements`, ou dans `rum` avec `par_rum`) n'est
  acceptée que si elle concorde avec le nom de fichier ; sinon l'écriture échoue. Pour nommer
  les fichiers d'après cette colonne : `filename="{identifiant_message}.xml"`.
- Le XSD définit l'identifiant comme `nom12` : 1 à 12 caractères parmi lettres, chiffres, `-`,
  `,` et `_`. La contrainte s'applique donc au nom de fichier sans extension ; un nom trop long
  fait échouer l'écriture avec un message explicite.
- Deux messages qui recevraient le même nom de fichier font échouer l'écriture (pas
  d'écrasement silencieux).
- `identifiant_egal_nom_fichier=False` rend identifiant et nom de fichier indépendants, par
  exemple pour réécrire à l'identique des fichiers d'autres producteurs.

À la relecture, chaque fichier est un événement à un seul RUM (`rum_id` = 1). Le séjour se
retrouve par `rss_emetteur` ou `nda`.

#### Correspondance colonnes → XML

Les valeurs vides (`null`, `NaN`, `""`) sont simplement omises.

| table | colonne | élément / attribut XML | |
|---|---|---|---|
| evenements | `evt_id` | nom du fichier et `enteteMessage/identifiantMessage` (voir la règle ci-dessus) | obligatoire |
| evenements | `ipp` | `patient/identifiant/emetteur/valeur` | obligatoire |
| evenements | `ipp_recepteur` | `patient/identifiant/recepteur/valeur` | |
| evenements | `nda` | `venue/identifiant/emetteur/valeur` | obligatoire |
| evenements | `nda_recepteur` | `venue/identifiant/recepteur/valeur` | |
| evenements | `sexe` | `patient/personnePhysique/@sexe` (M, F, I) | obligatoire |
| evenements | `date_naissance` | `patient/personnePhysique/dateNaissance/date` | obligatoire |
| evenements | `venue_date_entree`, `venue_heure_entree` | `venue/entree/dateHeureOptionnelle` | date obligatoire |
| evenements | `venue_mode_entree`, `venue_uf_responsable` | `venue/entree/modeEntree/code`, `venue/entree/uniteFonctionnelleResponsable/code` | |
| evenements | `venue_date_sortie`, `venue_heure_sortie` | `venue/sortie/dateHeureOptionnelle` | |
| evenements | `nom_usuel`, `nom_naissance`, `prenom` | `patient/personnePhysique/...` | |
| evenements | `rss_emetteur`, `rss_recepteur` | `rss/identifiantRSS/emetteur`, `recepteur` | |
| evenements | `numero_finess`, `commentaire` | `numeroFiness`, `commentaireMessage` | |
| rum | `rum_id` | clé de jointure avec `diagnostics` et `actes` | obligatoire |
| rum | `rum_emetteur`, `rum_recepteur` | `rum/identifiant/emetteur` (défaut : `rum_id`), `recepteur` | |
| rum | `um` | `rum/uniteMedicale/code` | obligatoire |
| rum | `um_date_entree`, `um_heure_entree` | `uniteMedicale/entree/date`, `heure` | date obligatoire |
| rum | `um_mode_entree`, `um_provenance` | `uniteMedicale/entree/@mode`, `@complementMode` | mode obligatoire |
| rum | `um_date_sortie`, `um_heure_sortie` | `uniteMedicale/sortie/date`, `heure` | |
| rum | `um_mode_sortie`, `um_destination` | `uniteMedicale/sortie/@mode`, `@complementMode` | |
| rum | `date_action` | `rum/dateAction` (défaut : `um_date_entree`) | |
| rum | `action` | `rum/@action` (défaut : `creation`) | |
| rum | `rum_recepteur`, `igs2`, `nb_seances`, `rum_version` | `identifiant/recepteur`, `igs2`, `seance`, `rss/@version` | |
| diagnostics | `type`, `code` | `diagnostics/diagnosticPrincipal`, `diagnosticRelie`, `diagnosticsSignificatifs`, `diagnosticsDocumentaires` | obligatoires |
| actes | `code`, `phase`, `activite` | `acte/CCAM/codeActe`, `codePhase`, `codeActivite` | obligatoires |
| actes | `quantite` | `CCAM/quantite` (défaut : 1) | |
| actes | `extension_pmsi`, `date_realisation`, `extension_documentaire` | `codeActeExtensionPMSI`, `dateRealisation`, `codeExtensionDocumentaire` | |
| actes | `modificateurs`, `association_non_prevue` | `modificateurs/modificateur`, `codeAssociationNonPrevue` | |
| actes | `remboursement_exceptionnel`, `externe` | `CCAM/@remboursementExceptionnel`, `acte/@externe` (booléen → oui/non) | |

`colmap={"ancien_nom": "nouveau_nom"}` renomme des colonnes existantes vers ces noms.

#### Colonnes-chemins : atteindre n'importe quel élément du XSD

Toute colonne dont le nom contient `/` ou commence par `@` est un chemin XML relatif
au nœud que décrit la table (`@nom` désigne un attribut). Pas besoin de colonne dédiée :

| table | colonne | produit |
|---|---|---|
| evenements | `patient/@anonyme` | `<patient anonyme="non">` |
| evenements | `venue/@prive` | `<venue prive="non">` |
| rum | `@classant` | `<rum classant="non">` |
| rum | `medecinResponsable/identification/code` | `<medecinResponsable><identification><code>…` |
| actes | `CCAM/@remboursementExceptionnel` | `<CCAM remboursementExceptionnel="non">` |

#### Résultat

Le fichier `sortie/rum/S240001_2.xml` produit par ce script (second RUM, en RUM unitaire) :

<!-- fichier:sejour:rum/S240001_2.xml -->
```xml
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<evenementsPMSI version="2.00">
  <enteteMessage>
    <identifiantMessage>S240001_2</identifiantMessage>
    <dateHeureProduction>2024-03-10T08:00:00</dateHeureProduction>
    <emetteur>
      <agents>
        <agent categorie="application">
          <code>DIM</code>
        </agent>
      </agents>
    </emetteur>
    <destinataire>
      <agents>
        <agent categorie="application">
          <code>DPI</code>
        </agent>
      </agents>
    </destinataire>
  </enteteMessage>
  <evenementPMSI>
    <patient>
      <identifiant>
        <emetteur>
          <valeur>190101337</valeur>
        </emetteur>
      </identifiant>
      <personnePhysique sexe="F">
        <dateNaissance>
          <date>1958-03-12</date>
        </dateNaissance>
      </personnePhysique>
    </patient>
    <venue>
      <identifiant>
        <emetteur>
          <valeur>240000123</valeur>
        </emetteur>
      </identifiant>
      <entree>
        <dateHeureOptionnelle>
          <date>2024-03-04</date>
          <heure>10:20:00</heure>
        </dateHeureOptionnelle>
      </entree>
      <sortie>
        <dateHeureOptionnelle>
          <date>2024-03-09</date>
        </dateHeureOptionnelle>
      </sortie>
    </venue>
    <rss>
      <identifiantRSS>
        <emetteur>240000123</emetteur>
      </identifiantRSS>
      <rum action="creation">
        <dateAction>2024-03-06T00:00:00</dateAction>
        <identifiant>
          <emetteur>S240001_2</emetteur>
        </identifiant>
        <medecinResponsable>
          <noRPPS>10009876543</noRPPS>
        </medecinResponsable>
        <uniteMedicale>
          <code>3405</code>
          <entree mode="6" complementMode="1">
            <date>2024-03-06</date>
            <heure>14:00:00</heure>
          </entree>
          <sortie mode="8">
            <date>2024-03-09</date>
          </sortie>
        </uniteMedicale>
        <diagnostics>
          <diagnosticPrincipal>
            <codeCim10>I501</codeCim10>
          </diagnosticPrincipal>
          <diagnosticsSignificatifs>
            <diagnosticSignificatif>
              <codeCim10>N183</codeCim10>
            </diagnosticSignificatif>
            <diagnosticSignificatif>
              <codeCim10>E119</codeCim10>
            </diagnosticSignificatif>
          </diagnosticsSignificatifs>
        </diagnostics>
        <actes>
          <acte>
            <CCAM>
              <codeActe>DEQP003</codeActe>
              <codePhase>0</codePhase>
              <codeActivite>1</codeActivite>
              <quantite>1</quantite>
              <dateRealisation>2024-03-06T15:00:00</dateRealisation>
            </CCAM>
          </acte>
        </actes>
      </rum>
    </rss>
  </evenementPMSI>
</evenementsPMSI>

```
<!-- /fichier:sejour:rum/S240001_2.xml -->

### Serveur d'actes et états patient

Même principe, avec les mêmes options (`xmlns`, `version`, `validate_xsd`, `filename`, `colmap`) :

- `hx.write_evenements_serveur_actes(evenements, actes, ...)` : `evenementServeurActe`
  avec patient, venue, intervention (colonnes `intervention_*`, `demande_*`) et `actesCCAM`
  (une ligne par acte : `acte_id`, `code`, `activite`, `phase`, `date_execution`, `medecin`…).
- `hx.write_evenements_etat_patient(evenements, diagnostics, ...)` : patient, venue,
  intervention et `Diagnostics` (une ligne par diagnostic : `type` en dp, dr, da…, `code`,
  `date_action`).

Les colonnes de chaque table sont décrites dans les docstrings de `pyhprimxml.pmsi`,
`pyhprimxml.serveur_actes` et `pyhprimxml.etat_patient`.

#### États patient : IGS2 détaillé

L'IGS2 détaillé passe par un message états patient : un élément `<igs2>` dont chaque item
est un **attribut qui porte une classe** (`age="60A69"`, `frequenceCardiaque="120A159"`…),
plus le score global `valeurGlobale` (de 0 à 194). Aucune fonction dédiée n'est nécessaire :
les [colonnes-chemins](#colonnes-chemins--atteindre-nimporte-quel-élément-du-xsd) `igs2/@age`, `igs2/valeurGlobale`… donnent accès à tout
l'élément.

Le script `examples/exemple_igs2.py` part des pires valeurs mesurées pendant les 24 premières
heures. Il en déduit la classe et les points de chaque item selon la grille IGS2 de la SFAR
(Le Gall, 1993), puis écrit un fichier par patient, en version 2.00, validé contre le XSD.

Points imposés par le XSD :

- **un seul `<igs2>` par message**, donc un fichier par patient ;
- **un repère obligatoire** : ici le `recueil` (colonnes `recueil_id`, `recueil_date`,
  `recueil_uf`), qui donne la date **et l'UF** où les états ont été observés ; le récepteur
  retrouve ainsi le RUM, même un jour de mutation. Une simple date (`date_observation`) ou une
  intervention sont aussi possibles ;
- **un contenu exclusif** : un message porte soit des diagnostics, soit un IGS2, soit des
  dépendances…, jamais deux à la fois ;
- en version 2.4 (pas en 2.00), un élément `<divers/>` obligatoire, émis automatiquement.

La table de contrôle produite par le script (classe et points par item) :

<!-- tables:igs2:controle -->
| item | classe_IGS240001 | classe_IGS240002 | points_IGS240001 | points_IGS240002 |
|---|---|---|---|---|
| age | 60A69 | superieurEgalA80 | 12 | 18 |
| frequenceCardiaque | 120A159 | 70A119 | 4 | 0 |
| tensionArterielleSystolique | 70A99 | superieurEgalA200 | 5 | 2 |
| temperature | inferieurA39 | superieurEgalA39 | 0 | 3 |
| paO2_FIO2 | 100A199 | rien | 9 | 0 |
| diurese | "0,5A0,999" | superieurA1 | 4 | 0 |
| ureeSanguine | "10A29,9" | inferieurA10 | 6 | 0 |
| leucocytes | "1A19,9" | superieurEgalA20 | 0 | 3 |
| kaliemie | "3A4,9" | superieurEgalA5 | 0 | 3 |
| natremie | 125A144 | superieurEgalA145 | 0 | 1 |
| HCO3 | 15A19 | superieurEgalA20 | 3 | 0 |
| bilirubine | "inferieurA68,4" | "superieurA102,6" | 0 | 9 |
| scoreGlasgow | 11A13 | 14A18 | 5 | 0 |
| maladieChronique | aucune | cancerMetastatique | 0 | 9 |
| modeAdmission | medecine | chirUrgente | 6 | 8 |
<!-- /tables:igs2:controle -->

Le code complet :

<!-- exemple:igs2 -->
```python
# IGS2 détaillé dans un message états patient (evenementsServeurEtatsPatient).
# Des mesures brutes (pires valeurs des 24 premières heures), on déduit pour chaque item
# la classe attendue par le XSD (attribut de <igs2>) et ses points, puis le score global.
# Un fichier par patient : l'élément <igs2> n'est pas répétable dans un message.
from datetime import date, datetime

import polars as pl

import pyhprimxml as hx

entete = {
    "version": "2.00",                   # version HPRIM XML des messages
    "emetteur": "REA",
    "destinataire": "DIM",
    "date_heure_production": datetime(2024, 3, 6, 9, 0),
}

# Pires valeurs des 24 premières heures, une ligne par patient
mesures = pl.DataFrame({
    "evt_id": ["IGS240001", "IGS240002"],
    "age": [67, 82],
    "frequence_cardiaque": [128, 105],      # /min
    "pas": [85, 210],                       # pression artérielle systolique, mmHg
    "temperature": [38.2, 39.4],            # °C
    "ventile": [True, False],               # ventilation mécanique ou CPAP
    "pao2_fio2": [180, None],               # mmHg, si ventilé
    "diurese": [0.8, 1.6],                  # L/24 h
    "uree": [18.0, 8.0],                    # mmol/L
    "leucocytes": [14.0, 22.0],             # 10³/mm³
    "kaliemie": [4.1, 5.4],                 # mmol/L
    "natremie": [132, 147],                 # mmol/L
    "hco3": [17, 22],                       # mmol/L
    "bilirubine": [25.0, 110.0],            # µmol/L
    "ictere": [False, True],                # la bilirubine ne compte que si ictère
    "glasgow": [13, 15],
    "maladie_chronique": ["aucune", "cancerMetastatique"],
    "mode_admission": ["medecine", "chirUrgente"],
})

# Barème IGS2 : attribut XSD -> (mesure, bornes, [(classe XSD, points)])
# Source : grille et définitions de la SFAR, https://sfar.org/scores/igs2.php
# (Le Gall JR et coll., JAMA 1993; 270: 2957-2963). Recueil sur les 24 heures suivant
# l'admission : valeur la plus défavorable de chaque item ; Glasgow estimé avant sédation ;
# diurèse ramenée à 24 h si le séjour est plus court ; en cas d'arrêt cardiaque, FC 0,
# PAS 0 et Glasgow < 6. Unités : urée en mmol/L (seuils SFAR en g/L : 0,6 et 1,8),
# leucocytes en 10³/mm³, bilirubine en µmol/L (seuils en mg/L : 40 et 60).
# Les bornes sont fermées à gauche : 40 tombe dans « 40A59 ».
BAREME = {
    "age": ("age", [40, 60, 70, 75, 80],
            [("inferieurA40", 0), ("40A59", 7), ("60A69", 12), ("70A74", 15),
             ("75A79", 16), ("superieurEgalA80", 18)]),
    "frequenceCardiaque": ("frequence_cardiaque", [40, 70, 120, 160],
            [("inferieurA40", 11), ("40A69", 2), ("70A119", 0), ("120A159", 4),
             ("superieurEgalA160", 7)]),
    "tensionArterielleSystolique": ("pas", [70, 100, 200],
            [("inferieurA70", 13), ("70A99", 5), ("100A199", 0), ("superieurEgalA200", 2)]),
    "temperature": ("temperature", [39], [("inferieurA39", 0), ("superieurEgalA39", 3)]),
    "paO2_FIO2": ("pao2_fio2", [100, 200],
            [("inferieurA100", 11), ("100A199", 9), ("superieurEgalA200", 6)]),
    "diurese": ("diurese", [0.5, 1.0],
            [("inferieurA0,5", 11), ("0,5A0,999", 4), ("superieurA1", 0)]),
    "ureeSanguine": ("uree", [10, 30],
            [("inferieurA10", 0), ("10A29,9", 6), ("superieurA30", 10)]),
    "leucocytes": ("leucocytes", [1, 20],
            [("inferieurA1", 12), ("1A19,9", 0), ("superieurEgalA20", 3)]),
    "kaliemie": ("kaliemie", [3, 5],
            [("inferieurA3", 3), ("3A4,9", 0), ("superieurEgalA5", 3)]),
    "natremie": ("natremie", [125, 145],
            [("inferieurA125", 5), ("125A144", 0), ("superieurEgalA145", 1)]),
    "HCO3": ("hco3", [15, 20], [("inferieurA15", 6), ("15A19", 3), ("superieurEgalA20", 0)]),
    "bilirubine": ("bilirubine", [68.4, 102.6],
            [("inferieurA68,4", 0), ("68,4A102,5", 4), ("superieurA102,6", 9)]),
    "scoreGlasgow": ("glasgow", [6, 9, 11, 14],
            [("inferieurA6", 26), ("6A8", 13), ("9A10", 7), ("11A13", 5), ("14A18", 0)]),
}
POINTS_QUALITATIFS = {
    "maladieChronique": ("maladie_chronique",
            {"aucune": 0, "cancerMetastatique": 9, "maladieHematologiqueMaligne": 10, "sida": 17}),
    "modeAdmission": ("mode_admission", {"chirProgrammee": 0, "medecine": 6, "chirUrgente": 8}),
}

def classer(mesure: str, bornes: list, libelles: list) -> pl.Expr:
    """Classe d'une mesure : libelles[i] si bornes[i-1] <= mesure < bornes[i]."""
    expr = pl.lit(libelles[-1])
    for borne, libelle in reversed(list(zip(bornes, libelles))):
        expr = pl.when(pl.col(mesure) < borne).then(pl.lit(libelle)).otherwise(expr)
    return pl.when(pl.col(mesure).is_null()).then(None).otherwise(expr)


classes, points = [], []
for attr, (mesure, bornes, cl) in BAREME.items():
    classe = classer(mesure, bornes, [c for c, _ in cl])
    if attr == "paO2_FIO2":  # ni ventilé ni sous CPAP : classe « rien », 0 point
        classe = pl.when(pl.col("ventile")).then(classe).otherwise(pl.lit("rien"))
    if attr == "bilirubine":  # patient non ictérique : classe la plus basse, 0 point
        classe = pl.when(pl.col("ictere")).then(classe).otherwise(pl.lit("inferieurA68,4"))
    classes.append(classe.alias(attr))
    points.append(pl.col(attr).replace_strict(dict(cl) | {"rien": 0}, return_dtype=pl.Int64)
                  .alias(f"points_{attr}"))
for attr, (mesure, bareme) in POINTS_QUALITATIFS.items():
    classes.append(pl.col(mesure).alias(attr))
    points.append(pl.col(mesure).replace_strict(bareme, return_dtype=pl.Int64)
                  .alias(f"points_{attr}"))

igs2 = (
    mesures.with_columns(classes)
    .with_columns(points)
    .with_columns(valeurGlobale=pl.sum_horizontal(pl.col("^points_.*$")))
)
attributs = list(BAREME) + list(POINTS_QUALITATIFS)

# Patient et venue, une ligne par message
patients = pl.DataFrame({
    "evt_id": ["IGS240001", "IGS240002"],
    "ipp": ["190101337", "190101338"], "sexe": ["M", "F"],
    "date_naissance": [date(1956, 5, 14), date(1941, 11, 2)],
    "nda": ["240000123", "240000124"], "venue_date_entree": [date(2024, 3, 5)] * 2,
    # repère du message : le recueil, avec sa date et l'UF de réanimation où les états ont
    # été observés (le récepteur retrouve ainsi le RUM, même un jour de mutation)
    "recueil_id": ["REC240001", "REC240002"],
    "recueil_date": [date(2024, 3, 6)] * 2,
    "recueil_uf": ["4501"] * 2,
})

# L'IGS2 passe par des colonnes-chemins relatives à la racine du message
evenements = patients.join(
    igs2.select(
        "evt_id",
        pl.lit("creation").alias("igs2/@action"),
        *[pl.col(a).alias(f"igs2/@{a}") for a in attributs],
        pl.lit(datetime(2024, 3, 6, 8, 0)).alias("igs2/dateAction"),
        pl.col("valeurGlobale").alias("igs2/valeurGlobale"),
    ),
    on="evt_id",
)

fichiers = hx.write_evenements_etat_patient(
    evenements, None,                   # pas de table de diagnostics ici
    entete=entete,
    out_dir="sortie/igs2",              # -> sortie/igs2/IGS240001.xml, IGS240002.xml
    xmlns=None,
)

# Contrôle : une ligne par item, avec la classe et les points de chaque patient
controle = (
    igs2.unpivot(index="evt_id", on=attributs, variable_name="item", value_name="classe")
    .join(igs2.unpivot(index="evt_id", on=[f"points_{a}" for a in attributs],
                       variable_name="item", value_name="points")
              .with_columns(pl.col("item").str.strip_prefix("points_")),
          on=["evt_id", "item"], maintain_order="left")
    .pivot(on="evt_id", index="item", values=["classe", "points"])
)
```
<!-- /exemple:igs2 -->

Le fichier produit pour le premier patient (`sortie/igs2/IGS240001.xml`) :

<!-- fichier:igs2:igs2/IGS240001.xml -->
```xml
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<evenementsServeurEtatsPatient version="2.00">
  <enteteMessage>
    <identifiantMessage>IGS240001</identifiantMessage>
    <dateHeureProduction>2024-03-06T09:00:00</dateHeureProduction>
    <emetteur>
      <agents>
        <agent categorie="application">
          <code>REA</code>
        </agent>
      </agents>
    </emetteur>
    <destinataire>
      <agents>
        <agent categorie="application">
          <code>DIM</code>
        </agent>
      </agents>
    </destinataire>
  </enteteMessage>
  <patient>
    <identifiant>
      <emetteur>
        <valeur>190101337</valeur>
      </emetteur>
    </identifiant>
    <personnePhysique sexe="M">
      <dateNaissance>
        <date>1956-05-14</date>
      </dateNaissance>
    </personnePhysique>
  </patient>
  <venue>
    <identifiant>
      <emetteur>
        <valeur>240000123</valeur>
      </emetteur>
    </identifiant>
    <entree>
      <dateHeureOptionnelle>
        <date>2024-03-05</date>
      </dateHeureOptionnelle>
    </entree>
  </venue>
  <recueil>
    <identifiant>
      <emetteur>REC240001</emetteur>
    </identifiant>
    <date>2024-03-06</date>
    <uniteFonctionnelle>
      <code>4501</code>
    </uniteFonctionnelle>
  </recueil>
  <igs2 action="creation" modeAdmission="medecine" maladieChronique="aucune" scoreGlasgow="11A13" age="60A69" tensionArterielleSystolique="70A99" frequenceCardiaque="120A159" temperature="inferieurA39" paO2_FIO2="100A199" diurese="0,5A0,999" ureeSanguine="10A29,9" leucocytes="1A19,9" kaliemie="3A4,9" natremie="125A144" HCO3="15A19" bilirubine="inferieurA68,4">
    <dateAction>2024-03-06T08:00:00</dateAction>
    <valeurGlobale>54</valeurGlobale>
  </igs2>
</evenementsServeurEtatsPatient>

```
<!-- /fichier:igs2:igs2/IGS240001.xml -->

> **Source du barème.** Grille et définitions de la SFAR (https://sfar.org/scores/igs2.php),
> d'après Le Gall JR et coll., *JAMA* 1993; 270: 2957-2963. Les 15 items, seuils et points
> du script sont vérifiés contre cette grille par un test. Elle lève aussi les ambiguïtés des
> classes du XSD : `14A18` correspond à un Glasgow de 14 à 15, `superieurA1` à une diurèse
> d'au moins 1 L. Les règles de recueil (pires valeurs des 24 premières heures, Glasgow
> avant sédation, bilirubine seulement en cas d'ictère…) restent celles de votre service.

### Depuis un dictionnaire (tous types de messages)

`to_xml` / `write_xml` prennent un dictionnaire au format xmltodict, le même que celui
produit à la lecture. L'aller-retour lecture → écriture redonne les trois fichiers
d'exemple à l'identique.

```python
import xmltodict
tree = xmltodict.parse(open("data/xml_tests/actes/00001.xml", "rb").read())
hx.write_xml(tree, "copie.xml", xmlns=None)
```

### Options

- `xmlns` : `hx.HPRIM_NS` (défaut), `None` (aucune déclaration) ou `""` (`xmlns=""` littéral).
  La validation utilise automatiquement la variante de XSD sans namespace.
- `drop_empty=True` (défaut) : supprime les éléments et attributs vides (`<seance></seance>`,
  `nombreFaisceau=""`…), ce qui les rendrait invalides. Les éléments obligatoires du XSD
  sont conservés (ex. `<diagnostics/>`).
- `strict=True` : une clé absente du XSD lève une erreur au lieu d'être ignorée.
- `fichier_ok` : dépose un `.ok` vide une fois chaque `.xml` écrit intégralement ; le `.xml`
  est toujours écrit de façon atomique (nom temporaire puis renommage).
- `version` : version du schéma ; par défaut l'attribut `version` du message, sinon 2.4
  (les exemples déclarent `"version": "2.00"` dans `entete`).
- `hx.validate(xml_bytes)` : liste des erreurs XSD (vide si conforme).

## 2. Lecture : des fichiers HPRIM XML vers les tables

Les fonctions `read_*` sont l'inverse exact des fonctions `write_*` : elles renvoient
les mêmes tables, avec les mêmes noms de colonnes.

```python
import pyhprimxml as hx

t = hx.read_evenements_pmsi("dossier/")      # fichier, dossier, motif glob, bytes ou liste
t["evenements"], t["rum"], t["diagnostics"], t["actes"]

hx.read_evenements_serveur_actes("actes/")   # {"evenements", "actes"}
hx.read_evenements_etat_patient("etats/")    # {"evenements", "diagnostics"}
```

- **Lecture guidée par le XSD.** Un élément répétable est toujours une liste, même s'il
  n'apparaît qu'une fois : un RUM avec un seul acte donne bien une ligne dans `actes`.
- **Colonnes typées d'après le XSD** : `xsd:date` → `Date`, `xsd:dateTime` → `Datetime`,
  `xsd:time` → `Time`, types entiers → `Int64`, le reste (et tous les attributs) en texte.
  Le XSD a quelques particularités : `nombre2` est un entier, mais `nombre5` (par exemple la
  `quantite` des actes du serveur d'actes) est une chaîne de chiffres, relue en texte.
- **Namespace indifférent** : un fichier avec, sans ou à `xmlns` vide se relit à l'identique.
- **Clés absentes du XML.** `evt_id` est le nom du fichier sans extension (suffixé `_1`, `_2`…
  si un fichier contient plusieurs événements). `rum_id` est le rang du RUM dans le RSS (1, 2…) ;
  l'identifiant XML du RUM est dans `rum_emetteur`.
- **En-tête dans `evenements`** : `version`, `acquittement_attendu`, `mode_traitement`,
  `identifiant_message`, `date_heure_production`, `emetteur`, `destinataire`, `commentaire`…
  En écriture, ces colonnes priment sur le dict `entete`, qui devient facultatif. On peut donc
  réécrire directement ce qu'on a lu : `hx.write_evenements_pmsi(*t.values(), out_dir=...)`.
- **`extra`** est le symétrique des colonnes-chemins : il liste, par table, les chemins
  supplémentaires à extraire.

```python
t = hx.read_evenements_pmsi(
    "dossier/",
    extra={
        "evenements": ["patient/@anonyme", "venue/@prive"],
        "rum": ["@classant", "medecinResponsable/identification/code"],
    },
)
```

- `exiger_ok=True` ne lit que les `.xml` dont le marqueur `.ok` est présent (dépôt terminé).
- `backend="pandas"` renvoie des DataFrames pandas.
- Débit indicatif : environ 3 000 fichiers par seconde.
- Limites actuelles : PMSI → RSS MCO uniquement (les `rhss`, `rpsss`, `rimp`, `rssGhs`
  sont signalés par un avertissement) ; serveur d'actes → actes CCAM uniquement.

Les allers-retours tables → XML → tables et XML → tables → XML sont vérifiés sur les trois
exemples par `tests/test_relecture.py`.

`hx.parse_xml(fichier)` donne la version dictionnaire (typée, guidée par le XSD), au format
accepté par `hx.to_xml`. `read_hprimxml` (lecture en structs polars imbriqués) reste disponible.

## 3. Autres façons de lire : xpath et structs polars

Les fonctions de la section précédente lisent les messages vers des tables prêtes à
l'emploi. Pour explorer des fichiers sans passer par ces tables, deux autres approches
restent documentées ici.

Il existe plusieurs manières de lire les données d'un fichier XML.

La plus rapide en temps est certainement d'utiliser les chemins xpath.
Néanmoins cet accès rapide fait souvent l'impasse sur la structure hiérarchique du fichier qui en tant que telle est une information importante.


### Utilisation de xpath pour interroger des éléments xml

Trois exemples sont réalisés autour des fichiers hprimXML utilisant xpath :

- le [premier](https://guillaumepressiat.github.io/pyhprimxml/xpath_xml.html) utilise le package python xml en spécifiant le namespace xmlns d'hprim au travers d'un alias dans les définitions de xpath.
- le [deuxième](https://guillaumepressiat.github.io/pyhprimxml/xpath_lxml.html) utilise le package python lxml en supprimant le namespace xmlns avant d'utiliser xpath.

- le [troisième](https://guillaumepressiat.github.io/pyhprimxml/xpath_xml_r.html) utilise R et le package xml2 en supprimant le namespace xmlns avant d'utiliser xpath.

### Récupération des éléments XML complets


L'utilisation du package [pyhprimxml](https://guillaumepressiat.github.io/pyhprimxml/) dans le contexte de la lecture de fichiers hprimXML (v1.07 et v2 testés) est présentée [ici](https://guillaumepressiat.github.io/pyhprimxml/historique/lecture-structs-polars.html).

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

La lecture historique `read_hprimxml` (structs polars imbriqués) reste disponible. Elle
s'appuie sur :

- lxml : pour enlever le namespace xmlns avec un script xslt ;
- xmltodict : pour convertir le xml en dict python ;
- polars : pour les étapes de déstructuration de la donnée hiérarchique issue des XML.

Ressources :

- le script pour le namespace xslt est issu de la ressource [ici](https://wiki.tei-c.org/index.php/Remove-Namespaces.xsl) ;
- la fonction d'aplatissement récursif des struct/list en polars est issue d'[ici](https://github.com/pola-rs/polars/issues/7078#issuecomment-2258225305).

## Documentation

La documentation est publiée sur **https://guillaumepressiat.github.io/pyhprimxml/**.

Elle est construite avec [MkDocs](https://www.mkdocs.org/) (thème Material) à partir du
dossier `doc/` et des docstrings, puis publiée sur GitHub Pages par le workflow
`.github/workflows/docs.yml` à chaque push sur `main`. Le workflow vérifie au passage que
les exemples de la doc sont à jour (`tools/exemples_doc.py --check`) et refuse de publier
une doc qui se construit avec des avertissements.

Pour la construire en local :

```bash
pip install -r doc/requirements.txt
mkdocs serve      # aperçu sur http://127.0.0.1:8000
mkdocs build      # site statique dans site/
```

Les anciennes pages (xpath, lecture en structs polars) font partie du site, aux mêmes
adresses pour les pages xpath. Le dossier `docs/`, qui les publiait jusqu'ici, n'est plus
nécessaire une fois le nouveau déploiement en place.

## Contexte

> Ce projet a également une visée documentaire / bloc-notes : il propose des pistes pour
> exploiter ces données dans divers contextes en les dénaturant le moins possible.

