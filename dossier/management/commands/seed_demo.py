"""Données de démonstration : patients, consultations et bilans.

Sert à valider l'écran avec du volume réaliste — anomalies comprises.
Usage : python manage.py seed_demo
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from dossier.models import Allergie, Bilan, Consultation, Mesure, Patient, Suivi
from dossier.permissions import GROUPE_SECRETARIAT, GROUPE_SOIGNANT

# Mot de passe des comptes de démonstration. À changer avant tout usage réel.
MOT_DE_PASSE_DEMO = "Infirmerie2026!"

# (paramètre, valeur, unité, min, max)
BILANS_TYPE = {
    "Bilan sanguin complet": [
        ("Hémoglobine", "13,8", "g/dL", 12.0, 16.0),
        ("Globules blancs", "11,2", "G/L", 4.0, 10.0),   # haut
        ("Plaquettes", "245", "G/L", 150, 400),
        ("Glycémie à jeun", "5,4", "g/L", 3.9, 6.1),
        ("Créatinine", "78", "µmol/L", 60, 110),
        ("ALAT", "22", "UI/L", 10, 50),
        ("Ferritine", "18", "µg/L", 30, 300),             # bas
        ("TSH", "2,1", "mUI/L", 0.4, 4.0),
    ],
    "Bilan lipidique": [
        ("Cholestérol total", "2,35", "g/L", 1.5, 2.0),   # haut
        ("LDL", "1,62", "g/L", None, 1.3),
        ("HDL", "0,58", "g/L", 0.4, None),
        ("Triglycérides", "1,10", "g/L", 0.5, 1.5),
    ],
    "Bilan thyroïdien": [
        ("TSH", "6,4", "mUI/L", 0.4, 4.0),                # haut
        ("T4 libre", "13,1", "pmol/L", 10, 20),
    ],
    "Glycémie veineuse": [
        ("Glycémie", "6,8", "g/L", 3.9, 6.1),
    ],
}

PATIENTS = [
    {
        "nom": "Benali", "prenom": "Amina", "naissance": "1979-04-12", "sexe": "F",
        "tel": "06 12 45 78 90", "medecin": "Dr Ferrand",
        "allergies": [("Pénicilline", "Urticaire généralisée", "severe")],
        "constantes": {"tension": "138/86", "pouls": "78", "temperature": "36.8",
                       "saturation": "98", "poids": "64", "taille": "165"},
        "consultations": [
            (30, "Bilan annuel de suivi", "Hypertension artérielle stable", "Amlodipine 5 mg le matin", "Bilan lipidique"),
            (3, "Fatigue persistante depuis 3 semaines", "Anémie ferriprive à confirmer", "Fer + acide folique", "Bilan sanguin complet"),
        ],
    },
    {
        "nom": "Cherif", "prenom": "Youssef", "naissance": "1965-11-02", "sexe": "M",
        "tel": "06 88 21 09 14", "medecin": "Dr Vasseur",
        "allergies": [("Aspirine", "Bronchospasme", "moderee")],
        "constantes": {"tension": "152/94", "pouls": "88", "temperature": "37.1",
                       "saturation": "96", "poids": "88", "taille": "174"},
        "consultations": [
            (45, "Contrôle tensionnel", "HTA modérée, facteur de risque cardiovasculaire", "Réduction sodée, activité physique", "Bilan lipidique"),
            (12, "Prise de poids et œdèmes des membres inférieurs", "Cardiopathie à évaluer, avis cardiologique demandé", "Furosémide 40 mg", "Bilan sanguin complet"),
        ],
    },
    {
        "nom": "Moreau", "prenom": "Claire", "naissance": "1991-06-25", "sexe": "F",
        "tel": "07 41 66 33 22", "medecin": "Dr Lemaire",
        "allergies": [],
        "constantes": {"tension": "112/70", "pouls": "66", "temperature": "36.5",
                       "saturation": "99", "poids": "58", "taille": "170"},
        "consultations": [
            (8, "Contrôle après 6 mois de traitement", "Hypothyroïdie bien contrôlée", "Lévothyroxine 75 µg, contrôle dans 6 mois", "Bilan thyroïdien"),
        ],
    },
    {
        "nom": "Traoré", "prenom": "Moussa", "naissance": "1983-02-18", "sexe": "M",
        "tel": "06 55 78 90 12", "medecin": "Dr Ferrand",
        "allergies": [("Arachide", "Choc anaphylactique", "severe")],
        "constantes": {"tension": "125/80", "pouls": "72", "temperature": "36.6",
                       "saturation": "98", "poids": "79", "taille": "180"},
        "consultations": [
            (2, "Renouvellement d'ordonnance", "Diabète de type 2 équilibré", "Metformine 850 mg × 2", "Glycémie veineuse"),
        ],
    },
    {
        "nom": "Lemoine", "prenom": "Sylvie", "naissance": "1958-09-30", "sexe": "F",
        "tel": "05 62 11 44 90", "medecin": "Dr Vasseur",
        "allergies": [("Iode", "Eruption cutanée", "legere")],
        "constantes": {"tension": "144/88", "pouls": "82", "temperature": "36.9",
                       "saturation": "97", "poids": "70", "taille": "161"},
        "consultations": [
            (400, "Bilan de santé annuel", "Diabète de type 2 — surveillance rénale", "Metformine 1000 mg", "Bilan sanguin complet"),
            (20, "Douleurs lombaires", "Lombalgie commune, sans drapeau", "Paracétamol, étirements", None),
        ],
    },
    {
        "nom": "Haddad", "prenom": "Karim", "naissance": "1995-12-08", "sexe": "M",
        "tel": "07 90 23 11 45", "medecin": None,
        "allergies": [],
        "constantes": {"tension": "118/74", "pouls": "64", "temperature": "36.4",
                       "saturation": "99", "poids": "71", "taille": "176"},
        "consultations": [
            (5, "Certificat de sport", "Examen clinique normal", "Aucune prescription", None),
        ],
    },
]


class Command(BaseCommand):
    help = "Charge des données de démonstration (patients, consultations, bilans)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--comptes", action="store_true",
            help="Crée aussi les comptes de démonstration secretaire et soignant.",
        )
        parser.add_argument(
            "--reinitialiser-mdp", action="store_true",
            help=(
                "Réinitialise le mot de passe des comptes de démonstration. "
                "Nécessaire après une création interrompue."
            ),
        )

    @transaction.atomic
    def handle(self, *args, **options):
        aujourdhui = timezone.localdate()

        # Groupes de rôles
        for nom in (GROUPE_SECRETARIAT, GROUPE_SOIGNANT):
            Group.objects.get_or_create(name=nom)

        soignant = None
        if options["comptes"]:
            User = get_user_model()
            soignant, _ = User.objects.get_or_create(
                username="dr.benali",
                defaults={"first_name": "Nadia", "last_name": "Benali",
                          "email": "soignant@infirmerie.local", "is_staff": True},
            )
            # Un compte peut avoir été créé sans mot de passe exploitable
            # (création interrompue) : dans ce cas, on le réinitialise.
            if not soignant.has_usable_password() or options["reinitialiser_mdp"]:
                soignant.set_password(MOT_DE_PASSE_DEMO)
            soignant.groups.clear()
            soignant.groups.add(Group.objects.get(name=GROUPE_SOIGNANT))
            soignant.is_active = True
            soignant.save()

            secretaire, _ = User.objects.get_or_create(
                username="secretariat",
                defaults={"first_name": "Accueil", "last_name": "Infirmerie"},
            )
            if not secretaire.has_usable_password() or options["reinitialiser_mdp"]:
                secretaire.set_password(MOT_DE_PASSE_DEMO)
            secretaire.groups.clear()
            secretaire.groups.add(Group.objects.get(name=GROUPE_SECRETARIAT))
            secretaire.is_active = True
            secretaire.save()

            self.stdout.write(
                self.style.SUCCESS(
                    "Comptes créés — soignant: dr.benali / secrétariat: secretariat "
                    "(mot de passe: Infirmerie2026!)"
                )
            )

        n_patients = n_consult = n_bilans = n_mesures = 0

        for i, data in enumerate(PATIENTS, start=1):
            numero = f"INF-{i:04d}"
            if Patient.objects.filter(numero_dossier=numero).exists():
                continue

            p = Patient.objects.create(
                nom=data["nom"], prenom=data["prenom"],
                date_naissance=f"{data['naissance'][:4]}-{data['naissance'][5:7]}-{data['naissance'][8:]}",
                sexe=data["sexe"], telephone=data["tel"],
                medecin_traitant=data["medecin"] or "", numero_dossier=numero,
            )
            n_patients += 1

            for substance, reaction, gravite in data["allergies"]:
                Allergie.objects.create(
                    patient=p, substance=substance, reaction=reaction, gravite=gravite
                )

            for jours, motif, diagnostic, prescription, type_bilan in data["consultations"]:
                c = Consultation.objects.create(
                    patient=p,
                    date=aujourdhui - timedelta(days=jours),
                    soignant=soignant,
                    motif=motif, diagnostic=diagnostic, prescription=prescription,
                    constantes=data["constantes"],
                    statut="cloturee" if jours > 20 else "ouverte",
                )
                n_consult += 1

                if type_bilan:
                    b = Bilan.objects.create(
                        consultation=c, date=c.date, type_examen=type_bilan,
                        laboratoire="Laboratoire Biolys",
                    )
                    n_bilans += 1
                    for parametre, valeur, unite, mini, maxi in BILANS_TYPE[type_bilan]:
                        Mesure.objects.create(
                            bilan=b, parametre=parametre, valeur=valeur, unite=unite,
                            norme_min=mini, norme_max=maxi,
                        )
                        n_mesures += 1

        # Les numéros de dossier sont au format INF-0001 (4 chiffres)
        Suivi.objects.get_or_create(
            patient=Patient.objects.filter(numero_dossier="INF-0005").first(),
            description="Renouveler l'imagerie de contrôle (bilan > 12 mois)",
            echeance=aujourdhui + timedelta(days=15),
        )
        Suivi.objects.get_or_create(
            patient=Patient.objects.filter(numero_dossier="INF-0001").first(),
            description="Relancer la NFS de contrôle après 3 semaines de fer",
            echeance=aujourdhui - timedelta(days=4),
        )

        self.stdout.write(self.style.SUCCESS(
            f"Démonstration chargée : {n_patients} patients, {n_consult} consultations, "
            f"{n_bilans} bilans, {n_mesures} mesures."
        ))
