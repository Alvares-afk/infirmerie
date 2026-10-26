"""Verifie la connexion complete par formulaire, pour chaque compte.

Sert a confirmer que le formulaire de connexion fonctionne de bout en bout
(session, redirection, acces a l'accueil), pas seulement la fonction
d'authentification.

Usage : python manage.py verifier_connexion
"""

from django.contrib.auth import get_user_model
import os

from django.core.management.base import BaseCommand
from django.test import Client

from dossier import comptes
from dossier.management.commands.seed_demo import MOT_DE_PASSE_DEMO

COMPTES = [
    ("dr.benali", "soignant"),
    ("secretariat", "secrétariat"),
    ("admin", "administrateur"),
]


class Command(BaseCommand):
    help = "Tente une connexion par formulaire pour chaque compte de démonstration."

    def add_arguments(self, parser):
        parser.add_argument(
            "--mot-de-passe",
            help="Mot de passe à essayer pour tous les comptes (vérification "
                 "après un changement volontaire). Sans cette option, le "
                 "fichier acces-comptes.txt est utilisé.",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        mots = comptes.lire()
        # Voir renouveler_mots_de_passe : l'environnement evite que le
        # mot de passe apparaisse dans la ligne de commande du processus.
        impose = options.get("mot_de_passe") or os.environ.get("INFIRMERIE_MDP")
        echecs = 0

        entete = f"{'compte':<14} {'mdp':<6} {'session':<10} {'arrivee':<22} rôle attendu"
        self.stdout.write(entete)
        self.stdout.write("-" * len(entete))

        for username, role_attendu in COMPTES:
            if not User.objects.filter(username=username).exists():
                self.stdout.write(
                    self.style.ERROR(f"{username:<14} COMPTE ABSENT — lancez seed_demo --comptes")
                )
                echecs += 1
                continue

            # Après renouvellement, les mots de passe vivent dans
            # acces-comptes.txt. Le mot de passe de démonstration ne sert plus
            # que de repli tant que le fichier n'existe pas.
            mot_de_passe = impose or mots.get(username, MOT_DE_PASSE_DEMO)

            c = Client()
            r = c.post(
                "/connexion/",
                {"username": username, "password": mot_de_passe},
                follow=True,
            )

            session_ouverte = bool(c.session.get("_auth_user_id"))
            # Une session ouverte doit aboutir a l'accueil, pas a un nouveau formulaire
            sur_accueil = any(
                getattr(url, "url", str(url)) == "/" for url in r.redirect_chain
            ) or (session_ouverte and r.status_code == 200)

            if not (session_ouverte and sur_accueil):
                echecs += 1

            mdp = "ok" if session_ouverte else "NON"
            arrivee = "/" if sur_accueil else f"HTTP {r.status_code}"
            ligne = (
                f"{username:<14} {mdp:<6} "
                f"{'ouverte' if session_ouverte else 'fermee':<10} "
                f"{arrivee:<22} {role_attendu}"
            )
            if session_ouverte and sur_accueil:
                self.stdout.write(ligne)
            else:
                self.stdout.write(self.style.ERROR(ligne))

        self.stdout.write("")
        if echecs:
            self.stdout.write(self.style.ERROR(f"{echecs} compte(s) en échec."))
        else:
            self.stdout.write(self.style.SUCCESS("Tous les comptes se connectent."))
            if impose:
                self.stdout.write("Mot de passe imposé : vérifié sur les trois comptes.")
            elif comptes.FICHIER.exists():
                self.stdout.write(
                    f"Mots de passe individuels : {comptes.FICHIER.name} "
                    f"(à supprimer une fois notés)"
                )
            else:
                self.stdout.write(
                    "Attention : mot de passe de démonstration encore en service. "
                    "Lancez renouveler_mots_de_passe."
                )
