"""Tests des relances.

Property central de la spec LAB 04 : les relances restent « en attente de
validation (sans envoi automatique) ». Ces tests verrouillent ce point,
ainsi que la règle d'or : une relance ne cite que des faits existants.

Un test vérifie explicitement qu'aucun appel réseau ne peut partir de
l'application : si quelqu'un ajoute un envoi automatique plus tard, il
faudra supprimer ce test — et le Saur.
"""

from datetime import date, timedelta

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from dossier.models import (
    Bilan, Consultation, Patient, Relance, StatutRelance, Suivi,
)
from dossier.permissions import GROUPE_SECRETARIAT, GROUPE_SOIGNANT
from dossier.relances import proposer_relances, proposer_relances_global


class RelancesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Group

        User = get_user_model()
        cls.soignant = User.objects.create_user("soignant_r", password="MotDePasseLong2026!")
        cls.soignant.groups.add(Group.objects.create(name=GROUPE_SOIGNANT))
        cls.secretaire = User.objects.create_user("secretariat_r", password="MotDePasseLong2026!")
        cls.secretaire.groups.add(Group.objects.create(name=GROUPE_SECRETARIAT))

        aujourdhui = timezone.localdate()

        # Patient 1 : suivi échu -> relance justifiée
        cls.p_echu = Patient.objects.create(
            nom="Dupont", prenom="Jean", date_naissance=date(1970, 1, 1),
            numero_dossier="INF-0001",
        )
        Suivi.objects.create(
            patient=cls.p_echu, description="Relancer la NFS de contrôle",
            echeance=aujourdhui - timedelta(days=5),
        )

        # Patient 2 : bilan vieux de 2 ans -> relance justifiée
        cls.p_bilan = Patient.objects.create(
            nom="Durand", prenom="Paul", date_naissance=date(1980, 1, 1),
            numero_dossier="INF-0002",
        )
        c = Consultation.objects.create(patient=cls.p_bilan, date=aujourdhui - timedelta(days=800))
        Bilan.objects.create(consultation=c, date=aujourdhui - timedelta(days=800))

        # Patient 3 : tout est à jour -> AUCUNE relance
        cls.p_ras = Patient.objects.create(
            nom="Martin", prenom="Alain", date_naissance=date(1990, 1, 1),
            numero_dossier="INF-0003",
        )
        c3 = Consultation.objects.create(patient=cls.p_ras, date=aujourdhui)
        Bilan.objects.create(consultation=c3, date=aujourdhui)
        Suivi.objects.create(
            patient=cls.p_ras, description="Contrôle dans 6 mois",
            echeance=aujourdhui + timedelta(days=180),
        )

    # ------------------------------------------------- rien sans motif

    def test_01_patient_a_jour_ne_donne_aucune_relance(self):
        creees = proposer_relances(self.p_ras)
        self.assertEqual(creees, [], "aucun fait ne justifie une relance ici")

    def test_02_suivi_echu_donne_une_relance(self):
        creees = proposer_relances(self.p_echu)
        objets = [r.objet for r in creees]
        self.assertTrue(
            any("Relancer la NFS" in o for o in objets),
            f"la relance du suivi échu doit être rédigée, obtenu : {objets}",
        )
        # Ce patient n'a par ailleurs aucune consultation : une seconde
        # relance (premier rendez-vous) est donc elle aussi justifiée.

    def test_03_bilan_ancien_donne_une_relance(self):
        creees = proposer_relances(self.p_bilan)
        bilans = [r for r in creees if r.type_relance == "bilan"]
        self.assertEqual(len(bilans), 1)
        self.assertIn("Bilan de santé à renouveler", bilans[0].objet)

    def test_04_chaque_relance_a_un_motif(self):
        """Pas de relance sans motif : c'est le seul qui justifie son
        existence. Une relance sans raison serait du bruit."""
        for r in Relance.objects.all():
            self.assertTrue(r.motif.strip(), f"« {r.objet} » n'a pas de motif")

    def test_05_pas_de_doublon(self):
        """Relancer deux fois ne doit pas créer deux fois la même relance."""
        proposer_relances(self.p_echu)
        avant = Relance.objects.filter(patient=self.p_echu).count()
        proposer_relances(self.p_echu)
        apres = Relance.objects.filter(patient=self.p_echu).count()
        self.assertEqual(avant, apres)

    # --------------------------------------------- jamais d'envoi automatique

    def test_06_une_relance_rédigee_est_un_brouillon(self):
        r = proposer_relances(self.p_echu)[0]
        self.assertEqual(r.statut, StatutRelance.BROUILLON)
        self.assertIsNone(r.envoyee_le)

    def test_07_aucune_relance_n_est_envoyee_automatiquement(self):
        proposer_relances_global()
        for r in Relance.objects.all():
            self.assertFalse(r.est_envoyee_automatiquement)
            self.assertIsNone(r.envoyee_le)
            self.assertIsNone(r.validee_par)

    def test_08_la_validation_est_humaine(self):
        r = proposer_relances(self.p_echu)[0]
        c = Client()
        c.login(username="soignant_r", password="MotDePasseLong2026!")
        c.post(reverse("relance_valider", args=[r.pk]))
        r.refresh_from_db()
        self.assertEqual(r.statut, StatutRelance.VALIDEE)
        self.assertEqual(r.validee_par.username, "soignant_r")
        self.assertIsNotNone(r.validee_le)
        # Même validée, elle n'est pas envoyée : la validation authorize,
        # elle n'exécute pas.
        self.assertIsNone(r.envoyee_le)

    def test_09_relance_deja_traitee_non_revalidable(self):
        r = proposer_relances(self.p_echu)[0]
        c = Client()
        c.login(username="soignant_r", password="MotDePasseLong2026!")
        c.post(reverse("relance_valider", args=[r.pk]))
        c.post(reverse("relance_valider", args=[r.pk]))
        r.refresh_from_db()
        # La seconde validation ne doit pas changer le validateur
        self.assertEqual(r.validee_par.username, "soignant_r")

    def test_10_abandon_conserve_la_trace(self):
        """Abandonner ne supprime pas : savoir qu'une relance a été refusée
        est une information utile."""
        r = proposer_relances(self.p_echu)[0]
        c = Client()
        c.login(username="soignant_r", password="MotDePasseLong2026!")
        c.post(reverse("relance_abandonner", args=[r.pk]))
        r.refresh_from_db()
        self.assertEqual(r.statut, StatutRelance.ABANDONNEE)
        self.assertTrue(Relance.objects.filter(pk=r.pk).exists())

    # ---------------------------------------- règle d'or : que des faits

    def test_11_aucune_interpretation_clinique_dans_une_relance(self):
        """Une relance ne doit contenir ni diagnostic, ni interprétation
        d'un résultat. Elle reste administrative."""
        proposer_relances_global()
        interdits = [
            "probablement", "semble", "évoque", "diagnostic", "suspicion",
            "votre maladie", "vous souffrez", "pathologie",
        ]
        for r in Relance.objects.all():
            texte = f"{r.objet} {r.corps} {r.motif}".lower()
            for mot in interdits:
                self.assertNotIn(
                    mot, texte,
                    f"la relance « {r.objet} » contient « {mot} »",
                )

    def test_12_les_dates_citees_existent_dans_le_dossier(self):
        """Chaque relance cite une date issue du dossier, pas inventée."""
        relances = proposer_relances_global()
        dates_dossier = set()
        for s in Suivi.objects.all():
            if s.echeance:
                dates_dossier.add(s.echeance.strftime("%d/%m/%Y"))
        for b in Bilan.objects.all():
            dates_dossier.add(b.date.strftime("%d/%m/%Y"))

        for r in relances:
            import re
            citees = re.findall(r"\d{2}/\d{2}/\d{4}", r.corps)
            for d in citees:
                self.assertIn(
                    d, dates_dossier,
                    f"la relance « {r.objet} » cite la date {d}, absente du dossier",
                )

    def test_13_aucun_envoi_reseau_dans_le_code(self):
        """Aucun appel réseau ne doit exister dans le module de rédaction.

        Si quelqu'un ajoute un envoi automatique, ce test échoue : il
        faudra alors supprimer ce test — et le faire sciemment.
        """
        import re
        from pathlib import Path

        source = Path(__file__).resolve().parent / "relances.py"
        texte = source.read_text(encoding="utf-8")
        interdits = [
            "requests", "urllib", "http.client", "smtplib", "sendmail",
            "send_mail", "EmailMessage", "socket",
        ]
        for mot in interdits:
            self.assertNotIn(
                mot, texte,
                f"relances.py ne doit rien envoyer — « {mot} » trouvé",
            )

    # ------------------------------------------------------------ accès

    def test_14_soignant_accede_aux_relances(self):
        c = Client()
        c.login(username="soignant_r", password="MotDePasseLong2026!")
        r = c.get(reverse("liste_relances"))
        self.assertEqual(r.status_code, 200)

    def test_15_secretaire_refuse(self):
        c = Client()
        c.login(username="secretariat_r", password="MotDePasseLong2026!")
        self.assertEqual(c.get(reverse("liste_relances")).status_code, 403)

    def test_16_secretaire_ne_peut_pas_valider(self):
        c = Client()
        c.login(username="secretariat_r", password="MotDePasseLong2026!")
        r = proposer_relances(self.p_echu)[0]
        resp = c.post(reverse("relance_valider", args=[r.pk]))
        self.assertEqual(resp.status_code, 403)
        r.refresh_from_db()
        self.assertEqual(r.statut, StatutRelance.BROUILLON)

    def test_17_generer_est_refuse_au_secretaire(self):
        c = Client()
        c.login(username="secretariat_r", password="MotDePasseLong2026!")
        self.assertEqual(c.post(reverse("relance_generer")).status_code, 403)

    def test_18_anonyme_redirige(self):
        self.assertEqual(Client().get(reverse("liste_relances")).status_code, 302)
