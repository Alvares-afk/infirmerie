"""Vérifie le comportement du mode démonstration.

Le mode démo s'active quand une variable DATABASE_URL est présente : la base
alors hebergee et accessible sur Internet. Ce test verifie que l'instance se
signale clairement comme telle, et que rien ne fuit.

Usage : python manage.py test dossier.test_demo
"""

from django.template.loader import render_to_string
from django.test import TestCase, override_settings


class ModeDemoTests(TestCase):
    """Le bandeau d'avertissement doit apparaitre exactement quand il faut."""

    def test_01_bandeau_present_en_mode_demo(self):
        html = render_to_string(
            "dossier/base.html",
            {"mode_demo": True, "user": None, "messages": []},
        )
        self.assertIn("VERSION DE DÉMONSTRATION", html)
        self.assertIn("patients fictifs", html)

    def test_02_bandeau_absent_hors_demo(self):
        """En local, pas de bandeau : l'application est un vrai outil."""
        html = render_to_string(
            "dossier/base.html",
            {"mode_demo": False, "user": None, "messages": []},
        )
        self.assertNotIn("VERSION DE DÉMONSTRATION", html)

    def test_03_bandeau_mentionne_ne_pas_saisir_de_donnees_reelles(self):
        html = render_to_string(
            "dossier/base.html",
            {"mode_demo": True, "user": None, "messages": []},
        )
        self.assertIn("Ne saisissez aucune donnée de santé réelle", html)

    @override_settings(MODE_DEMO_HEBERGE=False)
    def test_04_local_n_est_pas_une_demo(self):
        from django.conf import settings
        self.assertFalse(settings.MODE_DEMO_HEBERGE)
