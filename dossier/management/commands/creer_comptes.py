"""Crée les trois comptes de l'application, sans aucune donnée patient.

Destinée à l'installation sur un poste vierge. `seed_demo` charge aussi des
patients fictifs : pratique pour essayer, dangereux comme étape
d'installation, parce qu'une base de production se retrouverait avec six
dossiers qui n'existent pas.

Les comptes sont créés **sans mot de passe utilisable**. Aucun mot de passe
par défaut ne circule : il faut lancer `renouveler_mots_de_passe` juste
après, sinon personne ne peut se connecter — ce qui est préférable à un
mot de passe connu de tous.

Usage :
    python manage.py creer_comptes
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction

from dossier.permissions import GROUPE_SECRETARIAT, GROUPE_SOIGNANT

COMPTES = [
    ("dr.benali", "Nadia", "Benali", GROUPE_SOIGNANT, False, True),
    ("secretariat", "Accueil", "Infirmerie", GROUPE_SECRETARIAT, False, False),
    ("admin", "Administration", "Infirmerie", None, True, False),
]


class Command(BaseCommand):
    help = "Crée les comptes soignant, secrétariat et administrateur (sans patients)."

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        groupes = {}
        for nom in (GROUPE_SECRETARIAT, GROUPE_SOIGNANT):
            groupes[nom], _ = Group.objects.get_or_create(name=nom)

        crees, existants = [], []
        for identifiant, prenom, nom, groupe, admin, staff in COMPTES:
            utilisateur, nouveau = User.objects.get_or_create(
                username=identifiant,
                defaults={
                    "first_name": prenom,
                    "last_name": nom,
                    "email": f"{identifiant}@infirmerie.local",
                    "is_superuser": admin,
                    "is_staff": staff or admin,
                },
            )
            if nouveau:
                utilisateur.set_unusable_password()
                utilisateur.save(update_fields=["password"])
            if groupe:
                utilisateur.groups.add(groupes[groupe])
            (crees if nouveau else existants).append(identifiant)

        if crees:
            self.stdout.write(self.style.SUCCESS(
                f"{len(crees)} compte(s) créé(s) : {', '.join(crees)}"
            ))
        if existants:
            self.stdout.write(
                f"{len(existants)} compte(s) déjà présent(s), laissé(s) tel(s) quel(s) : "
                f"{', '.join(existants)}"
            )

        self.stdout.write("")
        self.stdout.write(
            "Aucun mot de passe n'a été défini. Étape suivante obligatoire :"
        )
        self.stdout.write("  manage.py renouveler_mots_de_passe")
        self.stdout.write("")
        self.stdout.write("Aucune donnée patient n'a été créée.")
