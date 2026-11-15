# pyhprimxml 0.3.0

## Nouveautés

- Écriture des messages HPRIM XML guidée par les XSD officiels embarqués (versions 1.03a à
  2.4) : `to_xml`, `write_xml`, ordre des éléments, attributs, formats et validation donnés
  par le schéma.
- Lecture guidée par le XSD : `parse_xml`, éléments répétables toujours en liste, valeurs
  typées.
- Couche tabulaire (polars ou pandas) pour les trois messages, en écriture et en lecture :
  `write_evenements_pmsi` / `read_evenements_pmsi`, `write_evenements_serveur_actes` /
  `read_evenements_serveur_actes`, `write_evenements_etat_patient` /
  `read_evenements_etat_patient`.
- Atomicité des messages : un message par RUM (`par_rum`), par acte (`par_acte`) ou par
  diagnostic (`par_diagnostic`).
- Actes NGAP dans le serveur d'actes (table `actes_ngap`) : consultations, forfaits
  techniques, biologie avec codes NABM ; un message peut mêler CCAM et NGAP.
- Repère `recueil` (date et UF d'observation) pour les états patient ; un seul repère par
  message, contrôlé avec un message d'erreur explicite.
- Règle identifiant du message = nom du fichier, contrôlée à l'écriture (limite de
  12 caractères, noms uniques).
- Dépôt atomique des fichiers et marqueurs `.ok` (`fichier_ok`), lecture des seuls dépôts
  terminés (`exiger_ok`), suivi des dépôts (`suivi_depots`).
- Diagnostics en format long, en colonne liste ou en chaîne séparée par des virgules.
- Colonnes-chemins (`patient/@anonyme`, `medecinResponsable/noRPPS`…) pour atteindre tout le
  XSD ; `extra` en lecture.
- Anonymisation locale de fichiers pour les tests (`anonymiser`) : faux noms plausibles,
  identifiants masqués au même format, dates décalées, une transformation aléatoire par
  fichier, fichiers toujours conformes au XSD.
- Anciennes versions : valeurs énumérées accordées aux accents près (`création` en 1.0x,
  `creation` en 2.x) ; une colonne facultative vide n'empêche plus d'écrire dans une version
  qui ne la connaît pas.
- Documentation MkDocs (guide, exemples, référence), exemples exécutables comme source unique
  de la doc, workflows GitHub de publication de la doc et des releases.

## Changements d'API

- La table des actes CCAM s'appelle `actes_ccam`, dans le PMSI comme dans le serveur d'actes,
  à côté de `actes_ngap` : argument `actes_ccam` des fonctions d'écriture, clé `actes_ccam`
  des tables relues (et de l'argument `extra`). L'ancien argument `actes` reste accepté, avec
  un avertissement, jusqu'à une prochaine version.

## Corrections

- Le XSD officiel PMSI 1.06, lui-même invalide, lève désormais une erreur explicite
  (`HprimSchemaError`) au lieu d'une erreur brute de lxml.
- Mise en forme du XML par libxml2 (indentation de deux espaces), identique à celle du
  package R hprimxml.

## Licence

- Licence alignée : GNU AGPL-3.0-or-later (le fichier `LICENSE` était en MIT, le
  `pyproject.toml` déclarait un identifiant non SPDX).
