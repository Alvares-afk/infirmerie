"""Tests de la préparation automatique des relances.

Ce que ces tests protègent : l'automatisation ne doit jamais envoyer ni
valider un message, et relancer la commande ne doit pas empiler des
brouillons identiques.
"""

from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from dossier.models import (
    Bilan, Consultation, Patient, Relance, StatutRelance, Suivi,
)


class PreparationDesRelances(TestCase):
    def setUp(self):
        self.patient = Patient.objects.create(
            nom="Test", prenom="Relance", date_naissance="1970-01-01",
            numero_dossier="INF-9100",
        )
        self.consultation = Consultation.objects.create(patient=self.patient)
        self.bilan = Bilan.objects.create(
            consultation=self.consultation,
            date=timezone.localdate() - timedelta(days=500),
        )
        self.suivi = Suivi.objects.create(
            patient=self.patient, description="Contrôle à faire",
            echeance=timezone.localdate() - timedelta(days=30), fait=False,
        )

    def _appeler(self, *args):
        flux = StringIO()
        call_command("preparer_relances", *args, stdout=flux)
        return flux.getvalue()

    def test_essai_ne_cree_rien(self):
        sortie = self._appeler("--essai")
        self.assertIn("INF-9100", sortie)
        self.assertEqual(Relance.objects.count(), 0)

    def test_cree_des_brouillons_sans_jamais_envoyer(self):
        self._appeler()
        relances = Relance.objects.all()
        self.assertGreaterEqual(relances.count(), 2, "suivi en retard + bilan ancien")
        for relance in relances:
            self.assertEqual(relance.statut, StatutRelance.BROUILLON)
            self.assertIsNone(relance.envoyee_le, "aucun envoi automatique")
            self.assertIsNone(relance.validee_le, "aucune validation automatique")

    def test_relancer_ne_double_pas(self):
        self._appeler()
        avant = Relance.objects.count()
        self._appeler()
        self.assertEqual(Relance.objects.count(), avant, "pas de doublon")

    def test_un_suivi_deja_fait_ne_declenche_rien(self):
        self.suivi.fait = True
        self.suivi.save()
        Bilan.objects.all().delete()
        self._appeler()
        self.assertEqual(Relance.objects.count(), 0)

    def test_anomalies_seulement_si_demande(self):
        """Sans --avec-anomalies, aucune relance ne porte sur un chiffre :
        une valeur hors bornes n'est pas un diagnostic."""
        self.suivi.delete()
        Bilan.objects.all().delete()
        self._appeler()
        self.assertEqual(Relance.objects.count(), 0)
