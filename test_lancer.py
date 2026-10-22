"""Tests des règles d'adresse locale, sans modifier Windows."""
import io
import unittest
from unittest.mock import patch

import lancer


class AdresseLocaleTests(unittest.TestCase):
    def test_sans_nom_port_8000_meme_si_80_libre(self):
        with patch.object(lancer, "port_libre", return_value=True) as libre:
            self.assertEqual(lancer.choisir_port(False), 8000)
            libre.assert_called_once_with(8000)

    def test_nom_simple_port_80(self):
        with patch.object(lancer, "port_libre", return_value=True):
            self.assertEqual(lancer.choisir_port(True), 80)

    def test_nom_simple_repli_8000(self):
        with patch.object(lancer, "port_libre", side_effect=lambda p: p != 80):
            self.assertEqual(lancer.choisir_port(True), 8000)

    def test_port_8000_occupe_repli_8010(self):
        with patch.object(lancer, "port_libre", side_effect=lambda p: p == 8010):
            self.assertEqual(lancer.choisir_port(False), 8010)

    def test_aucun_port_disponible(self):
        with patch.object(lancer, "port_libre", return_value=False):
            self.assertIsNone(lancer.choisir_port(False))

    def test_nom_dans_commentaire_ignore(self):
        with patch("builtins.open", return_value=io.StringIO("127.0.0.1 localhost # infirmerie\n")):
            self.assertFalse(lancer.nom_enregistre())

    def test_nom_enregistre_insensible_casse(self):
        with patch("builtins.open", return_value=io.StringIO("127.0.0.1 INFIRMERIE # local\n")):
            self.assertTrue(lancer.nom_enregistre())


if __name__ == "__main__":
    unittest.main()