# Exemples

Tous les exemples écrivent en **version 2.00**, déclarée une fois dans l'en-tête
(`entete = {"version": "2.00", ...}`). Sans précision, le package écrit en 2.4, la dernière
version publiée ; le paramètre `version=` d'un appel l'emporte sur l'en-tête.

Le dossier `examples/` contient un script par fichier de `data/xml_tests` : chacun
construit des tables polars et régénère le fichier correspondant.

```bash
python examples/exemple_sejour.py           # -> sortie/sejour/S240001.xml, sortie/rum/S240001_1.xml…
python examples/exemple_pmsi.py            # -> examples/sortie/pmsi/00001_pmsi.xml
python examples/exemple_serveur_actes.py   # -> examples/sortie/actes/00001_acte.xml
python examples/exemple_etat_patient.py    # -> examples/sortie/etat_patient/00001_esep.xml
```

Chaque fichier produit est identique à sa référence, à deux différences près. Il porte
le nom de son identifiant de message (`00001_pmsi.xml`…), selon la règle
[identifiant du message = nom du fichier](guide/ecriture.md#identifiant-du-message-nom-du-fichier),
alors que les originaux s'appellent `00001.xml`. Et les éléments vides de l'original, non
conformes au XSD, sont supprimés. L'agent destinataire sans `code`
est reproduit tel quel ; il n'est pas conforme au XSD, d'où `validate_xsd="warn"` dans les
scripts.

Les tests `tests/test_exemples.py` et `tests/test_relecture.py` vérifient ces fichiers et
les allers-retours tables → XML → tables et XML → tables → XML.

## Séjour réaliste avec mutation, par séjour et par RUM

Entrée par les urgences en cardiologie, mutation en médecine, sortie à domicile : un RSS
de deux RUM, avec de vrais codes CIM-10 et CCAM, écrit en un fichier par séjour puis en RUM
unitaires. Les tables sont présentées dans [Écrire depuis des tables](guide/ecriture.md).

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

## Diagnostics : trois formes équivalentes

Un RUM avec un DP et quatre DAS, donné en format long, en colonnes de `rum` avec les DAS en
liste, puis avec les DAS en chaîne séparée par des virgules. Les trois fichiers produits sont
identiques.

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

## États patient : IGS2 détaillé

Des mesures brutes aux classes du XSD et aux points du barème IGS2, puis un fichier par
patient. Explications dans [Serveur d'actes et états patient](guide/autres-messages.md#etats-patient-igs2-detaille).

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

## PMSI : un séjour, deux RUM

Le patient passe par deux unités médicales : un RSS à deux RUM. Les deux RUM partagent
le même `identifiant/emetteur` et ne diffèrent que par le récepteur, d'où la colonne
`rum_emetteur`, distincte de la clé `rum_id`. Le médecin responsable et les attributs
`oui`/`non` passent par des colonnes-chemins.

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

## Serveur d'actes : une intervention, quatre actes CCAM

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

## États patient : DP et DR

Les attributs `etat`, `portee` et `referent` des identifiants patient sont produits par
des colonnes-chemins générées en compréhension.

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
