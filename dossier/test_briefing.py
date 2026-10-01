"""Tests du briefing du point quotidien.

Le briefing engage la sécurité d'un point de soins : il doit proposer des
éléments vérifiables, dans le bon ordre, et ne doit jamais formuler de
conclusion clinique. Ces tests verrouillent ces propriétés.
"""

from datetime import date, timedelta

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from dossier.briefing import (
    PRIORITE_HAUTE,
    PRIORITE_IMMEDIATE,
    PRIORITE_NORMALE,
    briefing_du_jour,
    construire_briefing,
)
from dossier.models import Allergie, Bilan, Consultation, Mesure, Patient, Suivi
from dossier.permissions import GROUPE_SECRETARIAT, GROUPE_SOIGNANT


class BriefingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Group

        User = get_user_model()
        cls.soignant = User.objects.create_user("soignant_b", password="MotDePasseLong2026!")
        cls.soignant.groups.add(Group.objects.create(name=GROUPE_SOIGNANT))
        cls.secretaire = User.objects.create_user("secretariat_b", password="MotDePasseLong2026!")
        cls.secretaire.groups.add(Group.objects.create(name=GROUPE_SECRETARIAT))

        aujourdhui = timezone.localdate()

        # Patient 1 : allergie sévère + valeurs hors norme
        cls.p1 = Patient.objects.create(
            nom="Dupont", prenom="Jean", date_naissance=date(1970, 1, 1),
            numero_dossier="INF-0001",
        )
        Allergie.objects.create(
            patient=cls.p1, substance="Pénicilline", reaction="Urticaire", gravite="severe"
        )
        c1 = Consultation.objects.create(patient=cls.p1, date=aujourdhui)
        b1 = Bilan.objects.create(consultation=c1, date=aujourdhui, type_examen="Bilan")
        Mesure.objects.create(
            bilan=b1, parametre="Ferritine", valeur="18", unite="µg/L",
            norme_min=30, norme_max=300,
        )

        # Patient 2 : allergie légère seule — ne doit PAS être immédiate
        cls.p2 = Patient.objects.create(
            nom="Durand", prenom="Paul", date_naissance=date(1980, 1, 1),
            numero_dossier="INF-0002",
        )
        Allergie.objects.create(
            patient=cls.p2, substance="Iode", reaction="Éruption", gravite="legere"
        )

        # Patient 3 : suivi échu
        cls.p3 = Patient.objects.create(
            nom="Martin", prenom="Alain", date_naissance=date(1960, 1, 1),
            numero_dossier="INF-0003",
        )
        Suivi.objects.create(
            patient=cls.p3, description="Relancer la NFS",
            echeance=aujourdhui - timedelta(days=3),
        )

        # Patient 4 : bilan vieux de 2 ans
        cls.p4 = Patient.objects.create(
            nom="Petit", prenom="Marc", date_naissance=date(1975, 1, 1),
            numero_dossier="INF-0004",
        )
        c4 = Consultation.objects.create(patient=cls.p4, date=aujourdhui)
        Bilan.objects.create(
            consultation=c4, date=aujourdhui - timedelta(days=800), type_examen="Bilan"
        )

        # Patient 5 : rien à signaler
        cls.p5 = Patient.objects.create(
            nom="Roux", prenom="Luc", date_naissance=date(1990, 1, 1),
            numero_dossier="INF-0005",
        )

    # ------------------------------------------------------- priorisation

    def test_01_allergie_severe_est_immediate(self):
        lignes = construire_briefing(self.p1)
        allerg = [l for l in lignes if l.categorie == "allergie"]
        self.assertEqual(len(allerg), 1)
        self.assertEqual(allerg[0].priorite, PRIORITE_IMMEDIATE)

    def test_02_allergie_legere_n_est_pas_immediate(self):
        """Une allergie légère ne doit pas remonter en priorité immédiate."""
        lignes = construire_briefing(self.p2)
        self.assertEqual([l for l in lignes if l.categorie == "allergie"], [])

    def test_03_valeur_hors_norme_est_priorite_haute(self):
        lignes = construire_briefing(self.p1)
        bilan = [l for l in lignes if l.categorie == "bilan"]
        self.assertEqual(len(bilan), 1)
        self.assertEqual(bilan[0].priorite, PRIORITE_HAUTE)
        self.assertIn("Ferritine", bilan[0].titre)

    def test_04_suivi_echu_est_signale(self):
        lignes = construire_briefing(self.p3)
        suivis = [l for l in lignes if l.categorie == "suivi"]
        self.assertEqual(len(suivis), 1)
        self.assertIn("Relancer la NFS", suivis[0].titre)

    def test_05_bilan_ancien_est_signale(self):
        lignes = construire_briefing(self.p4)
        frais = [l for l in lignes if l.categorie == "fresqueur"]
        self.assertEqual(len(frais), 1)
        self.assertEqual(frais[0].priorite, PRIORITE_NORMALE)

    def test_06_patient_sans_rien_ne_donne_aucune_ligne(self):
        self.assertEqual(construire_briefing(self.p5), [])

    def test_07_ordre_par_priorite(self):
        b = briefing_du_jour()
        priorites = [l.priorite for l in b["lignes"]]
        self.assertEqual(priorites, sorted(priorites), "les lignes doivent être triées")

    def test_08_immediats_avant_hauts(self):
        b = briefing_du_jour()
        self.assertGreaterEqual(len(b["immediats"]), 1)
        if b["immediats"] and b["hauts"]:
            self.assertLess(
                max(l.priorite for l in b["immediats"]),
                min(l.priorite for l in b["hauts"]),
            )

    def test_09_compteurs_coherents(self):
        b = briefing_du_jour()
        total = len(b["immediats"]) + len(b["hauts"]) + len(b["normaux"])
        self.assertEqual(total, b["nb_lignes"])

    # ------------------------------------------- règle d'or : pas d'inférence

    def test_10_aucune_conclusion_clinique_dans_le_briefing(self):
        """Le briefing signale, il n'interprète pas.

        Toute formulation d'hypothèse clinique serait un risque : le
        personnel verrait une conclusion dans une ligne purement factuelle.
        """
        b = briefing_du_jour()
        interdits = [
            "probablement", "semble", "évoque", "évoquant", "suggestion de",
            "diagnostic probable", "suspicion", "forecaster",
        ]
        for l in b["lignes"]:
            texte = f"{l.titre} {l.detail}".lower()
            for mot in interdits:
                self.assertNotIn(
                    mot, texte,
                    f"le briefing ne doit pas contenir « {mot} » (ligne : {l.titre})",
                )

    def test_11_valeur_non_chiffree_n_est_jamais_normale(self):
        """Une mention qualitative ne doit pas remonter comme point d'attention
        positive : ni signalée comme anormale, ni classée normale."""
        c = Consultation.objects.create(patient=self.p5, date=timezone.localdate())
        b = Bilan.objects.create(consultation=c, date=timezone.localdate())
        m = Mesure.objects.create(bilan=b, parametre="CRP", valeur="négative")
        self.assertEqual(m.anormalite, "inconnu")
        lignes = construire_briefing(self.p5)
        bilan_lines = [l for l in lignes if l.categorie == "bilan"]
        self.assertEqual(
            bilan_lines, [],
            "une valeur non chiffrée ne doit pas produire de ligne de briefing",
        )

    def test_12_chaque_ligne_est_verifiable(self):
        """Chaque ligne renvoie vers une page où l'on peut la vérifier."""
        b = briefing_du_jour()
        for l in b["lignes"]:
            self.assertTrue(
                l.source.startswith("/"),
                f"la ligne « {l.titre} » doit pointer vers une page consultable",
            )

    # ------------------------------------------------------------ accès

    def test_13_soignant_accede_au_briefing(self):
        c = Client()
        c.login(username="soignant_b", password="MotDePasseLong2026!")
        r = c.get(reverse("briefing"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Point quotidien")

    def test_14_secretaire_refuse(self):
        c = Client()
        c.login(username="secretariat_b", password="MotDePasseLong2026!")
        r = c.get(reverse("briefing"))
        self.assertEqual(r.status_code, 403)

    def test_15_anonyme_redirige(self):
        r = Client().get(reverse("briefing"))
        self.assertEqual(r.status_code, 302)

    def test_16_briefing_journalise(self):
        """Consulter le briefing laisse une trace : c'est un accès aux données."""
        from dossier.journalisation import JournalAcces

        JournalAcces.objects.all().delete()
        c = Client()
        c.login(username="soignant_b", password="MotDePasseLong2026!")
        c.get(reverse("briefing"))
        self.assertTrue(
            JournalAcces.objects.filter(objet="briefing du jour").exists(),
            "la consultation du briefing doit être journalisée",
        )
