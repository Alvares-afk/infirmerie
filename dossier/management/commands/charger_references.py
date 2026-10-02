"""Fourchettes de référence du laboratoire.

⚠ Ces valeurs proviennent d'un compte rendu réel. Elles servent à signaler
une valeur hors norme — jamais à poser un diagnostic.

Règle appliquée, sans exception : ce qui n'est pas dans cette table n'est
pas classé. Un paramètre absent ressort « à qualifier », ce qui est un
résultat honnête : mieux vaut une case vide qu'un « normal » inventé.

Origine : feuille du laboratoire, à revalider si le laboratoire change ses
méthodes ou ses appareils. Les valeurs qui varient d'un labo à l'autre
(leucocytes, hémoglobine) sont ici celles de CE laboratoire.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from dossier.models import Laboratoire, ReferenceIntervalle

# (code, libellé, unité, min, max)
# min/max à None = borne non applicable (pourcentages, etc.)
# 'sexe' : "H", "F", "M" (= tous), "" = tous
# age_min/age_max en années ; None = pas de borne d'âge
REFS = [
    # --- Numération formule sanguine -------------------------------
    ("LEU",  "Leucocytes",         "x10^3/mm3",   4,     10,    "T", 0, None),
    ("ERY",  "Érythrocytes",       "x10^6/mm3",   3.4,   5.8,   "T", 0, None),
    ("HB",   "Hémoglobine",        "g/dL",        11.5,  16.5,  "T", 0, None),
    ("HTE",  "Hématocrite",        "%",           37,    47,    "T", 0, None),
    ("VGM",  "VGM",                "fL",          76,    96,    "T", 0, None),
    ("TCMH", "TCMH",               "pg",          27,    32,    "T", 0, None),
    ("CCMH", "CCMH",               "g/dL",        30,    36,    "T", 0, None),
    ("PLQ",  "Plaquettes",         "x10^3/mm3",   150,   400,   "T", 0, None),

    # --- Formule leucocytaire (pourcentages) ---------------------
    ("LYM",  "Lymphocytes",        "%",           20,    45,    "T", 0, None),
    ("MON",  "Monocytes",          "%",           0,     10,    "T", 0, None),
    ("NEU",  "Neutrophiles",       "%",           45,    75,    "T", 0, None),
    ("BAS",  "Basophiles",         "%",           0,     1,     "T", 0, None),
    ("EOS",  "Éosinophiles",       "%",           0,     6,     "T", 0, None),
]


class Command(BaseCommand):
    help = "Charge les fourchettes de référence du laboratoire."

    def add_arguments(self, parser):
        parser.add_argument(
            "--laboratoire", default="Laboratoire de référence",
            help="Nom du laboratoire dans la base.",
        )
        parser.add_argument(
            "--remplacer", action="store_true",
            help="Supprime les fourchettes existantes de ce laboratoire avant de recharger.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        lab, cree = Laboratoire.objects.get_or_create(
            nom=options["laboratoire"],
            defaults={"actif": True},
        )
        if cree:
            self.stdout.write(f"Laboratoire créé : {lab.nom}")
        else:
            self.stdout.write(f"Laboratoire existant : {lab.nom}")

        if options["remplacer"]:
            n, _ = ReferenceIntervalle.objects.filter(laboratoire=lab).delete()
            self.stdout.write(f"{n} référence(s) supprimée(s)")

        # Les bornes sont « en vigueur » depuis la date du document source
        debut = timezone.localdate() - timedelta(days=1)

        chargees = 0
        ignorees = []
        for code, libelle, unite, mini, maxi, sexe, age_min, age_max in REFS:
            deja = ReferenceIntervalle.objects.filter(
                laboratoire=lab, code=code, sexe=sexe,
                age_min=age_min, age_max=age_max,
            ).first()
            if deja:
                # Mise à jour sans casser les mesures qui pointent dessus
                deja.libelle = libelle
                deja.unite = unite
                deja.norme_min = mini
                deja.norme_max = maxi
                deja.date_fin = None
                deja.save()
                ignorees.append(f"{libelle} (mis à jour)")
                continue
            ReferenceIntervalle.objects.create(
                laboratoire=lab,
                code=code,
                libelle=libelle,
                unite=unite,
                norme_min=mini,
                norme_max=maxi,
                sexe=sexe,
                age_min=age_min,
                age_max=age_max,
                date_debut=debut,
            )
            chargees += 1

        self.stdout.write(self.style.SUCCESS(
            f"{chargees} référence(s) chargée(s)."
        ))
        if ignorees:
            self.stdout.write(
                f"{len(ignorees)} déjà présente(s), mise à jour : "
                + ", ".join(ignorees[:4]) + ("…" if len(ignorees) > 4 else "")
            )

        # Point de vigilance : ce que la feuille NE contient pas
        self.stdout.write("")
        self.stdout.write(self.style.WARNING(
            "Non couverts par cette feuille — un paramètre saisi ici ressortira"
        ))
        self.stdout.write(self.style.WARNING(
            "« à qualifier », jamais « normal ». C'est le comportement voulu."
        ))
        for absent in (
            "Glycémie, créatinine, ALAT, ferritine, TSH, lipides (non sur la feuille)",
            "Widal (titres, pas de fourchette chiffrée)",
            "Parasitémie en TPZ/ml (positif/négatif, pas de norme)",
        ):
            self.stdout.write(f"  · {absent}")

        self.stdout.write("")
        self.stdout.write("Recharger avec --remplacer si le laboratoire change ses normes.")
