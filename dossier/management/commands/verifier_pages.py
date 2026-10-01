"""Vérification des écrans réels sur la base de démonstration.

Contrairement au navigateur, ce script utilise le client de test : il rend
chaque vue et signale les erreurs. Sert de contrôle après toute modification.

Usage : python manage.py verifier_pages
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.test import Client
from django.urls import reverse

from dossier.models import Bilan, Consultation, Patient


class Command(BaseCommand):
    help = "Rend chaque écran de l'application et affiche son code de réponse."

    def handle(self, *args, **options):
        User = get_user_model()
        soignant, _ = User.objects.get_or_create(
            username="dr.benali", defaults={"first_name": "Nadia", "last_name": "Benali"}
        )
        secretaire, _ = User.objects.get_or_create(username="secretariat")

        c = Client()
        patient = Patient.objects.order_by("pk").first()
        consultation = Consultation.objects.order_by("pk").first()
        bilan = Bilan.objects.order_by("pk").first()

        pages = [
            ("Connexion", reverse("connexion")),
            ("Accueil (anonyme)", reverse("accueil")),
        ]
        if patient:
            pages += [
                ("Accueil (soignant)", reverse("accueil")),
                ("Liste patients", reverse("liste_patients")),
                ("Recherche", reverse("liste_patients") + "?q=Benali"),
                ("Fiche patient", reverse("patient_detail", args=[patient.pk])),
                ("Formulaire patient", reverse("patient_create")),
                ("Synthèse PDF", reverse("synthese_patient", args=[patient.pk])),
            ]
        if patient and consultation:
            pages += [
                ("Nouvelle consultation", reverse("consultation_create", args=[patient.pk])),
                ("Détail consultation", reverse("consultation_detail", args=[consultation.pk])),
            ]
        if consultation and bilan:
            pages += [
                ("Nouveau bilan", reverse("bilan_create", args=[consultation.pk])),
                ("Détail bilan", reverse("bilan_detail", args=[bilan.pk])),
            ]

        largeur = 28
        self.stdout.write(f"{'page':<{largeur}} {'soignant':>9} {'secrétariat':>11}")
        self.stdout.write("-" * (largeur + 22))

        for titre, url in pages:
            c.force_login(soignant)
            r_s = c.get(url)
            c.logout()

            c.force_login(secretaire)
            r_c = c.get(url)
            c.logout()

            if r_s.status_code not in (200, 302):
                self.stdout.write(
                    self.style.ERROR(f"{titre:<{largeur}} {r_s.status_code:>9} {r_c.status_code:>11}  <- ERREUR")
                )
            else:
                self.stdout.write(f"{titre:<{largeur}} {r_s.status_code:>9} {r_c.status_code:>11}")

