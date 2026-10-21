"""Contrôle des unités et des fourchettes réellement enregistrées.

Usage :
    python manage.py verifier_unites            # tout contrôler
    python manage.py verifier_unites --strict   # échouer si un paramètre échappe

Deux choses différentes sont signalées, et il ne faut pas les confondre :

  1. **Incohérence** — le paramètre est couvert par la table, mais l'unité ne
     colle pas avec ses bornes. C'est une erreur à corriger : elle rend une
     valeur dangereuse rassurante (« 5,4 g/L — Normal »).
  2. **Non couvert** — aucune règle ne connaît ce paramètre. Il n'est pas
     faux, il est simplement hors de portée du contrôle. À signaler pour que
     la table soit complétée, sinon le garde-fou ne protège de rien sur ce
     paramètre.

Le second cas n'est jamais une erreur en soi : la table ne prétend pas couvrir
toute la biologie. `--strict` en fait une erreur, à réserver au moment où
l'on charge une nouvelle feuille de laboratoire.
"""

from django.core.management.base import BaseCommand

from dossier.models import Mesure, ReferenceIntervalle
from dossier.unites import fragment_reconnu, incoherence_unite


class Command(BaseCommand):
    help = "Vérifie la cohérence unité / bornes des fourchettes et des mesures."

    def add_arguments(self, parser):
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Traiter un paramètre non couvert comme une erreur.",
        )

    def handle(self, *args, **options):
        strict = options["strict"]
        incoherences = []
        non_couverts = {}
        verifies = 0

        # --- Fourchettes de référence du laboratoire ------------------------
        for ref in ReferenceIntervalle.objects.select_related("laboratoire"):
            verifies += 1
            message = incoherence_unite(
                ref.libelle, ref.unite, ref.norme_min, ref.norme_max
            )
            if message:
                incoherences.append(("fourchette", ref.libelle, message))
            elif fragment_reconnu(ref.libelle) is None:
                non_couverts.setdefault(ref.libelle, 0)
                non_couverts[ref.libelle] += 1

        # --- Mesures saisies dans les bilans --------------------------------
        for mesure in Mesure.objects.all():
            verifies += 1
            message = incoherence_unite(
                mesure.parametre, mesure.unite, mesure.norme_min, mesure.norme_max
            )
            if message:
                incoherences.append(("mesure", mesure.parametre, message))
            elif fragment_reconnu(mesure.parametre) is None:
                non_couverts.setdefault(mesure.parametre, 0)
                non_couverts[mesure.parametre] += 1

        # --- Rapport --------------------------------------------------------
        self.stdout.write("")
        self.stdout.write(f"{verifies} enregistrement(s) contrôlé(s)")

        if incoherences:
            self.stdout.write("")
            self.stderr.write(
                self.style.ERROR(f"{len(incoherences)} incohérence(s) :")
            )
            for origine, libelle, message in incoherences:
                self.stderr.write(f"  [{origine}] {message}")

        if non_couverts:
            self.stdout.write("")
            self.stdout.write(
                f"{len(non_couverts)} paramètre(s) hors de portée du contrôle "
                f"({'strict' if strict else 'à compléter dans FOURCHETTES_PLAUSIBLES'}) :"
            )
            for libelle, nombre in sorted(non_couverts.items()):
                self.stdout.write(f"  - {libelle} ({nombre} ligne(s))")
            self.stdout.write("")
            self.stdout.write(
                "Ce n'est pas une erreur : ces paramètres passent simplement "
                "sans contrôle d'unité."
            )

        self.stdout.write("")
        if not incoherences and not (strict and non_couverts):
            self.stdout.write(
                self.style.SUCCESS("Aucune incohérence détectée.")
            )
            return

        if strict and non_couverts:
            self.stderr.write(
                self.style.ERROR(
                    "Mode strict : des paramètres ne sont pas couverts par la table."
                )
            )
        raise SystemExit(1)
