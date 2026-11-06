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
