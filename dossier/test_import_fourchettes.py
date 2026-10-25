"""Tests de l'import des fourchettes de référence.

Un fichier de laboratoire ne s'applique que s'il tient debout en entier.
Un import partiel laisserait des paramètres sur les anciennes bornes et
d'autres sur les nouvelles, sans moyen de savoir lesquels.
"""

import tempfile
from datetime import date, timedelta
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from dossier.models import Laboratoire, ReferenceIntervalle

VALIDE = """code;libelle;unite;min;max;sexe;age_min;age_max
GLY;Glycémie à jeun;mmol/L;3,9;6,1;T;;
CREA;Créatinine;µmol/L;60;110;T;;
FER;Ferritine;µg/L;30;300;T;;
"""

FAUTIF = """code;libelle;unite;min;max;sexe;age_min;age_max
GLY;Glycémie à jeun;g/L;3,9;6,1;T;;
HB;Hémoglobine;g/dL;16,5;11,5;T;;
"""

HEMATOLOGIE = """code;libelle;unite;min;max;sexe;age_min;age_max
HB;Hémoglobine;g/dL;12;16;T;;
GB;Globules blancs;G/L;4;10;T;;
"""


class ImportFourchettes(TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.racine = Path(self.dossier.name)

    def tearDown(self):
        self.dossier.cleanup()

    def _fichier(self, contenu, nom="feuille.csv"):
        chemin = self.racine / nom
        chemin.write_text(contenu, encoding="utf-8")
        return str(chemin)

    def _appeler(self, contenu, *args):
        flux = StringIO()
        call_command(
            "importer_fourchettes", self._fichier(contenu), *args, stdout=flux
        )
        return flux.getvalue()

    def test_fichier_valide_charge_les_fourchettes(self):
        self._appeler(VALIDE, "--laboratoire", "Labo Test")
        self.assertEqual(ReferenceIntervalle.objects.count(), 3)
        glycémie = ReferenceIntervalle.objects.get(code="GLY")
        self.assertEqual(glycémie.unite, "mmol/L")
        self.assertEqual(glycémie.norme_min, 3.9)

    def test_unite_incoherente_refuse_tout_le_fichier(self):
        with self.assertRaises(CommandError):
            self._appeler(FAUTIF, "--laboratoire", "Labo Test")
        self.assertEqual(
            ReferenceIntervalle.objects.count(), 0,
            "aucune ligne ne doit être écrite si une seule est fautive",
        )

    def test_bornes_inversees_refusees(self):
        contenu = """code;libelle;unite;min;max;sexe;age_min;age_max
HB;Hémoglobine;g/dL;16,5;11,5;T;;
"""
        with self.assertRaises(CommandError):
            self._appeler(contenu, "--laboratoire", "Labo Test")
        self.assertEqual(ReferenceIntervalle.objects.count(), 0)

    def test_essai_n_ecrit_rien(self):
        self._appeler(VALIDE, "--laboratoire", "Labo Test", "--essai")
        self.assertEqual(ReferenceIntervalle.objects.count(), 0)

    def test_les_anciennes_fourchettes_sont_closes_pas_supprimees(self):
        """Un bilan ancien doit rester interprétable avec ses propres bornes."""
        labo = Laboratoire.objects.create(nom="Labo Test")
        ancienne = ReferenceIntervalle.objects.create(
            laboratoire=labo, code="GLY", libelle="Glycémie à jeun",
            unite="mmol/L", norme_min=3.5, norme_max=6.0, sexe="T",
            date_debut=date(2025, 1, 1),
        )

        self._appeler(VALIDE, "--laboratoire", "Labo Test")

        ancienne.refresh_from_db()
        self.assertEqual(
            ancienne.date_fin, date.today() - timedelta(days=1),
            "l'ancienne fourchette doit être close, pas effacée",
        )
        self.assertEqual(ReferenceIntervalle.objects.filter(code="GLY").count(), 2)
        self.assertTrue(
            ReferenceIntervalle.objects.filter(
                code="GLY", date_fin__isnull=True
            ).exists(),
            "une fourchette en vigueur doit subsister",
        )

    def test_une_seconde_feuille_ne_ferme_pas_les_parametres_absents(self):
        """Le laboratoire remet ses normes par feuilles : hématologie, puis
        biochimie. Importer la seconde ne doit pas effacer la première,
        sinon ces paramètres retombent en « à qualifier » sans bruit."""
        self._appeler(HEMATOLOGIE, "--laboratoire", "Labo Test")
        self._appeler(VALIDE, "--laboratoire", "Labo Test")

        en_vigueur = set(
            ReferenceIntervalle.objects.filter(date_fin__isnull=True)
            .values_list("code", flat=True)
        )
        self.assertIn("HB", en_vigueur, "l'hématologie doit rester en vigueur")
        self.assertIn("GLY", en_vigueur, "la biochimie vient d'être chargée")

    def test_remplacer_tout_ferme_aussi_les_codes_absents(self):
        """Feuille complète : le comportement d'origine reste accessible."""
        self._appeler(HEMATOLOGIE, "--laboratoire", "Labo Test")
        self._appeler(VALIDE, "--laboratoire", "Labo Test", "--remplacer-tout")

        en_vigueur = set(
            ReferenceIntervalle.objects.filter(date_fin__isnull=True)
            .values_list("code", flat=True)
        )
        self.assertNotIn("HB", en_vigueur)
        self.assertIn("GLY", en_vigueur)
