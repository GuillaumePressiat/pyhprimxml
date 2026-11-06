# Serveur d'actes et états patient

Ces deux messages suivent les mêmes principes que le PMSI : un fichier par événement,
mêmes options (`entete`, `xmlns`, `version`, `validate_xsd`, `filename`, `encoding`,
`colmap`), colonnes-chemins à l'écriture et `extra` à la lecture.

## Colonnes communes de `evenements`

| groupe | colonnes |
|---|---|
| patient | `ipp`, `ipp_recepteur`, `sexe`, `nom_usuel`, `nom_naissance`, `prenom`, `date_naissance` |
| venue (facultative) | `nda`, `nda_recepteur`, `venue_date_entree`, `venue_heure_entree`, `venue_mode_entree`, `venue_uf_responsable`, `venue_date_sortie`, `venue_heure_sortie` |
| intervention (facultative) | `intervention_id`, `intervention_date_debut`, `intervention_heure_debut`, `intervention_date_fin`, `intervention_heure_fin`, `intervention_uf` |
| demande (facultative) | `demande_date`, `demande_heure`, `demande_uf` |
| repère des états patient | `date_observation`, `heure_observation` ; ou `recueil_id`, `recueil_date`, `recueil_heure`, `recueil_uf` |
| en-tête | voir [En-tête du message](ecriture.md#en-tete-du-message) |

Obligatoires : `evt_id`, `ipp`, `sexe`, `date_naissance`. La venue n'est écrite que si
`nda` est renseigné, l'intervention que si `intervention_id` l'est.

## Serveur d'actes : `evenementsServeurActes`

```python
hx.write_evenements_serveur_actes(evenements, actes, entete=..., out_dir="sortie/")
t = hx.read_evenements_serveur_actes("sortie/")   # {"evenements", "actes"}
```

Table **`actes`** : une ligne par `acteCCAM`. Les colonnes-chemins sont relatives à `acteCCAM`.

| colonne | élément / attribut XML | |
|---|---|---|
| `acte_id` | `acteCCAM/identifiant/emetteur` | obligatoire |
| `code`, `extension_pmsi` | `codeActe`, `codeActeExtensionPMSI` | `code` obligatoire |
| `activite`, `phase` | `codeActivite`, `codePhase` | obligatoires |
| `date_execution`, `heure_execution` | `execute/date`, `execute/heure` | date obligatoire |
| `medecin` | `executant/medecins/medecinExecutant/medecin/identification/code` | obligatoire |
| `medecin_principal` | `medecinExecutant/@principal` (défaut : `oui`) | |
| `uf` | `executant/uniteFonctionnelle/code` | |
| `quantite` | `quantite` (`nombre5`, chaîne de chiffres) | |
| `action` | `@action` (défaut : `creation`) | |
| `facturable`, `valide` | `@facturable`, `@valide` | |
| `modificateurs` | `modificateurs/modificateur` (ex. `"7J"`) | |
| `association_non_prevue`, `extension_documentaire` | `codeAssociationNonPrevue`, `codeExtensionDocumentaire` | |

Les actes NGAP, LPP et UCD ne sont pas encore pris en charge par la couche tabulaire ;
ils restent accessibles par [le dictionnaire](dictionnaire.md).

## États patient : `evenementsServeurEtatsPatient`

```python
hx.write_evenements_etat_patient(evenements, diagnostics, entete=..., out_dir="sortie/")
t = hx.read_evenements_etat_patient("sortie/")    # {"evenements", "diagnostics"}
```

Ce message n'a pas de nœud « événement » : les colonnes-chemins de `evenements` sont
relatives à la racine du message.

Le XSD impose un **repère**, au choix : une intervention (colonnes `intervention_*`), une
date d'observation (colonnes `date_observation`, `heure_observation`) ou un recueil
(colonnes `recueil_id`, `recueil_date`, `recueil_heure`, `recueil_uf`). Le recueil est le plus
précis : il porte l'UF où les états ont été observés, qui permet au récepteur de retrouver le
RUM. Le **contenu** est lui aussi un choix exclusif : des
diagnostics, ou un IGS2, ou des dépendances… En 2.4, un élément `<divers/>` est
obligatoire ; il est émis automatiquement.

Table **`diagnostics`** : une ligne par diagnostic. Les colonnes-chemins sont relatives à `diagnostic`.

| colonne | élément / attribut XML | |
|---|---|---|
| `type` | `diagnostic/@type` : `dp`, `dr`, `da`, `ds`, `dd`, `fpc`, `mm`, `ae` (mis en minuscules) | obligatoire |
| `code` | `codeCim10` (point retiré) | obligatoire |
| `date_action` | `dateAction` | |
| `action` | `@action` (défaut : `creation`) | |

## États patient : IGS2 détaillé

L'IGS2 détaillé passe par un message états patient : un élément `<igs2>` dont chaque item
est un **attribut qui porte une classe** (`age="60A69"`, `frequenceCardiaque="120A159"`…),
plus le score global `valeurGlobale` (de 0 à 194). Aucune fonction dédiée n'est nécessaire :
les [colonnes-chemins](ecriture.md#colonnes-chemins) `igs2/@age`, `igs2/valeurGlobale`… donnent accès à tout
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

!!! note "Source du barème"
    Grille et définitions de la SFAR (<https://sfar.org/scores/igs2.php>), d'après
    Le Gall JR et coll., *JAMA* 1993; 270: 2957-2963. Les 15 items, seuils et points du
    script sont vérifiés contre cette grille par un test. Elle lève aussi les ambiguïtés
    des classes du XSD : `14A18` correspond à un Glasgow de 14 à 15, `superieurA1` à une
    diurèse d'au moins 1 L. Les règles de recueil (pires valeurs des 24 premières heures,
    Glasgow avant sédation, bilirubine seulement en cas d'ictère…) restent celles de
    votre service.