"""Test de la commande d'installation des comptes.

Elle est utilisée sur le poste du client, une fois, sans supervision. Une
erreur ici ne se voit pas tout de suite : elle se voit le jour où six
patients fictifs apparaissent dans les vrais dossiers, ou quand personne
ne peut se connecter.
"""

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from dossier.models import Patient
from dossier.permissions import GROUPE_SECRETARIAT, GROUPE_SOIGNANT


class CreerComptes(TestCase):
    def _appeler(self):
        flux = StringIO()
        call_command("creer_comptes", stdout=flux)
        return flux.getvalue()

    def test_cree_les_trois_comptes(self):
        self._appeler()
        User = get_user_model()
        self.assertEqual(User.objects.count(), 3)
        for identifiant in ("dr.benali", "secretariat", "admin"):
            self.assertTrue(User.objects.filter(username=identifiant).exists(), identifiant)

    def test_aucun_patient_cree(self):
        self._appeler()
        self.assertEqual(
            Patient.objects.count(), 0,
            "une installation ne doit créer aucun dossier patient",
        )

    def test_aucun_mot_de_passe_utilisable(self):
        self._appeler()
        for utilisateur in get_user_model().objects.all():
            self.assertFalse(
                utilisateur.has_usable_password(),
                f"{utilisateur.username} ne doit pas avoir de mot de passe par défaut",
            )

    def test_roles_attribues(self):
        self._appeler()
        User = get_user_model()
        self.assertIn(
            GROUPE_SOIGNANT, [g.name for g in User.objects.get(username="dr.benali").groups.all()]
        )
        self.assertIn(
            GROUPE_SECRETARIAT,
            [g.name for g in User.objects.get(username="secretariat").groups.all()],
        )
        self.assertTrue(User.objects.get(username="admin").is_superuser)

    def test_relance_ne_casse_rien(self):
        self._appeler()
        sortie = self._appeler()
        self.assertIn("déjà présent", sortie)
        self.assertEqual(get_user_model().objects.count(), 3)
