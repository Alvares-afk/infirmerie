"""Genere des apercus HTML des ecrans principaux, pour revue hors ligne.

Usage : python generer_apercus.py
Produit des fichiers apercu_*.html a ouvrir dans un navigateur.
"""

import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "conf.settings")
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.test import Client  # noqa: E402

from dossier.models import Bilan, Patient  # noqa: E402


def main():
    User = get_user_model()
    soignant, _ = User.objects.get_or_create(username="dr.benali")
    secretaire, _ = User.objects.get_or_create(username="secretariat")

    patient = Patient.objects.order_by("pk").first()
    bilan = Bilan.objects.filter(consultation__patient=patient).first()

    ecrans = [
        ("apercu_connexion.html", "/connexion/", None),
        ("apercu_accueil.html", "/", soignant),
        ("apercu_accueil_secretaire.html", "/", secretaire),
        ("apercu_patients.html", "/patients/", soignant),
        ("apercu_patient.html", f"/patients/{patient.pk}/", soignant),
        ("apercu_bilan.html", f"/bilans/{bilan.pk}/", soignant),
        ("apercu_consultation_nouvelle.html", f"/patients/{patient.pk}/consultation/nouvelle/", soignant),
        ("apercu_synthese.html", f"/patients/{patient.pk}/synthese/", soignant),
    ]

    for nom_fichier, url, utilisateur in ecrans:
        c = Client()
        if utilisateur:
            c.force_login(utilisateur)
        r = c.get(url)
        contenu = r.content.decode("utf-8")
        with open(nom_fichier, "w", encoding="utf-8") as f:
            f.write(contenu)
        print(f"{nom_fichier:<40} HTTP {r.status_code}  ({len(contenu)} octets)")


if __name__ == "__main__":
    main()
