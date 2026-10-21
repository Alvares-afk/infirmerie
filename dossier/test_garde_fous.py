"""Garde-fous : ce que les tests de comportement ne voient pas.

Un écran peut répondre 200 et rester illisible. Deux défauts réels ont
échappé aux 81 tests précédents :

  - une balise ``{% else %}`` coupée sur deux lignes, que Django n'a pas
    reconnue et qu'il a affichée en clair au milieu de la liste patients ;
  - une glycémie étiquetée « g/L » alors que ses bornes 3,9–6,1 sont des
    mmol/L. Le badge affichait « Normal » sur une valeur qui, en g/L,
    serait une hyperglycémie sévère.

Ces tests contrôlent le **contenu rendu** et la **cohérence des unités**,
pas seulement les codes HTTP.

Exécution : python manage.py test dossier.test_garde_fous
"""

from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from dossier.management.commands.seed_demo import BILANS_TYPE
from dossier.models import (
    Allergie,
    Bilan,
    Consultation,
    Mesure,
    Patient,
    Suivi,
)
from dossier.permissions import GROUPE_SECRETARIAT, GROUPE_SOIGNANT

# Motifs qui ne doivent jamais apparaître dans une page rendue : s'ils sont
# là, le moteur de template n'a pas interprété la balise et l'a recopiée.
from dossier.unites import (
    BALISES_INTERDITES,
    FOURCHETTES_PLAUSIBLES,
    incoherence_unite,
    normaliser,
)


class AucuneBaliseAffichee(TestCase):
    """Le code du template ne doit jamais atteindre l'écran."""

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.soignant = User.objects.create_user(
            "soignant_garde", password="MotDePasseLong2026!"
        )
        cls.soignant.groups.add(Group.objects.create(name=GROUPE_SOIGNANT))
        cls.secretaire = User.objects.create_user(
            "secretaire_garde", password="MotDePasseLong2026!"
        )
        cls.secretaire.groups.add(Group.objects.create(name=GROUPE_SECRETARIAT))

        cls.patient = Patient.objects.create(
            nom="Dupont",
            prenom="Jeanne",
            sexe="F",
            date_naissance=date(1970, 5, 10),
            numero_dossier="INF-9001",
            medecin_traitant="Dr Garde",
            telephone="06 00 00 00 00",
        )
        Allergie.objects.create(
            patient=cls.patient, substance="Pénicilline", gravite="severe"
        )
        cls.consultation = Consultation.objects.create(
            patient=cls.patient,
            date=date(2026, 9, 1),
            soignant=cls.soignant,
            motif="Bilan annuel",
            diagnostic="Suivi de routine",
            constantes={"poids": "62", "taille": "168", "tension": "120/80"},
        )
        Suivi.objects.create(
            patient=cls.patient,
            description="Contrôle dans 6 mois",
            echeance=date(2027, 3, 1),
        )
        cls.bilan = Bilan.objects.create(
            consultation=cls.consultation,
            date=date(2026, 9, 1),
            type_examen="Bilan sanguin",
        )
        Mesure.objects.create(
            bilan=cls.bilan,
            parametre="Ferritine",
            valeur="18",
            unite="µg/L",
            norme_min=30,
            norme_max=300,
        )

    def _pages_soignant(self):
        return [
            ("accueil", reverse("accueil")),
            ("liste patients", reverse("liste_patients")),
            ("recherche", reverse("liste_patients") + "?q=Dupont"),
            ("fiche patient", reverse("patient_detail", args=[self.patient.pk])),
            ("formulaire patient", reverse("patient_create")),
            ("modifier patient", reverse("patient_edit", args=[self.patient.pk])),
            (
                "détail consultation",
                reverse("consultation_detail", args=[self.consultation.pk]),
            ),
            (
                "nouvelle consultation",
                reverse("consultation_create", args=[self.patient.pk]),
            ),
            ("détail bilan", reverse("bilan_detail", args=[self.bilan.pk])),
            (
                "nouveau bilan",
                reverse("bilan_create", args=[self.consultation.pk]),
            ),
            ("point quotidien", reverse("briefing")),
            ("relances", reverse("liste_relances")),
        ]

    def test_aucune_balise_sur_les_pages_soignant(self):
        client = Client()
        client.force_login(self.soignant)
        for nom, url in self._pages_soignant():
            with self.subTest(page=nom):
                r = client.get(url)
                self.assertEqual(r.status_code, 200, f"{nom} ne rend pas 200")
                html = r.content.decode("utf-8", errors="replace")
                for motif in BALISES_INTERDITES:
                    self.assertNotIn(
                        motif,
                        html,
                        f"{nom} : « {motif} » apparaît dans la page rendue. "
                        f"Une balise est probablement coupée sur deux lignes.",
                    )

    def test_aucune_balise_sur_les_pages_du_secretariat(self):
        client = Client()
        client.force_login(self.secretaire)
        for nom, url in [
            ("accueil", reverse("accueil")),
            ("liste patients", reverse("liste_patients")),
            ("formulaire patient", reverse("patient_create")),
            ("modifier patient", reverse("patient_edit", args=[self.patient.pk])),
        ]:
            with self.subTest(page=nom):
                r = client.get(url)
                self.assertEqual(r.status_code, 200, f"{nom} ne rend pas 200")
                html = r.content.decode("utf-8", errors="replace")
                for motif in BALISES_INTERDITES:
                    self.assertNotIn(
                        motif,
                        html,
                        f"{nom} (secrétariat) : « {motif} » apparaît dans la page.",
                    )

    def test_secretariat_refuse_sur_le_dossier_clinique(self):
        """Rappel du verrou : la fiche clinique reste fermée au secrétariat.

        Ce test n'est pas décoratif — il garantit que la liste de pages
        ci-dessus reste honnête. Si un jour la fiche s'ouvre au secrétariat,
        ce test échoue et la décision devra être assumée explicitement.
        """
        client = Client()
        client.force_login(self.secretaire)
        for nom, url in [
            ("fiche patient", reverse("patient_detail", args=[self.patient.pk])),
            (
                "détail consultation",
                reverse("consultation_detail", args=[self.consultation.pk]),
            ),
            ("détail bilan", reverse("bilan_detail", args=[self.bilan.pk])),
        ]:
            with self.subTest(page=nom):
                self.assertEqual(client.get(url).status_code, 403)

    def test_page_connexion_sans_balise(self):
        r = Client().get(reverse("connexion"))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode("utf-8", errors="replace")
        for motif in BALISES_INTERDITES:
            self.assertNotIn(motif, html)


class UnitesCoherentes(TestCase):
    """Une unité fausse rend un résultat dangereux rassurant."""

    def test_donnees_de_demonstration_coherentes(self):
        """Le jeu de démo est ce que l'on montre : il doit être irréprochable."""
        for type_bilan, lignes in BILANS_TYPE.items():
            for parametre, valeur, unite, norme_min, norme_max in lignes:
                with self.subTest(bilan=type_bilan, parametre=parametre):
                    message = incoherence_unite(
                        parametre, unite, norme_min, norme_max
                    )
                    self.assertIsNone(message, message)

    def test_bornes_ordonnees(self):
        for type_bilan, lignes in BILANS_TYPE.items():
            for parametre, valeur, unite, norme_min, norme_max in lignes:
                if norme_min is None or norme_max is None:
                    continue
                with self.subTest(bilan=type_bilan, parametre=parametre):
                    self.assertLess(
                        norme_min,
                        norme_max,
                        f"{parametre} : borne min ≥ borne max ({norme_min} / "
                        f"{norme_max}) — l'interprétation serait inversée.",
                    )

    def test_fourchettes_du_laboratoire_coherentes(self):
        """Les 13 fourchettes réellement chargées doivent passer le contrôle."""
        from dossier.management.commands.charger_references import REFS

        self.assertEqual(len(REFS), 13, "la feuille du laboratoire compte 13 paramètres")
        for code, libelle, unite, norme_min, norme_max, *_ in REFS:
            with self.subTest(code=code):
                message = incoherence_unite(libelle, unite, norme_min, norme_max)
                self.assertIsNone(message, message)

    def test_hemoglobine_glyquee_n_est_pas_une_hemoglobine(self):
        """Le libellé le plus précis doit l'emporter sur le plus général."""
        self.assertIsNone(
            incoherence_unite("Hémoglobine glyquée", "%", 4.0, 6.0),
            "un HbA1c en % est correct et ne doit pas être refusé",
        )
        self.assertIsNotNone(
            incoherence_unite("Hémoglobine glyquée", "g/dL", 4.0, 16.0),
            "un HbA1c en g/dL n'existe pas : c'est l'unité de l'hémoglobine",
        )

    def test_cles_et_unites_declarees_en_forme_normalisee(self):
        """Une clé écrite avec un accent ou un µ serait morte sans le dire."""
        for cle, unites in FOURCHETTES_PLAUSIBLES.items():
            with self.subTest(cle=cle):
                self.assertEqual(
                    cle,
                    normaliser(cle),
                    f"la clé « {cle} » ne sera jamais atteinte : "
                    f"écrire « {normaliser(cle)} »",
                )
                for unite in unites:
                    self.assertEqual(
                        unite,
                        normaliser(unite),
                        f"l'unité « {unite} » ne sera jamais atteinte : "
                        f"écrire « {normaliser(unite)} »",
                    )

    def test_le_controle_detecte_vraiment_l_erreur(self):
        """Un garde-fou qui ne détecte rien ne protège de rien."""
        message = incoherence_unite("Glycémie à jeun", "g/L", 3.9, 6.1)
        self.assertIsNotNone(message, "le contrôle aurait dû refuser g/L pour 3,9–6,1")

        self.assertIsNone(
            incoherence_unite("Glycémie à jeun", "mmol/L", 3.9, 6.1),
            "mmol/L avec 3,9–6,1 est correct et doit passer",
        )
        self.assertIsNone(
            incoherence_unite("Glycémie à jeun", "g/L", 0.7, 1.1),
            "g/L avec 0,70–1,10 est correct et doit passer",
        )

    def test_triglycerides_ne_sont_pas_pris_pour_du_glucose(self):
        """« Triglycérides » contient « glyc » : le contrôle doit les distinguer."""
        self.assertIsNone(
            incoherence_unite("Triglycérides", "g/L", 0.5, 1.5),
            "des triglycérides en g/L sont normaux et ne doivent pas alerter",
        )

    def test_unite_inconnue_signalee(self):
        message = incoherence_unite("Glycémie", "UI/L", 70, 110)
        self.assertIsNotNone(
            message, "une unité absente de la table doit être signalée"
        )
        self.assertIsNone(
            incoherence_unite("Glycémie", "mg/dL", 70, 110),
            "mg/dL est une unité valide pour une glycémie et doit passer",
        )


class MesuresEnBase(TestCase):
    """Contrôle des mesures réellement enregistrées, pas seulement de la démo."""

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.soignant = User.objects.create_user(
            "soignant_mesure", password="MotDePasseLong2026!"
        )
        cls.soignant.groups.add(Group.objects.create(name=GROUPE_SOIGNANT))
        cls.patient = Patient.objects.create(
            nom="Martin",
            prenom="Luc",
            date_naissance=date(1980, 2, 2),
            numero_dossier="INF-9002",
        )
        cls.consultation = Consultation.objects.create(
            patient=cls.patient,
            date=date(2026, 9, 2),
            soignant=cls.soignant,
            motif="Contrôle",
        )
        cls.bilan = Bilan.objects.create(
            consultation=cls.consultation,
            date=date(2026, 9, 2),
            type_examen="Bilan sanguin",
        )

    def test_toute_mesure_en_base_est_coherente(self):
        Mesure.objects.create(
            bilan=self.bilan,
            parametre="Glycémie à jeun",
            valeur="5,4",
            unite="mmol/L",
            norme_min=3.9,
            norme_max=6.1,
        )
        for mesure in Mesure.objects.all():
            with self.subTest(mesure=str(mesure)):
                message = incoherence_unite(
                    mesure.parametre,
                    mesure.unite,
                    mesure.norme_min,
                    mesure.norme_max,
                )
                self.assertIsNone(message, message)

    def test_valeur_numerique_sans_unite_est_signalee(self):
        """Une valeur chiffrée sans unité ne veut rien dire."""
        self.assertIsNotNone(
            incoherence_unite("Ferritine", "", 30, 300),
            "une unité vide doit être signalée pour un paramètre connu",
        )
        self.assertIsNone(
            incoherence_unite("Ferritine", "µg/L", 30, 300),
            "µg/L doit être reconnue malgré le micro-signe",
        )
