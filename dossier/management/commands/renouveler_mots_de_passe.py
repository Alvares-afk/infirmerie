"""Renouvelle les mots de passe des comptes.

Les trois comptes partageaient le mot de passe de démonstration, écrit en
clair dans le dépôt : quiconque voit le code connaît les accès.

La commande génère un mot de passe distinct par compte, l'applique, et
l'écrit dans `acces-comptes.txt` — jamais sur la sortie standard. Un mot de
passe affiché dans une conversation y reste ; un fichier se supprime.

Usage :
    python manage.py renouveler_mots_de_passe
    python manage.py renouveler_mots_de_passe --comptes dr.benali secretariat
"""

import secrets

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from dossier import comptes


class Command(BaseCommand):
    help = "Génère un mot de passe distinct par compte et l'écrit dans acces-comptes.txt."

    def add_arguments(self, parser):
        parser.add_argument(
            "--comptes",
            nargs="+",
            help="Identifiants à traiter (par défaut : tous les comptes actifs).",
        )
        parser.add_argument(
            "--longueur",
            type=int,
            default=20,
            help="Longueur des mots de passe générés (20 par défaut).",
        )
        parser.add_argument(
            "--mot-de-passe",
            help="Impose un même mot de passe à tous les comptes traités. "
                 "À réserver à un poste isolé : un mot de passe partagé "
                 "supprime la séparation des rôles dans les faits.",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        utilisateurs = User.objects.filter(is_active=True).order_by("username")
        if options["comptes"]:
            demandes = set(options["comptes"])
            utilisateurs = utilisateurs.filter(username__in=demandes)
            absents = demandes - {u.username for u in utilisateurs}
            if absents:
                raise CommandError(
                    f"Compte(s) introuvable(s) : {', '.join(sorted(absents))}"
                )

        if not utilisateurs:
            raise CommandError("Aucun compte à traiter.")

        generee = []
        impose = options.get("mot_de_passe")
        for utilisateur in utilisateurs:
            # token_urlsafe : aléatoire cryptographique, sans caractère ambigu
            # à recopier depuis un écran.
            mot_de_passe = impose or secrets.token_urlsafe(options["longueur"])
            utilisateur.set_password(mot_de_passe)
            utilisateur.save(update_fields=["password"])
            roles = ", ".join(g.name for g in utilisateur.groups.all())
            if utilisateur.is_superuser:
                roles = "superutilisateur" + (f", {roles}" if roles else "")
            generee.append((utilisateur.username, mot_de_passe, roles or "sans rôle"))

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(f"{len(generee)} mot(s) de passe renouvelé(s).")
        )
        for utilisateur in utilisateurs:
            self.stdout.write(f"  {utilisateur.username}")

        if impose:
            # Mot de passe imposé : il est connu de celui qui l'a demandé.
            # L'écrire dans un fichier n'ajouterait qu'une copie en clair.
            if comptes.FICHIER.exists():
                comptes.FICHIER.unlink()
                self.stdout.write("")
                self.stdout.write(
                    f"Ancien fichier {comptes.FICHIER.name} supprimé : "
                    f"il contenait des mots de passe qui ne servent plus."
                )
            self.stdout.write("")
            self.stdout.write(
                "Mot de passe imposé, commun aux comptes traités. "
                "Il n'a été écrit nulle part."
            )
            return

        fichier = comptes.ecrire(generee)
        self.stdout.write("")
        self.stdout.write(f"Écrits dans : {fichier}")
        self.stdout.write(
            "Ouvrez ce fichier, notez les mots de passe, puis supprimez-le."
        )
        self.stdout.write(
            "Il est ignoré par Git, mais un fichier en clair sur le disque "
            "reste un fichier en clair."
        )
