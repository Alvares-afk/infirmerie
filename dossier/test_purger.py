"""Tests de la purge des dossiers anciens.

La suppression de données de santé est l'action la plus destructrice de
l'application : elle mérite des tests qui vérifient autant ce qu'elle
supprime que ce qu'elle refuse de supprimer.
"""

from datetime import date, timedelta
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from dossier.journalisation import Action, JournalAcces
from dossier.models import Consultation, Patient


class PurgeDesDossiers(TestCase):
    def setUp(self):
        self.ancien = Patient.objects.create(
            nom="Ancien", prenom="Dossier", date_naissance=date(1950, 1, 1),
            numero_dossier="INF-9001",
        )
        Consultation.objects.create(patient=self.ancien, date=date(2018, 5, 4))

        self.recent = Patient.objects.create(
            nom="Recent", prenom="Dossier", date_naissance=date(1980, 1, 1),
            numero_dossier="INF-9002",
        )
        Consultation.objects.create(
            patient=self.recent, date=timezone.localdate() - timedelta(days=10)
        )

    def _appeler(self, *args):
        flux = StringIO()
        call_command("purger", *args, stdout=flux)
        return flux.getvalue()

    def test_simulation_ne_supprime_rien(self):
        sortie = self._appeler("--avant", "2020-01-01")
        self.assertIn("INF-9001", sortie)
        self.assertNotIn("INF-9002", sortie)
        self.assertEqual(Patient.objects.count(), 2, "la simulation ne doit rien effacer")

    def test_confirmer_supprime_uniquement_les_dossiers_anciens(self):
        self._appeler("--avant", "2020-01-01", "--confirmer")
        self.assertFalse(Patient.objects.filter(numero_dossier="INF-9001").exists())
        self.assertTrue(Patient.objects.filter(numero_dossier="INF-9002").exists())

    def test_la_purge_laisse_une_trace_au_journal(self):
        self._appeler("--avant", "2020-01-01", "--confirmer", "--motif", "conservation 5 ans")
        trace = JournalAcces.objects.filter(action=Action.SUPPRESSION).first()
        self.assertIsNotNone(trace, "une suppression sans trace n'est pas acceptable")
        self.assertIn("conservation 5 ans", trace.objet)

    def test_le_journal_survit_a_la_suppression_du_patient(self):
        """Le journal perd le lien vers la fiche, jamais la référence."""
        self._appeler("--avant", "2020-01-01", "--confirmer")
        trace = JournalAcces.objects.filter(action=Action.SUPPRESSION).first()
        self.assertIsNone(trace.patient, "le patient supprimé ne doit plus être lié")

    def test_date_future_refusee(self):
        futur = (timezone.localdate() + timedelta(days=30)).isoformat()
        with self.assertRaises(CommandError):
            self._appeler("--avant", futur, "--confirmer")
        self.assertEqual(Patient.objects.count(), 2)

    def test_date_illisible_refusee(self):
        with self.assertRaises(CommandError):
            self._appeler("--avant", "01/01/2020")

    def test_un_dossier_sans_activite_n_est_pas_purge_par_surprise(self):
        """Sans consultation, la date retenue est celle de création : un
        dossier créé aujourd'hui ne peut pas être « ancien »."""
        Patient.objects.create(
            nom="Neuf", prenom="Sans actes", date_naissance=date(1990, 1, 1),
            numero_dossier="INF-9003",
        )
        sortie = self._appeler("--avant", "2020-01-01")
        self.assertNotIn("INF-9003", sortie)
