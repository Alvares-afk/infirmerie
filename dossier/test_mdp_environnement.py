"""Le mot de passe ne doit jamais transiter par la ligne de commande.

Un argument de processus est lisible par tout utilisateur de la session
(gestionnaire de tâches, WMI). Une variable d'environnement, elle, n'est
lisible que par le processus et ses enfants.

Ces tests verrouillent les deux chemins : l'environnement doit suffire, et
la commande ne doit pas exiger `--mot-de-passe`.
"""

import os
from io import StringIO
from unittest import mock

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

PHRASE = "Verification-par-environnement-42"


class MotDePasseParEnvironnement(TestCase):
    def setUp(self):
        self.compte = User.objects.create_user("dr.benali", password="ancien-mot-de-passe")

    def test_renouveler_lit_la_variable_d_environnement(self):
        flux = StringIO()
        with mock.patch.dict(os.environ, {"INFIRMERIE_MDP": PHRASE}):
            call_command("renouveler_mots_de_passe", stdout=flux)

        self.compte.refresh_from_db()
        self.assertTrue(
            self.compte.check_password(PHRASE),
            "le mot de passe imposé par l'environnement doit être appliqué",
        )

    def test_verifier_connexion_lit_la_variable_d_environnement(self):
        flux = StringIO()
        with mock.patch.dict(os.environ, {"INFIRMERIE_MDP": PHRASE}):
            call_command("renouveler_mots_de_passe", stdout=flux)
            sortie = StringIO()
            call_command("verifier_connexion", stdout=sortie)

        # Le test porte sur le compte créé ici : les deux autres ne sont pas
        # dans la base de test, ce n'est pas ce qu'on vérifie.
        self.assertIn("dr.benali      ok", sortie.getvalue())

    def test_l_argument_reste_prioritaire(self):
        """Compatibilité : la ligne de commande fonctionne toujours."""
        flux = StringIO()
        call_command("renouveler_mots_de_passe", "--mot-de-passe", "Argument-Prioritaire-7", stdout=flux)
        self.compte.refresh_from_db()
        self.assertTrue(self.compte.check_password("Argument-Prioritaire-7"))
