"""Tests du journal d'accès.

Le journal est une exigence de traçabilité sur des données de santé. Ces
tests verrouillent deux propriétés :

  1. ce qui doit être tracé l'est (connexions, refus, lectures, exports)
  2. ce qui ne doit JAMAIS l'être (valeurs biologiques, noms de patients) —
     un journal d'audit contenant les résultats serait lui-même un fichier
     de données de santé à protéger.
"""

from datetime import date, timedelta

from django.test import Client, TestCase
from django.urls import reverse

from dossier.journalisation import Action, JournalAcces
from dossier.models import Allergie, Bilan, Consultation, Mesure, Patient
from dossier.permissions import GROUPE_SECRETARIAT, GROUPE_SOIGNANT


class JournalAccesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Group

        User = get_user_model()
        cls.soignant = User.objects.create_user(
            "soignant_j", password="MotDePasseLong2026!"
        )
        cls.soignant.groups.add(Group.objects.create(name=GROUPE_SOIGNANT))
        cls.secretaire = User.objects.create_user(
            "secretariat_j", password="MotDePasseLong2026!"
        )
        cls.secretaire.groups.add(Group.objects.create(name=GROUPE_SECRETARIAT))

        cls.patient = Patient.objects.create(
            nom="Dupont", prenom="Jeanne", date_naissance=date(1980, 4, 1),
            numero_dossier="INF-0001",
        )
        cls.consultation = Consultation.objects.create(
            patient=cls.patient, date=date(2026, 9, 1), soignant=cls.soignant,
            motif="Bilan annuel", diagnostic="Glycémie élevée",
            constantes={"glycemie": "6,8", "pouls": "78"},
        )
        cls.bilan = Bilan.objects.create(
            consultation=cls.consultation, date=date(2026, 9, 1), type_examen="Bilan sanguin"
        )
        Mesure.objects.create(
            bilan=cls.bilan, parametre="Ferritine", valeur="18", unite="µg/L",
            norme_min=30, norme_max=300,
        )
        Allergie.objects.create(patient=cls.patient, substance="Pénicilline", gravite="severe")

    def _soignant(self):
        c = Client()
        c.login(username="soignant_j", password="MotDePasseLong2026!")
        return c

    def _secretaire(self):
        c = Client()
        c.login(username="secretariat_j", password="MotDePasseLong2026!")
        return c

    # -------------------------------------------------- ce qui est tracé

    def test_01_connexion_est_tracee(self):
        JournalAcces.objects.all().delete()
        self._soignant()
        j = JournalAcces.objects.filter(objet="connexion").first()
        self.assertIsNotNone(j, "la connexion doit être journalisée")
        self.assertEqual(j.identifiant_utilisateur, "soignant_j")

    def test_02_echec_connexion_est_trace(self):
        JournalAcces.objects.all().delete()
        c = Client()
        c.post("/connexion/", {"username": "soignant_j", "password": "faux"})
        j = JournalAcces.objects.filter(action=Action.ACCES_REFUSE).first()
        self.assertIsNotNone(j, "un échec de connexion doit laisser une trace")
        self.assertIn("soignant_j", j.details)

    def test_03_lecture_dossier_est_tracee(self):
        JournalAcces.objects.all().delete()
        self._soignant().get(reverse("patient_detail", args=[self.patient.pk]))
        j = JournalAcces.objects.filter(objet="dossier patient").first()
        self.assertIsNotNone(j)
        self.assertEqual(j.numero_dossier, "INF-0001")
        self.assertEqual(j.role, "soignant")

    def test_04_export_synthese_est_trace(self):
        """Un export de données de santé doit laisser une trace nominative."""
        JournalAcces.objects.all().delete()
        self._soignant().get(reverse("synthese_patient", args=[self.patient.pk]))
        j = JournalAcces.objects.filter(objet="synthese exportee").first()
        self.assertIsNotNone(j, "l'export de synthèse doit être journalisé")

    def test_05_refus_acces_est_trace(self):
        """Un secretariat qui tente le dossier clinique laisse une trace."""
        JournalAcces.objects.all().delete()
        c = self._secretaire()
        r = c.get(reverse("patient_detail", args=[self.patient.pk]))
        self.assertEqual(r.status_code, 403)
        j = JournalAcces.objects.filter(action=Action.ACCES_REFUSE).first()
        self.assertIsNotNone(j, "un refus d'accès doit être journalisé")
        self.assertEqual(j.identifiant_utilisateur, "secretariat_j")

    def test_06_creation_consultation_est_tracee(self):
        JournalAcces.objects.all().delete()
        c = self._soignant()
        c.post(
            reverse("consultation_create", args=[self.patient.pk]),
            {"date": "2026-09-28", "motif": "Contrôle", "poids": "70", "taille": "170"},
        )
        j = JournalAcces.objects.filter(action=Action.CREATION).first()
        self.assertIsNotNone(j)

    def test_07_adresse_ip_est_tracee(self):
        JournalAcces.objects.all().delete()
        self._soignant().get(reverse("patient_detail", args=[self.patient.pk]))
        j = JournalAcces.objects.filter(objet="dossier patient").first()
        self.assertIsNotNone(j.adresse_ip, "l'adresse IP doit être journalisée")

    # ------------------------------- ce qui ne doit JAMAIS être tracé

    def test_08_aucune_valeur_clinique_dans_le_journal(self):
        """Aucune valeur biologique ni constante ne doit apparaître."""
        c = self._soignant()
        c.get(reverse("patient_detail", args=[self.patient.pk]))
        c.get(reverse("bilan_detail", args=[self.bilan.pk]))
        c.get(reverse("synthese_patient", args=[self.patient.pk]))

        interdits = ["ferritine", "glycémie", "18", "6,8", "µg/L", "Pénicilline"]
        for j in JournalAcces.objects.all():
            contenu = f"{j.objet} {j.details} {j.numero_dossier}".lower()
            for mot in interdits:
                self.assertNotIn(
                    mot.lower(), contenu,
                    f"le journal ne doit pas contenir « {mot} » (entrée {j.pk})",
                )

    def test_09_aucun_nom_de_patient_dans_le_journal(self):
        """Le journal référence le dossier, il ne recopie pas l'identité."""
        self._soignant().get(reverse("patient_detail", args=[self.patient.pk]))
        for j in JournalAcces.objects.all():
            contenu = f"{j.objet} {j.details} {j.numero_dossier}".lower()
            self.assertNotIn("jeanne", contenu, "le prenom du patient ne doit pas figurer")
            self.assertNotIn("dupont", contenu, "le nom du patient ne doit pas figurer")

    def test_10_chaque_lecture_de_dossier_est_tracee(self):
        """Deux ouvertures = deux entrées : le journal ne déduplique pas."""
        JournalAcces.objects.all().delete()
        c = self._soignant()
        c.get(reverse("patient_detail", args=[self.patient.pk]))
        c.get(reverse("patient_detail", args=[self.patient.pk]))
        self.assertEqual(
            JournalAcces.objects.filter(objet="dossier patient").count(), 2
        )

    def test_11_une_panne_du_journal_ne_bloque_pas_l_acces(self):
        """Si le journal tombe en panne, le soignant doit rester acces."""
        from unittest import mock

        self.assertTrue(self.patient.id)
        c = self._soignant()
        with mock.patch(
            "dossier.audit.JournalAcces.objects.create",
            side_effect=RuntimeError("disque plein"),
        ):
            r = c.get(reverse("patient_detail", args=[self.patient.pk]))
        self.assertEqual(r.status_code, 200, "une panne du journal ne doit pas bloquer l'accès")
