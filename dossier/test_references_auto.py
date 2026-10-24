"""Tests du remplissage des bornes depuis les fourchettes du laboratoire.

Ce mécanisme décide si une mesure est interprétable. Une borne oubliée la
fait sortir en « à qualifier » — donc muette. Une borne prise au mauvais
sexe fait signaler une anomalie qui n'existe pas.
"""

from datetime import date
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from dossier.models import (
    Bilan,
    Consultation,
    Laboratoire,
    Mesure,
    Patient,
    ReferenceIntervalle,
)
from dossier.references import completer_mesures, fourchette_pour


class RemplissageDesBornes(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.labo = Laboratoire.objects.create(nom="Labo Test")
        cls.homme = Patient.objects.create(
            nom="Martin", prenom="Paul", sexe="M",
            date_naissance=date(1980, 1, 1), numero_dossier="INF-7001",
        )
        cls.femme = Patient.objects.create(
            nom="Durand", prenom="Anne", sexe="F",
            date_naissance=date(1985, 1, 1), numero_dossier="INF-7002",
        )
        # Créatinine : le laboratoire distingue les sexes.
        for sexe, mini, maxi in (("H", 7, 14), ("F", 6, 11)):
            ReferenceIntervalle.objects.create(
                laboratoire=cls.labo, code="CREA", libelle="Créatinine",
                unite="mg/L", norme_min=mini, norme_max=maxi, sexe=sexe,
                date_debut=date(2026, 1, 1),
            )
        ReferenceIntervalle.objects.create(
            laboratoire=cls.labo, code="ASAT", libelle="SGOT - ASAT",
            unite="UI/L", norme_min=None, norme_max=37, sexe="T",
            date_debut=date(2026, 1, 1),
        )

    def _bilan(self, patient):
        consultation = Consultation.objects.create(
            patient=patient, date=date(2026, 10, 1),
            soignant=get_user_model().objects.create_user("s_ref", password="x"),
            motif="Contrôle",
        )
        return Bilan.objects.create(
            consultation=consultation, date=date(2026, 10, 1),
            type_examen="Biochimie",
        )

    def test_borne_du_bon_sexe(self):
        bilan = self._bilan(self.femme)
        mesure = Mesure.objects.create(
            bilan=bilan, parametre="Créatinine", valeur="8",
        )
        completer_mesures(bilan, self.femme)
        mesure.refresh_from_db()
        self.assertEqual((mesure.norme_min, mesure.norme_max), (6, 11))
        self.assertEqual(mesure.unite, "mg/L")

    def test_sexe_masculin(self):
        bilan = self._bilan(self.homme)
        mesure = Mesure.objects.create(
            bilan=bilan, parametre="Créatinine", valeur="9",
        )
        completer_mesures(bilan, self.homme)
        mesure.refresh_from_db()
        self.assertEqual((mesure.norme_min, mesure.norme_max), (7, 14))

    def test_borne_saisie_jamais_ecrasee(self):
        """Le soignant peut retenir une autre valeur : on complète, on ne corrige pas."""
        bilan = self._bilan(self.femme)
        mesure = Mesure.objects.create(
            bilan=bilan, parametre="Créatinine", valeur="8",
            norme_min=5, norme_max=12,
        )
        completer_mesures(bilan, self.femme)
        mesure.refresh_from_db()
        self.assertEqual((mesure.norme_min, mesure.norme_max), (5, 12))

    def test_parametre_inconnu_reste_sans_borne(self):
        bilan = self._bilan(self.femme)
        mesure = Mesure.objects.create(
            bilan=bilan, parametre="Vitamine D", valeur="28",
        )
        completees = completer_mesures(bilan, self.femme)
        mesure.refresh_from_db()
        self.assertIsNone(mesure.norme_min)
        self.assertEqual(completees, 0, "on ne devine pas une norme")

    def test_borne_haute_seule_acceptee(self):
        """Le laboratoire écrit « < 37 » : pas de borne basse, et c'est valable."""
        bilan = self._bilan(self.homme)
        mesure = Mesure.objects.create(
            bilan=bilan, parametre="SGOT - ASAT", valeur="25",
        )
        completer_mesures(bilan, self.homme)
        mesure.refresh_from_db()
        self.assertIsNone(mesure.norme_min)
        self.assertEqual(mesure.norme_max, 37)

    def test_fourchette_ignoree_si_close(self):
        ReferenceIntervalle.objects.create(
            laboratoire=self.labo, code="URE", libelle="Urée", unite="g/L",
            norme_min=0.15, norme_max=0.45, sexe="T",
            date_debut=date(2025, 1, 1), date_fin=date(2025, 12, 31),
        )
        self.assertIsNone(
            fourchette_pour("Urée", self.femme),
            "une fourchette close ne doit plus servir",
        )


class ImportReel(TestCase):
    """Le fichier de biochimie du laboratoire doit passer le contrôle entier."""

    def test_fichier_biochimie_chargeable(self):
        flux = StringIO()
        call_command(
            "importer_fourchettes",
            "fourchettes-biochimie.csv",
            stdout=flux,
        )
        self.assertEqual(
            ReferenceIntervalle.objects.filter(date_fin__isnull=True).count(), 28
        )
        glycémie = ReferenceIntervalle.objects.filter(code="GLY")
        self.assertEqual(
            sorted((r.sexe, r.norme_min) for r in glycémie),
            [("F", 0.6), ("H", 0.7)],
            "les bornes homme et femme doivent être distinctes",
        )
