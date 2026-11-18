"""Tests du socle de décision de l'agent.

Ce qui est protégé ici :
  - la simulation n'écrit rien dans les dossiers ;
  - une action hors catalogue ou de classe C est refusée ;
  - une décision réversible peut être annulée, et retire ce qu'elle a créé ;
  - l'agent ne fabrique pas de doublon avec une relance déjà en attente.
"""

from datetime import timedelta
from io import StringIO

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from django.core.management import call_command

from dossier.agent import CATALOGUE, Action, Decision, appliquer, decisions
from dossier.models import (
    Bilan, Consultation, DecisionAgent, Patient, Relance, StatutRelance, Suivi,
)


class SocleAgent(TestCase):
    def setUp(self):
        self.patient = Patient.objects.create(
            nom="Durand", prenom="Léa", date_naissance="1978-03-11",
            numero_dossier="INF-9300",
        )
        Suivi.objects.create(
            patient=self.patient, description="Contrôle de tension",
            echeance=timezone.localdate() - timedelta(days=20), fait=False,
        )
        self.soignant = User.objects.create_user("soignant_agent", password="Mot-De-Passe-2026")
        groupe, _ = Group.objects.get_or_create(name="soignant")
        self.soignant.groups.add(groupe)

    def _commande(self, *args):
        flux = StringIO()
        call_command("agent_decision", *args, stdout=flux)
        return flux.getvalue()

    # ------------------------------------------------------- simulation
    def test_simulation_n_ecrit_aucune_relance(self):
        self._commande()
        self.assertEqual(Relance.objects.count(), 0, "la simulation ne doit rien créer")
        self.assertTrue(DecisionAgent.objects.filter(mode="simulation").exists())
        self.assertFalse(DecisionAgent.objects.filter(mode="appliquee").exists())

    def test_application_cree_un_brouillon(self):
        self._commande("--appliquer")
        relance = Relance.objects.get()
        self.assertEqual(relance.statut, StatutRelance.BROUILLON)
        self.assertIsNone(relance.envoyee_le, "l'agent n'envoie jamais")
        decision = DecisionAgent.objects.get(mode="appliquee")
        self.assertEqual(decision.objet_cree, f"relance#{relance.pk}")

    def test_pas_de_doublon_au_second_passage(self):
        self._commande("--appliquer")
        self._commande("--appliquer")
        self.assertEqual(Relance.objects.count(), 1)

    def test_pas_de_doublon_avec_une_relance_deja_preparee(self):
        """`preparer_relances` a pu déposer le même brouillon avant l'agent."""
        decision = decisions()[0]
        Relance.objects.create(
            patient=decision.patient, type_relance="soin",
            objet=decision.resume[:200], corps="déjà là", motif="",
            statut=StatutRelance.BROUILLON,
        )
        self._commande("--appliquer")
        self.assertEqual(Relance.objects.count(), 1, "l'agent ne double pas une relance")

    # ------------------------------------------------------- catalogue
    def test_action_hors_catalogue_refusee(self):
        decision = Decision(
            regle="test", action=Action("inconnue", "x", "A", True, ""),
            patient=self.patient, resume="test", motif="", corps="",
        )
        with self.assertRaises(ValueError):
            appliquer(decision)

    def test_action_de_classe_c_refusee(self):
        decision = Decision(
            regle="test",
            action=Action("envoi_patient", "Envoi", "C", False, "message au patient"),
            patient=self.patient, resume="test", motif="", corps="",
        )
        with self.assertRaises(ValueError):
            appliquer(decision)

    def test_le_catalogue_ne_contient_aucune_action_de_classe_c(self):
        self.assertTrue(
            all(a.classe in ("A", "B") for a in CATALOGUE.values()),
            "une action engageante ne doit jamais entrer dans le catalogue",
        )

    # ------------------------------------------------------- annulation
    def test_annulation_retire_le_brouillon(self):
        self._commande("--appliquer")
        decision = DecisionAgent.objects.get(mode="appliquee")

        self.client.force_login(self.soignant)
        self.client.post(reverse("agent_annuler", args=[decision.pk]))

        decision.refresh_from_db()
        self.assertIsNotNone(decision.annulee_le)
        self.assertEqual(Relance.objects.count(), 0, "le brouillon doit disparaître")

    def test_annulation_n_efface_pas_une_relance_validee(self):
        """Si un soignant a validé entre-temps, l'agent n'a plus la main."""
        self._commande("--appliquer")
        decision = DecisionAgent.objects.get(mode="appliquee")
        relance = Relance.objects.get()
        relance.statut = StatutRelance.VALIDEE
        relance.save()

        self.client.force_login(self.soignant)
        self.client.post(reverse("agent_annuler", args=[decision.pk]))

        self.assertTrue(Relance.objects.filter(pk=relance.pk).exists())

    def test_page_de_revue_reservee_aux_soignants(self):
        self.client.force_login(self.soignant)
        self.assertEqual(self.client.get(reverse("agent_revue")).status_code, 200)
