"""Tests du point du jour en ligne de commande.

C'est la commande qui alimente le message de 6 h. Elle doit respecter trois
règles, chacune testée ici :

  - **ne rien filtrer** : tous les points sont listés, chaque jour ;
  - **ne pas nommer** : le numéro de dossier suffit, le nom est une option
    explicite parce que le message sort du poste ;
  - **ne pas écrire sans le demander** : la commande est en lecture seule
    tant que `--enregistrer` n'est pas passé.
"""

from datetime import date, timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from dossier.briefing import (
    PRIORITE_HAUTE,
    PRIORITE_NORMALE,
    construire_briefing,
)
from dossier.models import Allergie, Consultation, Patient, Signalement, Suivi
from dossier.permissions import GROUPE_SOIGNANT


class SuiviEchuPasseAvant(TestCase):
    """Une échéance dépassée est plus urgente qu'une échéance à venir."""

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.soignant = User.objects.create_user("s1", password="MotDePasseLong2026!")
        cls.soignant.groups.add(Group.objects.create(name=GROUPE_SOIGNANT))
        cls.patient = Patient.objects.create(
            nom="Test", prenom="Suivi", numero_dossier="INF-8001",
            date_naissance=date(1970, 1, 1),
        )
        aujourdhui = timezone.localdate()
        cls.echu = Suivi.objects.create(
            patient=cls.patient, description="Échéance dépassée",
            echeance=aujourdhui - timedelta(days=10),
        )
        cls.a_venir = Suivi.objects.create(
            patient=cls.patient, description="Échéance à venir",
            echeance=aujourdhui + timedelta(days=30),
        )

    def test_echu_est_plus_urgent_que_a_venir(self):
        lignes = construire_briefing(self.patient, aujourdhui=timezone.localdate())
        par_titre = {l.titre: l for l in lignes}

        self.assertEqual(
            par_titre["Échéance dépassée"].priorite, PRIORITE_HAUTE,
            "un suivi échu doit passer en « avant la visite », pas en « à planifier »",
        )
        self.assertEqual(
            par_titre["Échéance à venir"].priorite, PRIORITE_NORMALE,
            "un suivi à venir n'est pas urgent aujourd'hui",
        )


class CommandePointDuJour(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.soignant = User.objects.create_user("s2", password="MotDePasseLong2026!")
        cls.soignant.groups.add(Group.objects.create(name=GROUPE_SOIGNANT))
        cls.patient = Patient.objects.create(
            nom="Dupont", prenom="Jeanne", numero_dossier="INF-8002",
            date_naissance=date(1970, 1, 1),
        )
        Allergie.objects.create(
            patient=cls.patient, substance="Pénicilline", gravite="severe",
            reaction="Urticaire généralisée",
        )

    def _sortie(self, *args):
        flux = StringIO()
        call_command("point_du_jour", *args, stdout=flux)
        return flux.getvalue()

    def test_affiche_le_point_du_jour(self):
        sortie = self._sortie()
        self.assertIn("Point du jour", sortie)
        self.assertIn("Allergie sévère : Pénicilline", sortie)
        self.assertIn("INF-8002", sortie)

    def test_aucun_nom_par_defaut(self):
        sortie = self._sortie()
        self.assertNotIn("Dupont", sortie)
        self.assertNotIn("Jeanne", sortie)
        self.assertNotIn("Urticaire", sortie.replace("Urticaire généralisée", ""),
                         "la réaction détaillée reste hors du message")

    def test_noms_sur_demande_explicite(self):
        sortie = self._sortie("--avec-noms")
        self.assertIn("Dupont", sortie)

    def test_premier_passage_marque_nouveau(self):
        self.assertIn("NOUVEAU", self._sortie())

    def test_apres_enregistrement_plus_rien_n_est_nouveau(self):
        self._sortie("--enregistrer")
        self.assertEqual(Signalement.objects.count(), 1)
        seconde = self._sortie()
        self.assertIn("DÉJÀ SIGNALÉ", seconde)
        self.assertNotIn("NOUVEAU", seconde)
        # Rien n'est filtré pour autant : l'élément reste listé.
        self.assertIn("Allergie sévère : Pénicilline", seconde)

    def test_lecture_seule_sans_option(self):
        self._sortie()
        self.assertEqual(
            Signalement.objects.count(), 0,
            "sans --enregistrer, la commande ne doit rien écrire en base",
        )

    def test_sortie_vide_s_il_n_y_a_rien_a_signaler(self):
        Patient.objects.all().delete()
        self.assertEqual(self._sortie().strip(), "")

    def test_json_exploitable(self):
        import json

        donnees = json.loads(self._sortie("--json"))
        self.assertEqual(donnees["nb_lignes"], len(donnees["elements"]))
        self.assertEqual(donnees["elements"][0]["patient"], "INF-8002")
        self.assertTrue(donnees["elements"][0]["nouveau"])


class SilenceQuandRienNePresse(TestCase):
    """Le canal d'alerte n'est pas un journal d'activité.

    Une consultation sans point d'attention ne produit aucun message. Si on
    envoyait « 1 consultation aujourd'hui » chaque matin, le message
    deviendrait une routine qu'on cesse de lire — et les vraies alertes
    passeraient avec.
    """

    def test_consultation_sans_alerte_n_envoie_rien(self):
        User = get_user_model()
        soignant = User.objects.create_user("s3", password="MotDePasseLong2026!")
        patient = Patient.objects.create(
            nom="Martin", prenom="Luc", numero_dossier="INF-8003",
            date_naissance=date(1980, 1, 1),
        )
        Consultation.objects.create(
            patient=patient, date=timezone.localdate(), soignant=soignant,
            motif="Contrôle",
        )
        flux = StringIO()
        call_command("point_du_jour", stdout=flux)
        self.assertEqual(
            flux.getvalue().strip(), "",
            "aucun point d'attention : le silence est le bon comportement",
        )
