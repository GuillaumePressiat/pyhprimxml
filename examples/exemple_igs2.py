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
    "date_observation": [date(2024, 3, 6)] * 2,   # repère du message (dateObservation)
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
