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

import re
import unicodedata
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
BALISES_INTERDITES = ("{%", "{{", "%}", "}}")


def normaliser(texte):
    """Minuscules sans accents, pour comparer des libellés saisis à la main."""
    # µ (micro) disparaîtrait à la conversion ASCII : on le ramène à « u »
    # avant, sinon « µmol/L » et « umol/L » ne se reconnaîtraient pas.
    brut = str(texte).replace("µ", "u").replace("μ", "u")
    sans_accents = (
        unicodedata.normalize("NFKD", brut)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    return sans_accents.lower().strip()


# Fourchettes au-delà desquelles l'unité est forcément fausse.
# Clé : fragment de libellé normalisé. Valeur : (borne basse, borne haute)
# plausibles pour cette unité précise.
#
# C'est la table qui aurait attrapé le défaut : une glycémie « g/L » dont la
# borne haute vaut 6,1 sort de (0,2 ; 3,0) — c'est une valeur en mmol/L.
FOURCHETTES_PLAUSIBLES = {
    "glycemie": {
        "g/l": (0.2, 3.0),
        "mmol/l": (1.0, 40.0),
    },
    "triglycerides": {
        "g/l": (0.1, 15.0),
        "mmol/l": (0.1, 20.0),
    },
    "cholesterol": {
        "g/l": (0.5, 8.0),
        "mmol/l": (1.0, 25.0),
    },
    "creatinine": {
        "umol/l": (10.0, 2000.0),
        "mg/l": (1.0, 100.0),
    },
    "ferritine": {
        "ug/l": (0.5, 5000.0),
        "ng/ml": (0.5, 5000.0),
    },
    "hemoglobine": {
        "g/dl": (2.0, 25.0),
        "g/l": (20.0, 250.0),
    },
    "leucocytes": {
        "g/l": (0.01, 100.0),
    },
    "globules blancs": {
        "g/l": (0.01, 100.0),
    },
}


def incoherence_unite(parametre, unite, norme_min, norme_max):
    """Retourne un message si l'unité ne peut pas aller avec ces bornes.

    Ne juge que les paramètres présents dans la table : pour les autres,
    on ne sait rien, donc on ne dit rien. Un garde-fou qui crie au loup sur
    tout finit désactivé.
    """
    libelle = normaliser(parametre)
    unite_basse = normaliser(unite).replace(" ", "")

    for fragment, unites in FOURCHETTES_PLAUSIBLES.items():
        if fragment not in libelle:
            continue
        if unite_basse not in unites:
            return (
                f"unité « {unite} » non reconnue pour {parametre} "
                f"(attendu : {', '.join(sorted(unites))})"
            )
        plancher, plafond = unites[unite_basse]
        for borne, nom in ((norme_min, "min"), (norme_max, "max")):
            if borne is None:
                continue
            if not (plancher <= borne <= plafond):
                return (
                    f"{parametre} en {unite} : borne {nom} {borne} hors de "
                    f"[{plancher} ; {plafond}]. Ces bornes sont probablement "
                    f"exprimées dans une autre unité."
                )
        return None
    return None


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
        message = incoherence_unite("Glycémie", "mg/dL", 70, 110)
        self.assertIsNotNone(
            message, "une unité absente de la table doit être signalée"
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
