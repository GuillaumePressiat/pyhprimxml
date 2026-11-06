# Écrire depuis des tables

`write_evenements_pmsi` écrit des messages `evenementsPMSI` (RSS MCO), un fichier par
séjour par défaut, à partir de quatre tables reliées par `evt_id` (le séjour, donc le
fichier) et `rum_id` (le RUM).

## Les quatre tables

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
[colonne-chemin](#colonnes-chemins).

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

## Le code complet

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

Les tables peuvent être des DataFrames polars ou pandas. Les dates venues de pandas
(`datetime64`) sont converties selon le type XSD de l'élément cible : un `xsd:date` reçoit
bien `2024-01-01` et non `2024-01-01T00:00:00`.

`rum_id` n'est qu'une clé de jointure. L'identifiant XML du RUM est `rum_emetteur`, qui
vaut `rum_id` par défaut : deux RUM d'un même RSS peuvent avoir le même émetteur.

## Diagnostics : format long, liste ou chaîne

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

## Le fichier produit

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

## Correspondance colonnes → XML

Les valeurs vides (`null`, `NaN`, `""`) sont simplement omises.

| table | colonne | élément / attribut XML | |
|---|---|---|---|
| evenements | `evt_id` | nom du fichier et `enteteMessage/identifiantMessage` ([règle](#identifiant-du-message-nom-du-fichier)) | obligatoire |
| evenements | `ipp`, `ipp_recepteur` | `patient/identifiant/emetteur/valeur`, `recepteur/valeur` | `ipp` obligatoire |
| evenements | `sexe` | `patient/personnePhysique/@sexe` (M, F, I) | obligatoire |
| evenements | `date_naissance` | `patient/personnePhysique/dateNaissance/date` | obligatoire |
| evenements | `nom_usuel`, `nom_naissance`, `prenom` | `patient/personnePhysique/...` | |
| evenements | `nda`, `nda_recepteur` | `venue/identifiant/emetteur/valeur`, `recepteur/valeur` | `nda` obligatoire |
| evenements | `venue_date_entree`, `venue_heure_entree` | `venue/entree/dateHeureOptionnelle` | date obligatoire |
| evenements | `venue_mode_entree`, `venue_uf_responsable` | `venue/entree/modeEntree/code`, `uniteFonctionnelleResponsable/code` | |
| evenements | `venue_date_sortie`, `venue_heure_sortie` | `venue/sortie/dateHeureOptionnelle` | |
| evenements | `rss_emetteur`, `rss_recepteur`, `rss_version` | `rss/identifiantRSS/emetteur`, `recepteur`, `rss/@version` | |
| evenements | `numero_finess` | `evenementPMSI/numeroFiness` | |
| rum | `rum_id` | clé de jointure avec `diagnostics` et `actes` | obligatoire |
| rum | `rum_emetteur`, `rum_recepteur` | `rum/identifiant/emetteur` (défaut : `rum_id`), `recepteur` | |
| rum | `um` | `rum/uniteMedicale/code` | obligatoire |
| rum | `um_date_entree`, `um_heure_entree` | `uniteMedicale/entree/date`, `heure` | date obligatoire |
| rum | `um_mode_entree`, `um_provenance` | `uniteMedicale/entree/@mode`, `@complementMode` | mode obligatoire |
| rum | `um_date_sortie`, `um_heure_sortie` | `uniteMedicale/sortie/date`, `heure` | |
| rum | `um_mode_sortie`, `um_destination` | `uniteMedicale/sortie/@mode`, `@complementMode` | |
| rum | `action` | `rum/@action` (défaut : `creation`) | |
| rum | `date_action` | `rum/dateAction` (défaut : `um_date_entree`) | |
| rum | `igs2`, `nb_seances` | `rum/igs2`, `rum/seance` | |
| diagnostics | `type`, `code` | `diagnostics/diagnosticPrincipal`, `diagnosticRelie`, `diagnosticsSignificatifs`, `diagnosticsDocumentaires` | obligatoires |
| actes | `code`, `phase`, `activite` | `acte/CCAM/codeActe`, `codePhase`, `codeActivite` | obligatoires |
| actes | `quantite` | `CCAM/quantite` (défaut : 1) | |
| actes | `extension_pmsi`, `date_realisation`, `extension_documentaire` | `codeActeExtensionPMSI`, `dateRealisation`, `codeExtensionDocumentaire` | |
| actes | `modificateurs`, `association_non_prevue` | `modificateurs/modificateur`, `codeAssociationNonPrevue` | |
| actes | `remboursement_exceptionnel`, `externe` | `CCAM/@remboursementExceptionnel`, `acte/@externe` | |

Les booléens Python sont écrits `oui` / `non`.

## Colonnes-chemins

Toute colonne dont le nom contient `/` ou commence par `@` est un chemin XML relatif au
nœud que décrit la table ; `@nom` en dernier segment désigne un attribut. Tout élément
du XSD reste ainsi accessible sans colonne dédiée.

| table | nœud de référence | colonne | produit |
|---|---|---|---|
| evenements | `evenementPMSI` | `patient/@anonyme` | `<patient anonyme="non">` |
| evenements | `evenementPMSI` | `venue/@prive` | `<venue prive="non">` |
| rum | `rum` | `@classant` | `<rum classant="non">` |
| rum | `rum` | `medecinResponsable/identification/code` | `<medecinResponsable><identification><code>…` |
| diagnostics | le diagnostic | `codesLibres/codeLibre/code` | `<codesLibres><codeLibre><code>…` |
| actes | `acte` | `CCAM/@remboursementExceptionnel` | `<CCAM remboursementExceptionnel="non">` |

Les valeurs nulles sont ignorées. Un chemin inconnu du XSD fait échouer l'écriture
(voir [l'option `strict`](dictionnaire.md)).

## En-tête du message

Le dictionnaire `entete` accepte `emetteur`, `destinataire`, `emetteur_categorie`,
`destinataire_categorie` (défaut `application`), `mode_traitement`, `acquittement_attendu`,
`commentaire`, `date_heure_production` (défaut : maintenant) et `version`.

Chacune de ces clés peut aussi être une **colonne de `evenements`**, avec une valeur par
événement, qui prime sur le dictionnaire. C'est ce qui permet de réécrire directement des
tables relues, sans repasser d'en-tête.

## Identifiant du message = nom du fichier

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

## Options

Tous les exemples écrivent en **version 2.00**, déclarée une fois dans l'en-tête
(`entete = {"version": "2.00", ...}`). Sans précision, le package écrit en 2.4, la dernière
version publiée ; le paramètre `version=` d'un appel l'emporte sur l'en-tête.

| option | valeurs | effet |
|---|---|---|
| `xmlns` | `hx.HPRIM_NS` (défaut), `None`, `""` | namespace HPRIM ; aucune déclaration ; `xmlns=""` écrit littéralement |
| `validate_xsd` | `"error"` (défaut), `"warn"`, `False` | contrôle de chaque fichier contre son XSD |
| `version` | `"2.4"`, `"2.00"`, … | version du schéma ; sinon colonne `version`, sinon 2.4 |
| `filename` | gabarit ou fonction | nom de chaque fichier |
| `encoding` | `"UTF-8"` (défaut), `"ISO-8859-1"`, … | encodage des fichiers |
| `colmap` | `{"ancien": "nouveau"}` | renommage de colonnes existantes |
| `par_rum` | `False` (défaut), `True` | un fichier par RUM : voir [RUM unitaires](rum-unitaires.md) |
| `identifiant_egal_nom_fichier` | `True` (défaut), `False` | identifiantMessage = nom du fichier sans extension |
| `fichier_ok` | `False` (défaut), `True` | dépose un `.ok` vide une fois chaque `.xml` complet ([dépôts](rum-unitaires.md#depot-complet-les-fichiers-ok)) |

Sans namespace (`None` ou `""`), la validation utilise automatiquement une variante du XSD
sans `targetNamespace`.

Les éléments facultatifs vides sont supprimés ; les éléments complexes obligatoires du XSD
sont conservés même vides. Un RUM sans diagnostic produit ainsi `<diagnostics/>`.

## Performances

Environ 1 500 fichiers par seconde, validation XSD comprise : la validation lxml, écrite
en C, ne change pas le débit.
