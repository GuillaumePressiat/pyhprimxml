u = pl.Schema(
    [
        (
            "evenementsPMSI",
            pl.Struct(
                {
                    "acquittementAttendu": pl.String,
                    "version": pl.String,
                    "enteteMessage": pl.Struct(
                        {
                            "modeTraitement": pl.String,
                            "identifiantMessage": pl.String,
                            "dateHeureProduction": pl.String,
                            "emetteur": pl.Struct(
                                {
                                    "agents": pl.Struct(
                                        {
                                            "agent": pl.Struct(
                                                {
                                                    "categorie": pl.String,
                                                    "code": pl.String,
                                                }
                                            )
                                        }
                                    )
                                }
                            ),
                            "destinataire": pl.Struct(
                                {
                                    "agents": pl.Struct(
                                        {"agent": pl.Struct({"categorie": pl.String})}
                                    )
                                }
                            ),
                            "commentaireMessage": pl.String,
                        }
                    ),
                    "evenementPMSI": pl.Struct(
                        {
                            "patient": pl.Struct(
                                {
                                    "anonyme": pl.String,
                                    "confidentiel": pl.String,
                                    "identifiant": pl.Struct(
                                        {
                                            "emetteur": pl.Struct(
                                                {"valeur": pl.String}
                                            ),
                                            "recepteur": pl.Struct(
                                                {"valeur": pl.String}
                                            ),
                                        }
                                    ),
                                    "personnePhysique": pl.Struct(
                                        {
                                            "sexe": pl.String,
                                            "nomUsuel": pl.String,
                                            "nomNaissance": pl.String,
                                            "prenoms": pl.Struct({"prenom": pl.String}),
                                            "dateNaissance": pl.Struct(
                                                {"date": pl.String}
                                            ),
                                        }
                                    ),
                                }
                            ),
                            "venue": pl.Struct(
                                {
                                    "prive": pl.String,
                                    "identifiant": pl.Struct(
                                        {
                                            "emetteur": pl.Struct(
                                                {"valeur": pl.String}
                                            ),
                                            "recepteur": pl.Struct(
                                                {"valeur": pl.String}
                                            ),
                                        }
                                    ),
                                    "entree": pl.Struct(
                                        {
                                            "dateHeureOptionnelle": pl.Struct(
                                                {"date": pl.String, "heure": pl.String}
                                            ),
                                            "modeEntree": pl.Struct(
                                                {"code": pl.String}
                                            ),
                                            "uniteFonctionnelleResponsable": pl.Struct(
                                                {"code": pl.String}
                                            ),
                                        }
                                    ),
                                }
                            ),
                            "rss": pl.Struct(
                                {
                                    "identifiantRSS": pl.Struct(
                                        {"emetteur": pl.String, "recepteur": pl.String}
                                    ),
                                    "rum": pl.List(
                                        pl.Struct(
                                            {
                                                "action": pl.String,
                                                "classant": pl.String,
                                                "prestationInterEtablissementA": pl.String,
                                                "dateAction": pl.String,
                                                "identifiant": pl.Struct(
                                                    {
                                                        "emetteur": pl.String,
                                                        "recepteur": pl.String,
                                                    }
                                                ),
                                                "medecinResponsable": pl.Struct(
                                                    {
                                                        "identification": pl.Struct(
                                                            {"code": pl.String}
                                                        ),
                                                        "personne": pl.Struct(
                                                            {
                                                                "nomUsuel": pl.String,
                                                                "prenoms": pl.Struct(
                                                                    {
                                                                        "prenom": pl.String
                                                                    }
                                                                ),
                                                            }
                                                        ),
                                                    }
                                                ),
                                                "uniteMedicale": pl.Struct(
                                                    {
                                                        "code": pl.String,
                                                        "entree": pl.Struct(
                                                            {
                                                                "mode": pl.String,
                                                                "date": pl.String,
                                                                "heure": pl.String,
                                                            }
                                                        ),
                                                    }
                                                ),
                                                "diagnostics": pl.Struct(
                                                    {
                                                        "diagnosticPrincipal": pl.Struct(
                                                            {"codeCim10": pl.String}
                                                        ),
                                                        "diagnosticRelie": pl.Struct(
                                                            {"codeCim10": pl.String}
                                                        ),
                                                    }
                                                ),
                                                "actes": pl.Struct(
                                                    {
                                                        "acte": pl.List(
                                                            pl.Struct(
                                                                {
                                                                    "externe": pl.String,
                                                                    "CCAM": pl.Struct(
                                                                        {
                                                                            "remboursementExceptionnel": pl.String,
                                                                            "codeActe": pl.String,
                                                                            "codePhase": pl.String,
                                                                            "codeActivite": pl.String,
                                                                            "quantite": pl.String,
                                                                            "dateRealisation": pl.String,
                                                                        }
                                                                    ),
                                                                }
                                                            )
                                                        )
                                                    }
                                                ),
                                                "seance": pl.String,
                                                "radiotherapie": pl.Struct(
                                                    {
                                                        "nombreFaisceau": pl.String,
                                                        "typeDosimetrie": pl.String,
                                                        "typeMachine": pl.String,
                                                    }
                                                ),
                                            }
                                        )
                                    ),
                                }
                            ),
                        }
                    ),
                }
            ),
        )
    ]
)

