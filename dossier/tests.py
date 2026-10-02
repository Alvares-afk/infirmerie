"""Parcours de vérification : connexion, rôles, pages, création de données.

S'exécute avec : python manage.py test_dossier
Utilise le client de test Django, qui traverse les vraies vues, permissions
et templates. Une erreur de rendu ou de permission fait échouer le test.
"""

from django.test import Client, TestCase
from django.urls import reverse

from dossier.models import Bilan, Consultation, Mesure, Patient, Suivi
from dossier.permissions import GROUPE_SECRETARIAT, GROUPE_SOIGNANT


class ParcoursInfirmerie(TestCase):
    @classmethod
    def setUpTestData(cls):
        from datetime import date

        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Group

        User = get_user_model()
        cls.soignant = User.objects.create_user(
            "soignant_test", password="MotDePasseLong2026!"
        )
        cls.soignant.groups.add(Group.objects.create(name=GROUPE_SOIGNANT))
        cls.secretaire = User.objects.create_user(
            "secretaire_test", password="MotDePasseLong2026!"
        )
        cls.secretaire.groups.add(Group.objects.create(name=GROUPE_SECRETARIAT))

        cls.patient = Patient.objects.create(
            nom="Dupont", prenom="Jean", date_naissance=date(1970, 5, 10),
            numero_dossier="INF-0001", medecin_traitant="Dr Test",
        )
        cls.consultation = Consultation.objects.create(
            patient=cls.patient, date=date(2026, 9, 1), soignant=cls.soignant,
            motif="Bilan annuel", diagnostic="Suivi de routine",
            constantes={"poids": "80", "taille": "180", "tension": "130/80"},
        )
        cls.bilan = Bilan.objects.create(
            consultation=cls.consultation, date=date(2026, 9, 1), type_examen="Bilan sanguin"
        )
        Mesure.objects.create(
            bilan=cls.bilan, parametre="Glycémie", valeur="6,8", unite="g/L",
            norme_min=3.9, norme_max=6.1,
        )
        Mesure.objects.create(
            bilan=cls.bilan, parametre="Créatinine", valeur="78", unite="µmol/L",
            norme_min=60, norme_max=110,
        )
        Suivi.objects.create(
            patient=cls.patient, description="Relancer la NFS", echeance=date(2026, 9, 25)
        )

    # ------------------------------------------------------ authentification

    def test_01_connexion_requise(self):
        """Sans session, la page d'accueil redirige vers la connexion."""
        r = self.client.get(reverse("accueil"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/connexion/", r.url)

    def test_02_connexion_secretaire(self):
        self.assertTrue(
            self.client.login(username="secretaire_test", password="MotDePasseLong2026!")
        )
        r = self.client.get(reverse("accueil"))
        self.assertEqual(r.status_code, 200)

    # ------------------------------------------------------ rôle secrétariat

    def test_03_secretaire_voit_la_liste_patients(self):
        self.client.login(username="secretaire_test", password="MotDePasseLong2026!")
        r = self.client.get(reverse("liste_patients"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Dupont")

    def test_04_secretaire_acces_refuse_au_dossier_clinique(self):
        """Le secretariat ne doit pas lire le dossier clinique, même en URL directe."""
        self.client.login(username="secretaire_test", password="MotDePasseLong2026!")
        r = self.client.get(reverse("patient_detail", args=[self.patient.pk]))
        self.assertEqual(r.status_code, 403)

    def test_05_secretaire_acces_refuse_au_bilan(self):
        self.client.login(username="secretaire_test", password="MotDePasseLong2026!")
        r = self.client.get(reverse("bilan_detail", args=[self.bilan.pk]))
        self.assertEqual(r.status_code, 403)

    def test_06_secretaire_peut_creer_un_patient(self):
        self.client.login(username="secretaire_test", password="MotDePasseLong2026!")
        r = self.client.post(reverse("patient_create"), {
            "nom": "Martin", "prenom": "Claire", "date_naissance": "1988-03-03",
            "sexe": "F", "telephone": "0600000000",
        })
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Patient.objects.filter(nom="Martin").exists())

    # ----------------------------------------------------------- rôle soignant

    def test_07_soignant_accède_au_dossier(self):
        self.client.login(username="soignant_test", password="MotDePasseLong2026!")
        r = self.client.get(reverse("patient_detail", args=[self.patient.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Dupont")

    def test_08_soignant_accède_au_bilan(self):
        self.client.login(username="soignant_test", password="MotDePasseLong2026!")
        r = self.client.get(reverse("bilan_detail", args=[self.bilan.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Glycémie")

    def test_08b_detail_consultation_rend(self):
        """La page de consultation doit s'afficher (patient transmis au template)."""
        self.client.login(username="soignant_test", password="MotDePasseLong2026!")
        r = self.client.get(reverse("consultation_detail", args=[self.consultation.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Bilan annuel")

    def test_09_interpretation_des_valeurs(self):
        """Une valeur hors norme doit être signalée comme anormale."""
        glycemie = Mesure.objects.get(parametre="Glycémie")
        creatinine = Mesure.objects.get(parametre="Créatinine")
        self.assertEqual(glycemie.anormalite, "haut")
        self.assertTrue(glycemie.est_anormal)
        self.assertEqual(creatinine.anormalite, "normal")
        self.assertFalse(creatinine.est_anormal)
        self.assertTrue(self.bilan.a_des_anomalies)

    def test_10_valeur_non_numerique(self):
        """Une valeur non chiffrée n'est pas classée à tort."""
        m = Mesure.objects.create(
            bilan=self.bilan, parametre="CRP", valeur="négative", unite="mg/L"
        )
        self.assertEqual(m.anormalite, "inconnu")
        self.assertFalse(m.est_anormal)

    def test_10b_valeur_sans_norme_nest_jamais_normale(self):
        """Une valeur numérique sans aucune borne de référence ne peut pas
        être classée.

        C'est le cas le plus fréquent tant que les fourchettes ne sont pas
        alignées sur le laboratoire de l'établissement : sans cette règle,
        un résultat dont on ignore la norme s'afficherait comme normal,
        donc rassurant. C'est un risque, pas une commodité.
        """
        m = Mesure.objects.create(
            bilan=self.bilan, parametre="Glycémie", valeur="5,2", unite="g/L"
        )
        self.assertEqual(m.anormalite, "inconnu")
        self.assertFalse(m.est_anormal)

        # Avec une seule borne, seule la comparaison possible est faite :
        # 140 avec un minimum à 60 n'est pas « bas », mais on ne peut pas
        # dire non plus qu'il est « haut » sans borne maximale. Le
        # résultat reste indéterminé, donc « inconnu ».
        m2 = Mesure.objects.create(
            bilan=self.bilan, parametre="Créatinine", valeur="140",
            norme_min=60, norme_max=None,
        )
        self.assertEqual(m2.anormalite, "inconnu")

        m3 = Mesure.objects.create(
            bilan=self.bilan, parametre="Protéine C", valeur="50",
            norme_min=60, norme_max=110,
        )
        self.assertEqual(m3.anormalite, "bas")

    def test_11_imc_calcule(self):
        self.assertAlmostEqual(self.consultation.imc, 24.7, places=1)

    def test_12_age_calcule(self):
        self.assertGreater(self.patient.age, 50)

    def test_13_creation_consultation(self):
        self.client.login(username="soignant_test", password="MotDePasseLong2026!")
        r = self.client.post(
            reverse("consultation_create", args=[self.patient.pk]),
            {
                "date": "2026-09-28", "motif": "Douleur lombaire",
                "diagnostic": "Lombalgie", "prescription": "Paracétamol",
                "tension_arterielle": "125/78", "pouls": "70",
                "temperature": "36.7", "poids": "79", "taille": "180",
            },
        )
        self.assertEqual(r.status_code, 302)
        c = Consultation.objects.filter(motif="Douleur lombaire").first()
        self.assertIsNotNone(c)
        self.assertEqual(c.constantes["tension"], "125/78")

    def test_14_taille_implausible_rejetee(self):
        """Une taille hors limites ne doit pas passer silencieusement."""
        self.client.login(username="soignant_test", password="MotDePasseLong2026!")
        r = self.client.post(
            reverse("consultation_create", args=[self.patient.pk]),
            {"date": "2026-09-28", "motif": "Test", "poids": "70", "taille": "900"},
        )
        self.assertEqual(r.status_code, 200)  # le formulaire est renvoyé avec erreur
        self.assertFormError(r.context["form"], "taille", "Taille hors limites plausibles (50–250 cm).")

    def test_15_creation_bilan_avec_mesures(self):
        self.client.login(username="soignant_test", password="MotDePasseLong2026!")
        # Le formset exige son bloc de gestion : 1 formulaire rempli, 2 vides
        donnees = {
            "date": "2026-09-02", "type_examen": "Bilan lipidique",
            "laboratoire": "BioLab", "compte_rendu": "",
            "mesure-TOTAL_FORMS": "3", "mesure-INITIAL_FORMS": "0",
            "mesure-MIN_NUM_FORMS": "0", "mesure-MAX_NUM_FORMS": "1000",
            "mesure-0-parametre": "LDL", "mesure-0-valeur": "1,62",
            "mesure-0-unite": "g/L", "mesure-0-norme_min": "0",
            "mesure-0-norme_max": "1.3", "mesure-0-reference": "",
            "mesure-1-parametre": "", "mesure-1-valeur": "", "mesure-1-unite": "",
            "mesure-1-norme_min": "", "mesure-1-norme_max": "", "mesure-1-reference": "",
            "mesure-2-parametre": "", "mesure-2-valeur": "", "mesure-2-unite": "",
            "mesure-2-norme_min": "", "mesure-2-norme_max": "", "mesure-2-reference": "",
        }
        r = self.client.post(
            reverse("bilan_create", args=[self.consultation.pk]), donnees
        )
        self.assertEqual(r.status_code, 302)
        b = Bilan.objects.filter(type_examen="Bilan lipidique").first()
        self.assertIsNotNone(b)
        m = b.mesures.first()
        self.assertEqual(m.parametre, "LDL")
        self.assertEqual(m.anormalite, "haut")

    def test_16_synthese_pdf(self):
        self.client.login(username="soignant_test", password="MotDePasseLong2026!")
        r = self.client.get(reverse("synthese_patient", args=[self.patient.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertIn("Dupont", r.content.decode("utf-8"))

    def test_17_suivi_ajout_et_bascule(self):
        self.client.login(username="soignant_test", password="MotDePasseLong2026!")
        r = self.client.post(
            reverse("suivi_add", args=[self.patient.pk]),
            {"description": "Contrôle tension", "echeance": "2026-10-01"},
        )
        self.assertEqual(r.status_code, 302)
        s = Suivi.objects.get(description="Contrôle tension")
        self.client.post(reverse("suivi_toggle", args=[s.pk]))
        s.refresh_from_db()
        self.assertTrue(s.fait)

    def test_18_allergie_ajoutee(self):
        self.client.login(username="soignant_test", password="MotDePasseLong2026!")
        r = self.client.post(
            reverse("allergie_add", args=[self.patient.pk]),
            {"substance": "Pénicilline", "reaction": "Urticaire", "gravite": "severe"},
        )
        self.assertEqual(r.status_code, 302)
        self.assertTrue(self.patient.allergies_known().exists())

    def test_19_recherche_patient(self):
        self.client.login(username="soignant_test", password="MotDePasseLong2026!")
        r = self.client.get(reverse("liste_patients"), {"q": "Dup"})
        self.assertContains(r, "Dupont")
        r2 = self.client.get(reverse("liste_patients"), {"q": "ZZZZ"})
        self.assertNotContains(r2, "Dupont")

    def test_20_numero_dossier_auto(self):
        """Un numéro de dossier est attribué si laissé vide."""
        self.client.login(username="soignant_test", password="MotDePasseLong2026!")
        r = self.client.post(reverse("patient_create"), {
            "nom": "Petit", "prenom": "Marc", "date_naissance": "1975-01-01",
            "sexe": "M", "numero_dossier": "",
        })
        self.assertEqual(r.status_code, 302)
        p = Patient.objects.get(nom="Petit")
        self.assertTrue(p.numero_dossier.startswith("INF-"))
