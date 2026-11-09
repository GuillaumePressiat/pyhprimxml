# Autres façons de lire : xpath et structs polars

Les fonctions `read_*` lisent les messages vers des tables prêtes à l'emploi. Pour explorer
des fichiers sans passer par ces tables, deux autres approches restent documentées par des
pages historiques.

**Interroger des éléments avec xpath** :

- [avec le package python `xml`](../xpath_xml.html), en déclarant le namespace HPRIM par
  un alias dans les expressions xpath ;
- [avec `lxml`](../xpath_lxml.html), en supprimant le namespace avant d'utiliser xpath ;
- [avec R et `xml2`](../xpath_xml_r.html), en supprimant le namespace avant d'utiliser xpath.

**Récupérer les éléments complets en structs polars imbriqués** avec `read_hprimxml`,
puis les aplatir : [page historique](../historique/lecture-structs-polars.html).
