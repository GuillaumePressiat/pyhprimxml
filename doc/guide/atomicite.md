# Atomicité des messages

Chaque type de message a une **unité atomique** : l'objet que le standard sait créer,
modifier ou supprimer, parce qu'il porte l'attribut `action` et un identifiant. Un message
atomique transporte une seule de ces unités : il peut être accepté, rejeté ou renvoyé
indépendamment des autres.

| message | unité atomique | argument |
|---|---|---|
| ePMSI (`evenementsPMSI`) | le **RUM** | `par_rum=True` |
| serveur d'actes (`evenementsServeurActes`) | l'**acte** (`acteCCAM`) | `par_acte=True` |
| états patient (`evenementsServeurEtatsPatient`) | le **diagnostic** | `par_diagnostic=True` |

Par défaut (`False`), un message porte tout l'événement : le séjour et ses RUM, l'intervention
et ses actes, l'observation et ses diagnostics.

## Pourquoi c'est l'attribut `action` qui décide

Dans le XSD, l'attribut `action` (`creation`, `modification`, `suppression`…) n'est pas posé sur
l'événement, mais sur l'objet qui change : le `rum`, l'`acteCCAM`, le `diagnostic`. C'est donc à
ce niveau que se produit le fait métier, et à ce niveau qu'un message peut être rejeté, corrigé
ou annulé seul.

Pour le PMSI, les diagnostics et les actes d'un RUM n'ont **ni action ni identifiant** : ils ne
sont que le contenu du RUM. Un message qui ne porterait qu'un diagnostic ou qu'un acte d'un RUM
reste valide, mais il envoie un RUM partiel avec `action="creation"` : son sens dépend
entièrement du récepteur (fusion ou remplacement). Le package ne propose donc pas ce découpage.
Pour transmettre des diagnostics un par un, le canal naturel est le message états patient ;
pour des actes un par un, le serveur d'actes.

En états patient, le contenu est exclusif : diagnostics, ou actes de rééducation, ou IGS2,
dépendances, naissance. Les diagnostics et les actes de rééducation sont répétables et portent
chacun leur action : ce sont les unités atomiques. L'IGS2, les dépendances et la naissance,
uniques par message, sont atomiques par construction. Les actes de rééducation ne sont pas
encore couverts par les tables du package.

## Exemple

Un séjour à deux RUM, une intervention à trois actes et une observation à deux diagnostics,
écrits en messages atomiques (script `examples/exemple_atomicite.py`) :

<!-- exemple:atomicite -->
```python
# Atomicité : un message par unité atomique, l'objet qui porte l'attribut `action` et un
# identifiant. Le RUM pour le PMSI, l'acte pour le serveur d'actes, le diagnostic pour les
# états patient. Le contexte (patient, venue…) est répété dans chaque message.
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
patient = {"ipp": ["190101337"], "sexe": ["F"], "date_naissance": [date(1958, 3, 12)],
           "nda": ["240000123"], "venue_date_entree": [date(2024, 3, 4)]}

# PMSI : un séjour, deux RUM -> deux messages (par_rum)
sejours = pl.DataFrame({"evt_id": ["S1"], **patient})
rum = pl.DataFrame({
    "evt_id": ["S1", "S1"], "rum_id": [1, 2], "rum_emetteur": ["S1_1", "S1_2"],
    "um": ["1201", "3405"], "um_date_entree": [date(2024, 3, 4), date(2024, 3, 6)],
    "um_mode_entree": ["8", "6"], "dp": ["I21.0", "I50.1"],
})
hx.write_evenements_pmsi(sejours, rum, entete=entete, out_dir="sortie/rum", par_rum=True)

# Serveur d'actes : une intervention, trois actes -> trois messages (par_acte)
interventions = pl.DataFrame({"evt_id": ["A1"], **patient,
                              "intervention_id": ["INT0001"], "intervention_uf": ["1201"]})
actes = pl.DataFrame({
    "evt_id": ["A1"] * 3, "acte_id": ["ACT01", "ACT02", "ACT03"],
    "code": ["DEQP003", "ZBQK002", "YYYY033"], "activite": [1] * 3, "phase": [0] * 3,
    "date_execution": [date(2024, 3, 4)] * 3, "medecin": ["01234567"] * 3,
})
hx.write_evenements_serveur_actes(interventions, actes, entete=entete, out_dir="sortie/actes",
                                  par_acte=True, filename="{evt_origine}_{acte_id}.xml")

# États patient : une observation, deux diagnostics -> deux messages (par_diagnostic)
observations = pl.DataFrame({"evt_id": ["D1"], **patient, "recueil_id": ["REC01"],
                             "recueil_date": [date(2024, 3, 4)], "recueil_uf": ["1201"]})
diagnostics = pl.DataFrame({
    "evt_id": ["D1", "D1"], "type": ["dp", "da"], "code": ["I21.0", "E11.9"],
    "date_action": [datetime(2024, 3, 4, 12, 0)] * 2,
})
hx.write_evenements_etat_patient(observations, diagnostics, entete=entete,
                                 out_dir="sortie/diagnostics", par_diagnostic=True)

# Bilan : un fichier par unité atomique
def compte(fichier, balise):
    return fichier.read_text().count(f"<{balise}")

produits = pl.DataFrame([
    {"fichier": f.relative_to("sortie").as_posix(), "RUM": compte(f, "rum "),
     "actes": compte(f, "acteCCAM"), "diagnostics": compte(f, "diagnostic ")}
    for f in sorted(Path("sortie").rglob("*.xml"))
])
```
<!-- /exemple:atomicite -->

Les fichiers produits, un par unité atomique :

<!-- tables:atomicite:produits -->
| fichier | RUM | actes | diagnostics |
|---|---|---|---|
| actes/A1_ACT01.xml | 0 | 1 | 0 |
| actes/A1_ACT02.xml | 0 | 1 | 0 |
| actes/A1_ACT03.xml | 0 | 1 | 0 |
| diagnostics/D1_1.xml | 0 | 0 | 1 |
| diagnostics/D1_2.xml | 0 | 0 | 1 |
| rum/S1_1.xml | 1 | 0 | 0 |
| rum/S1_2.xml | 1 | 0 | 0 |
<!-- /tables:atomicite:produits -->

## Identifiants et noms de fichier

En mode atomique, la ligne d'événement est répétée pour chaque unité, et enrichie :

| clé | valeur | disponible dans le gabarit `filename` |
|---|---|---|
| `evt_id` | `{evt_id}_{rum_id}` (PMSI) ou `{evt_id}_{rang}` (actes, diagnostics) | oui, nom par défaut |
| `evt_origine` | l'`evt_id` de départ (le séjour, l'intervention, l'observation) | oui |
| `rang` | rang de l'acte ou du diagnostic dans l'événement | oui |
| `rum_id`, `rss_id` | PMSI | oui |
| `acte_id` | serveur d'actes | oui |

La règle identifiant du message = nom du fichier s'applique toujours, avec sa limite de
12 caractères. Une colonne `identifiant_message` dans la table de l'unité (`rum`, `actes`,
`diagnostics`) fixe l'identifiant de chaque message ; on s'en sert alors pour nommer les
fichiers : `filename="{identifiant_message}.xml"`.

## Conséquences pratiques

- **Rejets et renvois** : un rejet porte sur une seule unité, qu'on corrige et renvoie seule.
- **Suppression** : on renvoie l'unité avec `action="suppression"` (colonne `action` de la table
  de l'unité), le même identifiant d'unité, et un **nouvel** identifiant de message.
- **Ordre** : chaque message est indépendant ; si une création et une suppression de la même
  unité sont proches dans le temps, l'ordre de traitement dépend du récepteur.
- **Dépôts** : avec `fichier_ok=True`, chaque message atomique a son propre `.ok`.
- **Événement sans unité** (une intervention sans acte) : en mode atomique, il ne produit aucun
  message, et un avertissement le signale.
