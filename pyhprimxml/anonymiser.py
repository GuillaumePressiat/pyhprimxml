"""Anonymisation locale de fichiers HPRIM XML, pour tester sur des fichiers réels.

Principe (identique dans le package R hprimxml, fichiers identiques octet pour octet à graine
égale) :

- chaque fichier reçoit sa propre transformation aléatoire : rien ne relie deux fichiers
  anonymisés ; à l'intérieur d'un fichier, tout reste cohérent (une même valeur donne le même
  remplacement partout dans le fichier) ;
- noms et prénoms (patient, professionnels) sont remplacés par des noms français plausibles
  (faker), le prénom selon le sexe du patient ; ``nomNaissance`` reste égal à ``nomUsuel``
  quand ils l'étaient ;
- les autres valeurs masquées (identifiants, adresses, commentaires…) gardent leur longueur et
  leur nature (chiffre -> chiffre, majuscule -> majuscule, minuscule -> minuscule ; ponctuation
  et espaces conservés ; autre caractère -> X) : les fichiers restent conformes au XSD ;
- toutes les dates (xsd:date, xsd:dateTime) d'un fichier sont décalées d'un même nombre de
  jours : durées et âges sont conservés ; les heures ne changent pas ;
- les attributs (sexe, mode, action…) ne sont jamais modifiés : c'est le XSD qui dit ce qui est
  attribut ou élément ;
- sont masqués les éléments texte situés sous un identifiant (patient, venue, RSS, RUM, acte,
  intervention, recueil, message), les données du patient, les professionnels de santé et les
  commentaires ;
- le nom de fichier est pseudonymisé comme l'identifiant du message ;
- une graine (``graine``) rend le résultat reproductible : réservé à la doc et aux tests.

Ce n'est pas une anonymisation au sens du RGPD : les fichiers restent des données de santé
pseudonymisées (codes, durées, unités peuvent permettre des recoupements). Usage : tests
locaux.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import secrets
import warnings
from pathlib import Path

import lxml.etree as ET

from pyhprimxml.common import Sources, chemin_ok, deposer, iter_sources
from pyhprimxml.faker_noms import NOMS, PRENOMS_F, PRENOMS_M
from pyhprimxml.io.output import to_xml
from pyhprimxml.io.parse import parse_xml
from pyhprimxml.xsd import HPRIM_NS, get_schema

#: Éléments dont tout le contenu texte est masqué (avec leurs descendants)
ELEMENTS_MASQUES = frozenset({
    "identifiant", "identifiantRSS", "identifiantMessage",
    "patient", "medecin", "medecinResponsable", "personne", "acteur",
    "nomUsuel", "nomNaissance", "prenom", "noRPPS", "numeroAdeli",
    "commentaire", "commentaireMessage",
})


#: Éléments remplacés par un faux nom de famille, et par un faux prénom
ELEMENTS_NOMS = frozenset({"nomUsuel", "nomNaissance", "nomMarital"})
ELEMENT_PRENOM = "prenom"


def _hmac(cle: str, message: str) -> bytes:
    return hmac.new(cle.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()


def _choix(liste: tuple, cle: str, message: str) -> str:
    return liste[int.from_bytes(_hmac(cle, message)[:4], "big") % len(liste)]


def faux_nom(valeur: str, cle: str) -> str:
    """Faux nom de famille, tiré de la liste des noms courants (même valeur -> même nom)."""
    return _choix(NOMS, cle, f"nom|{valeur}")


def faux_prenom(valeur: str, cle: str, sexe: str | None = None) -> str:
    """Faux prénom, féminin si ``sexe == "F"``, masculin si ``"M"``, sinon dans les deux listes."""
    liste = PRENOMS_F if sexe == "F" else PRENOMS_M if sexe == "M" else PRENOMS_F + PRENOMS_M
    return _choix(liste, cle, f"prenom|{valeur}")


def _flux(valeur: str, cle: str, n: int) -> bytes:
    flux, bloc = b"", 0
    while len(flux) < n:
        flux += hmac.new(cle.encode("utf-8"), f"{valeur}|{bloc}".encode("utf-8"),
                         hashlib.sha256).digest()
        bloc += 1
    return flux


def pseudonyme(valeur: str, cle: str) -> str:
    """Pseudonyme d'une valeur pour une clé donnée : même longueur, même nature de caractères.

    Fonction de base de ``anonymiser``, qui tire une clé aléatoire par fichier.
    """
    valeur = str(valeur)
    flux = _flux(valeur, cle, len(valeur))
    sortie = []
    for i, c in enumerate(valeur):
        b = flux[i]
        if "0" <= c <= "9":
            sortie.append(chr(48 + b % 10))
        elif "A" <= c <= "Z":
            sortie.append(chr(65 + b % 26))
        elif "a" <= c <= "z":
            sortie.append(chr(97 + b % 26))
        elif ord(c) < 128:
            sortie.append(c)
        else:
            sortie.append("X")
    return "".join(sortie)


def decalage_jours(cle: str) -> int:
    """Décalage des dates dérivé de la clé : entre -365 et +365 jours, jamais nul."""
    d = int.from_bytes(hmac.new(cle.encode("utf-8"), b"decalage|dates", hashlib.sha256).digest()[:4],
                       "big") % 731 - 365
    return d if d != 0 else 1


def _anonymiser_noeud(valeur, type_name, schema, masquer: bool, champ: str | None,
                      sexe: str | None, cle: str, jours: int):
    if isinstance(valeur, list):
        return [_anonymiser_noeud(v, type_name, schema, masquer, champ, sexe, cle, jours)
                for v in valeur]
    if isinstance(valeur, dict):
        ct = schema.ctype(type_name) if schema.is_complex(type_name) else None
        if ct is not None and "sexe" in ct.attrs and isinstance(valeur.get("sexe"), str):
            sexe = valeur["sexe"]                              # sexe du patient, pour le prénom
        sortie = {}
        for k, v in valeur.items():
            if ct is not None and k in ct.attrs:
                sortie[k] = v                                  # attribut : jamais modifié
            elif k == "#text":
                sortie[k] = _anonymiser_noeud(v, ct.text_type if ct else None, schema, masquer,
                                              champ, sexe, cle, jours)
            else:
                enfant = ct.child_type(k) if ct is not None and k in ct.child_names() else None
                sortie[k] = _anonymiser_noeud(v, enfant, schema, masquer or k in ELEMENTS_MASQUES,
                                              k, sexe, cle, jours)
        return sortie
    if isinstance(valeur, dt.datetime) or isinstance(valeur, dt.date):
        return valeur + dt.timedelta(days=jours)
    if isinstance(valeur, str):
        if champ in ELEMENTS_NOMS:
            return faux_nom(valeur, cle)
        if champ == ELEMENT_PRENOM:
            return faux_prenom(valeur, cle, sexe)
        if masquer:
            return pseudonyme(valeur, cle)
    return valeur


def anonymiser_message(tree: dict, cle: str, jours: int | None = None) -> dict:
    """Anonymise un message lu avec ``parse_xml`` (voir le module pour les règles)."""
    jours = decalage_jours(cle) if jours is None else jours
    racine = next(iter(tree))
    schema = get_schema(str(tree[racine].get("version")), racine)
    return {racine: _anonymiser_noeud(tree[racine], schema.root_type(), schema, False, None, None,
                                      cle, jours)}


def anonymiser(sources: Sources, out_dir: str | Path, *, graine: str | None = None,
               encoding: str = "UTF-8") -> list[Path]:
    """Anonymise des fichiers HPRIM XML pour des tests locaux.

    Chaque fichier est lu, anonymisé et réécrit dans ``out_dir`` sous un nom pseudonymisé,
    avec sa propre transformation aléatoire (faux noms, pseudonymes, décalage des dates) :
    rien ne relie deux fichiers anonymisés. Un fichier ``.ok`` à côté du fichier source est
    reproduit. Le namespace d'origine (HPRIM ou aucun) et la version sont conservés ; les
    éléments vides aussi (``drop_empty=False``), pour rester au plus près de l'original.

    Args:
        sources: fichier(s), dossier ou motif glob.
        out_dir: dossier de sortie.
        graine: rend le résultat reproductible (même graine, même fichier source -> même
            fichier anonymisé). Réservé à la doc et aux tests ; sans graine, chaque appel donne
            un résultat différent.
        encoding: encodage des fichiers écrits.

    Returns:
        La liste des fichiers anonymisés.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    produits = []
    for ident, src in iter_sources(sources):
        if not isinstance(src, Path):
            continue
        cle = secrets.token_hex(16) if graine is None else f"{graine}|{src.name}"
        ns = ET.QName(ET.parse(str(src)).getroot()).namespace
        tree = anonymiser_message(parse_xml(src), cle)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # éléments hors XSD : ignorés, comme à l'écriture
            xml = to_xml(tree, xmlns=HPRIM_NS if ns == HPRIM_NS else None, encoding=encoding,
                         drop_empty=False, strict=False)
        cible = out_dir / f"{pseudonyme(ident, cle)}{src.suffix}"
        if cible in produits:
            raise ValueError(f"{src.name} : le nom anonymisé {cible.name} est déjà pris par un "
                             f"autre fichier du lot ; relancer (ou changer de graine).")
        deposer(cible, xml, fichier_ok=chemin_ok(src).exists())
        produits.append(cible)
    return produits
