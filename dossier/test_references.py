"""Tests des fourchettes de référence.

⚠ Ces tests n'utilisent AUCUNE valeur issue d'un compte rendu réel. Les
bornes de référence sont bien celles du laboratoire chargé — c'est le but
du chargement — mais les valeurs testées sont inventées, choisies pour
tomber du bon côté des bornes.

Pourquoi cette prudence : un dépôt, même privé, reste un lieu de
propagation. Des valeurs réelles associées à leurs fourchettes constituent
un résultat de laboratoire rattachable à une personne, même sans nom.
Rien de tel n'a vocation à être versionné.

Ce que ces tests verrouillent :
  - les bornes chargées sont celles du laboratoire, pas des repères usuels
  - une valeur hors borne est signalée
  - une valeur sans fourchette complète n'est jamais « normale »
"""

from datetime import date

from django.test import TestCase

from dossier.models import Laboratoire, ReferenceIntervalle

# Bornes issues de la feuille du laboratoire : ce sont des valeurs de
# RÉFÉRENCE, pas des résultats. Les nommer ici est le but même du test.
BORNES = [
    ("LEU", "Leucocytes",    "x10^3/mm3", 4,    10),
    ("HB",  "Hémoglobine",  "g/dL",      11.5, 16.5),
    ("HTE", "Hématocrite",  "%",         37,   47),
    ("PLQ", "Plaquettes",   "x10^3/mm3", 150,  400),
    ("LYM", "Lymphocytes",  "%",         20,   45),
    ("NEU", "Neutrophiles", "%",         45,   75),
]

# Valeurs FICTIVES, situées du bon côté des bornes ci-dessus.
CAS = [
    ("LEU", 2.5,  "bas"),
    ("HB",  10.0, "bas"),
    ("HTE", 34.0, "bas"),
    ("PLQ", 120,  "bas"),
    ("LYM", 60.0, "haut"),
    ("NEU", 30.0, "bas"),
    ("HB",  13.0, "normal"),
    ("PLQ", 250,  "normal"),
    ("LEU", 7.0,  "normal"),
]


class FourchettesReferenceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.lab = Laboratoire.objects.create(nom="Laboratoire de test")
        for code, lib, unite, mini, maxi in BORNES:
            ReferenceIntervalle.objects.create(
                laboratoire=cls.lab, code=code, libelle=lib, unite=unite,
                norme_min=mini, norme_max=maxi, date_debut=date.today(),
            )

    def test_01_valeur_basse_detectee(self):
        ref = ReferenceIntervalle.objects.get(code="LEU")
        self.assertEqual(ref.contient(2.5), "bas")

    def test_02_valeur_haute_detectee(self):
        ref = ReferenceIntervalle.objects.get(code="LYM")
        self.assertEqual(ref.contient(60.0), "haut")

    def test_03_valeur_dans_les_normes(self):
        ref = ReferenceIntervalle.objects.get(code="PLQ")
        self.assertEqual(ref.contient(250), "normal")

    def test_04_bornes_du_laboratoire_et_non_des_repheres_usuels(self):
        """Les bornes chargées sont bien celles de la feuille du laboratoire.

        Certains repères usuels placent la basse de l'hémoglobine plus bas
        que cette feuille. Avec un repère générique, une valeur à 11,6
        serait classée normale ; avec 11,5–16,5 elle est signalée basse.
        L'écart existe, et il change ce que le soignant voit à l'écran.
        """
        hb = ReferenceIntervalle.objects.get(code="HB")
        self.assertEqual(hb.norme_min, 11.5)
        self.assertEqual(hb.norme_max, 16.5)
        self.assertEqual(hb.contient(11.6), "normal")  # au-dessus de la borne
        self.assertEqual(hb.contient(11.4), "bas")     # juste sous la borne
        self.assertEqual(hb.contient(11.5), "normal")  # pile sur la borne
        self.assertEqual(hb.contient(17.0), "haut")

    def test_05_une_seule_borne_ne_conclut_pas(self):
        """Un minimum sans maximum ne permet pas de conclure « normal »."""
        partiel = ReferenceIntervalle.objects.create(
            laboratoire=self.lab, code="TEST", libelle="Test partiel",
            norme_min=10, norme_max=None,
        )
        self.assertIsNone(partiel.contient(50))
        self.assertIsNone(partiel.contient(5))

    def test_06_une_fourchette_vide_ne_conclut_pas(self):
        vide = ReferenceIntervalle.objects.create(
            laboratoire=self.lab, code="VIDE", libelle="Sans aucune borne",
            norme_min=None, norme_max=None,
        )
        self.assertFalse(vide.est_applicable)
        self.assertIsNone(vide.contient(42))

    def test_07_parametre_absent_de_la_table(self):
        """Un paramètre non chargé n'existe pas : aucune conclusion possible."""
        self.assertFalse(
            ReferenceIntervalle.objects.filter(code="FERRITINE").exists()
        )

    def test_08_les_unites_sont_conservees(self):
        """L'unité fait partie de la référence, pas de la mesure."""
        self.assertEqual(ReferenceIntervalle.objects.get(code="HB").unite, "g/dL")
        self.assertEqual(ReferenceIntervalle.objects.get(code="LYM").unite, "%")

    def test_09_tous_les_cas_de_la_table(self):
        """Vérifie chaque couple (valeur, résultat) déclaré dans CAS."""
        for code, valeur, attendu in CAS:
            ref = ReferenceIntervalle.objects.get(code=code)
            obtenu = ref.contient(valeur)
            self.assertEqual(
                obtenu, attendu,
                f"{ref.libelle} = {valeur} : attendu {attendu}, obtenu {obtenu}",
            )

    def test_10_les_bornes_sont_bien_celles_de_la_feuille(self):
        """Comparaison explicite, valeur par valeur, avec la feuille."""
        for code, lib, unite, mini, maxi in BORNES:
            ref = ReferenceIntervalle.objects.get(code=code)
            self.assertEqual(ref.libelle, lib)
            self.assertEqual(ref.unite, unite)
            self.assertEqual(ref.norme_min, mini)
            self.assertEqual(ref.norme_max, maxi)
