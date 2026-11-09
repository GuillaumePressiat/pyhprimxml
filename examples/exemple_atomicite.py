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
