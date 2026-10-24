"""Tests de l'interprétation d'une mesure.

C'est la règle qui décide si un résultat est signalé. Une erreur ici ne
provoque pas de plantage : elle rend une valeur muette, ou rassurante à tort.
"""

from datetime import date

from django.test import TestCase

from dossier.briefing import construire_briefing
from dossier.models import Bilan, Consultation, Mesure, Patient


class Interpretation(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.patient = Patient.objects.create(
            nom="Test", prenom="Interprétation", sexe="F",
            date_naissance=date(1990, 1, 1), numero_dossier="INF-6001",
        )
        cls.consultation = Consultation.objects.create(
            patient=cls.patient, date=date(2026, 10, 1), motif="Contrôle",
        )
        cls.bilan = Bilan.objects.create(
            consultation=cls.consultation, date=date(2026, 10, 1),
            type_examen="Biochimie",
        )

    def _mesure(self, valeur, mini=None, maxi=None, parametre="Paramètre"):
        return Mesure.objects.create(
            bilan=self.bilan, parametre=parametre, valeur=valeur,
            norme_min=mini, norme_max=maxi,
        )

    # --- deux bornes : comportement historique, inchangé -------------------
    def test_deux_bornes(self):
        self.assertEqual(self._mesure("5", 4, 10).anormalite, "normal")
        self.assertEqual(self._mesure("3", 4, 10).anormalite, "bas")
        self.assertEqual(self._mesure("12", 4, 10).anormalite, "haut")

    def test_aux_bornes_exactes(self):
        self.assertEqual(self._mesure("4", 4, 10).anormalite, "normal")
        self.assertEqual(self._mesure("10", 4, 10).anormalite, "normal")

    # --- borne haute seule : l'exception demandée --------------------------
    def test_borne_haute_seule_sous_le_plafond_est_normale(self):
        """« < 37 » veut dire : en dessous, c'est normal. C'est le laboratoire qui l'affirme."""
        mesure = self._mesure("25", maxi=37, parametre="SGOT - ASAT")
        self.assertEqual(mesure.anormalite, "normal")
        self.assertEqual(mesure.libelle_anomalie, "Normal")

    def test_borne_haute_seule_au_dessus_est_haute(self):
        mesure = self._mesure("74", maxi=37, parametre="SGOT - ASAT")
        self.assertEqual(mesure.anormalite, "haut")
        self.assertTrue(mesure.est_anormal)

    # --- borne basse seule : on ne conclut pas ----------------------------
    def test_borne_basse_seule_ne_conclut_pas(self):
        """Au-dessus du minimum, le haut reste non évalué : on ne rassure pas."""
        self.assertEqual(self._mesure("8", mini=4).anormalite, "inconnu")
        self.assertEqual(self._mesure("3", mini=4).anormalite, "bas")

    # --- ni borne, ni valeur chiffrée ------------------------------------
    def test_aucune_borne(self):
        self.assertEqual(self._mesure("5").anormalite, "inconnu")

    def test_valeur_non_chiffree(self):
        self.assertEqual(self._mesure("négatif", 4, 10).anormalite, "inconnu")
        self.assertEqual(self._mesure("traces", maxi=10).anormalite, "inconnu")

    # --- effet sur le briefing -------------------------------------------
    def test_asat_normale_ne_remonte_pas_comme_alerte(self):
        self._mesure("25", maxi=37, parametre="SGOT - ASAT")
        lignes = construire_briefing(self.patient, aujourdhui=date(2026, 10, 2))
        self.assertEqual(
            [l for l in lignes if l.categorie == "bilan"], [],
            "une enzyme sous son plafond ne doit pas produire d'alerte",
        )

    def test_asat_elevee_remonte_comme_alerte(self):
        self._mesure("74", maxi=37, parametre="SGOT - ASAT")
        lignes = construire_briefing(self.patient, aujourdhui=date(2026, 10, 2))
        self.assertEqual(len([l for l in lignes if l.categorie == "bilan"]), 1)
