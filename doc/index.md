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

## Exemple : un séjour écrit en HPRIM XML, puis relu

Une patiente entre par les urgences en cardiologie (UM 1201), est mutée en médecine
(UM 3405), puis rentre à domicile : un RSS de deux RUM. Le script écrit le séjour en un
fichier, puis en RUM unitaires, et le relit.

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

Les RUM relus, avec les diagnostics en colonnes (`rum_relu`) :

<!-- tables:sejour:rum_relu -->
| evt_id | rum_id | rum_emetteur | um | dp | das |
|---|---|---|---|---|---|
| S240001 | 1 | S240001_1 | 1201 | I210 | [E119, I10, E780] |
| S240001 | 2 | S240001_2 | 3405 | I501 | [N183, E119] |
<!-- /tables:sejour:rum_relu -->

Le second RUM, en RUM unitaire (`sortie/rum/S240001_2.xml`) :

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

## Principes

**Le XSD officiel pilote tout.** À l'écriture, il fixe l'ordre des éléments, la distinction
entre attribut et élément, les éléments obligatoires et le format des dates. À la lecture,
il indique quels éléments sont répétables et le type de chaque valeur. Chaque fichier
écrit est validé contre son XSD, en mode erreur par défaut.

**La lecture est l'inverse exact de l'écriture.** Les fonctions `read_*` renvoient les
tables qu'attendent les fonctions `write_*`, avec les mêmes noms de colonnes.
L'aller-retour tables → XML → tables, et XML → tables → XML, est vérifié par les tests.

**Un fichier par événement**, un séjour par défaut ou un RUM avec `par_rum=True`.
**L'identifiant du message est le nom du fichier** sans extension : un fichier, son
contenu et son marqueur `.ok` se rapprochent sans ambiguïté.

**Tout le XSD reste accessible.** Les colonnes métier nommées couvrent l'usage courant ;
les [colonnes-chemins](guide/ecriture.md#colonnes-chemins) atteignent n'importe quel
élément ou attribut.

**La documentation ne peut pas diverger du code.** Le code, les tableaux et les extraits
XML de ces pages proviennent des scripts `examples/` : `tools/exemples_doc.py` les recopie,
et les tests échouent si une page n'est plus à jour.

## Pour aller plus loin

- [Écrire depuis des tables](guide/ecriture.md) : les quatre tables, les trois formes de
  diagnostics, la correspondance colonnes → XML, les options
- [RUM unitaires et dépôts `.ok`](guide/rum-unitaires.md) : un fichier par RUM, marqueurs de dépôt complet
- [Relire vers des tables](guide/lecture.md) : colonnes typées, `extra`, `format_diagnostics`
- [Serveur d'actes et états patient](guide/autres-messages.md)
- [Exemples](exemples.md) : tous les scripts, dont ceux qui régénèrent `data/xml_tests`
- [Référence API](reference/pmsi.md)
