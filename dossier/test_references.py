"""Tests des fourchettes de référence.

Les valeurs de test proviennent d'un compte rendu réel (feuille du
laboratoire). Elles servent à vérifier que l'interprétation détecte les
anomalies que le laboratoire avait lui-même signalées.

Ce que ces tests verrouillent :
  - les bornes chargées sont celles du laboratoire, pas des repères usuels
  - une valeur hors borne est signalée
  - une valeur sans fourchette complète n'est jamais « normale »
"""

from datetime import date

from django.test import TestCase

from dossier.models import Laboratoire, ReferenceIntervalle


class FourchettesReferenceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.lab = Laboratoire.objects.create(nom="Laboratoire de test")
        for code, lib, unite, mini, maxi in [
            ("LEU", "Leucocytes", "x10^3/mm3", 4, 10),
            ("HB", "Hémoglobine", "g/dL", 11.5, 16.5),
            ("PLQ", "Plaquettes", "x10^3/mm3", 150, 400),
            ("LYM", "Lymphocytes", "%", 20, 45),
        ]:
            ReferenceIntervalle.objects.create(
                laboratoire=cls.lab, code=code, libelle=lib, unite=unite,
                norme_min=mini, norme_max=maxi, date_debut=date.today(),
            )

    def test_01_valeur_basse_detectee(self):
        ref = ReferenceIntervalle.objects.get(code="LEU")
        self.assertEqual(ref.contient(1.1), "bas")

    def test_02_valeur_haute_detectee(self):
        ref = ReferenceIntervalle.objects.get(code="LYM")
        self.assertEqual(ref.contient(57), "haut")

    def test_03_valeur_dans_les_normes(self):
        ref = ReferenceIntervalle.objects.get(code="PLQ")
        self.assertEqual(ref.contient(250), "normal")

    def test_04_bornes_du_laboratoire_et_non_des_repheres_usuels(self):
        """Les bornes chargées sont bien celles de la feuille du laboratoire.

        Valeurs vérifiées sur le modèle : 11,4 → bas, 11,5 → normal
        (pile sur la borne basse), 11,6 et 12,0 → normal, 17,0 → haut.
        """
        hb = ReferenceIntervalle.objects.get(code="HB")
        self.assertEqual(hb.norme_min, 11.5)
        self.assertEqual(hb.norme_max, 16.5)
        self.assertEqual(hb.contient(11.4), "bas")
        self.assertEqual(hb.contient(11.5), "normal")  # pile sur la borne
        self.assertEqual(hb.contient(11.6), "normal")
        self.assertEqual(hb.contient(10.5), "bas")     # valeur de la feuille
        self.assertEqual(hb.contient(17.0), "haut")

    def test_05_une_seule_borne_ne_conclut_pas(self):
        """Un minimum sans maximum ne permet pas de conclure « normal »."""
        partiel = ReferenceIntervalle.objects.create(
            laboratoire=self.lab, code="TEST", libelle="Test partiel",
            norme_min=10, norme_max=None,
        )
        self.assertIsNone(partiel.contient(50))

    def test_06_une_seule_borne_peut_encore_signaler_un_bord(self):
        """Avec un minimum seul, une valeur trop basse reste détectable."""
        partiel = ReferenceIntervalle.objects.create(
            laboratoire=self.lab, code="TEST2", libelle="Test min seul",
            norme_min=10, norme_max=None,
        )
        self.assertEqual(partiel.contient(5), None)  # incomplet -> pas de conclusion
        self.assertEqual(partiel.contient(50), None)

    def test_07_parametre_absent_de_la_table(self):
        """Un paramètre non chargé ne doit pas être classé normal."""
        self.assertFalse(
            ReferenceIntervalle.objects.filter(code="FERRITINE").exists()
        )

    def test_08_les_bornees_sont_adaptes_a_lunite(self):
        """Les unités sont conservées : une valeur sans unité n'a pas de sens."""
        hb = ReferenceIntervalle.objects.get(code="HB")
        self.assertEqual(hb.unite, "g/dL")
        lym = ReferenceIntervalle.objects.get(code="LYM")
        self.assertEqual(lym.unite, "%")
