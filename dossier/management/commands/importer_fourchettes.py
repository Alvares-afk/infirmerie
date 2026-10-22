"""Charge des fourchettes de référence depuis un fichier, avec contrôle.

Le laboratoire change de méthode ou d'appareil : ses bornes changent. Cette
commande remplace les fourchettes en vigueur par celles d'un fichier, en
vérifiant d'abord que l'ensemble tient debout.

Rien n'est écrit si une seule ligne est suspecte : un import à moitié appliqué
laisserait des paramètres avec les anciennes bornes et d'autres avec les
nouvelles, sans qu'on sache lesquelles.

Colonnes attendues, dans cet ordre (la première ligne peut être un en-tête) :

    code ; libellé ; unité ; borne basse ; borne haute ; sexe ; âge min ; âge max

  - sexe : T (tous), H, F — vide = T
  - bornes : vide accepté (borne non applicable), mais pas les deux
  - âges : en années, vides acceptés

Usage :
    python manage.py importer_fourchettes feuille.csv
    python manage.py importer_fourchettes feuille.csv --essai
    python manage.py importer_fourchettes feuille.csv --laboratoire "Labo XYZ"
"""

import csv
from datetime import date, timedelta
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from dossier.models import Laboratoire, ReferenceIntervalle
from dossier.unites import incoherence_unite

SEXE_VALIDES = {"T": "T", "H": "H", "F": "F", "": "T"}
COLONNES = 8


def _fr(valeur):
    """Nombre lisible en français : 30 plutôt que 30.0, 3,9 plutôt que 3.9."""
    if valeur is None:
        return "—"
    return f"{valeur:g}".replace(".", ",")


def _nombre(valeur, ligne, colonne):
    texte = (valeur or "").strip().replace(",", ".")
    if not texte:
        return None
    try:
        return float(texte)
    except ValueError:
        raise ValueError(f"ligne {ligne} : {colonne} « {valeur} » n'est pas un nombre")


def _entier(valeur, ligne, colonne):
    nombre = _nombre(valeur, ligne, colonne)
    if nombre is None:
        return None
    if nombre != int(nombre):
        raise ValueError(f"ligne {ligne} : {colonne} doit être un entier")
    return int(nombre)


class Command(BaseCommand):
    help = "Remplace les fourchettes de référence à partir d'un fichier contrôlé."

    def add_arguments(self, parser):
        parser.add_argument("fichier", help="Fichier CSV (séparateur ; ou ,)")
        parser.add_argument(
            "--essai",
            action="store_true",
            help="Vérifie sans rien enregistrer.",
        )
        parser.add_argument(
            "--laboratoire",
            help="Nom du laboratoire (créé s'il n'existe pas).",
        )

    def handle(self, *args, **options):
        chemin = Path(options["fichier"])
        if not chemin.exists():
            raise CommandError(f"Fichier introuvable : {chemin}")

        lignes = self._lire(chemin)
        problemes = self._controler(lignes)

        if problemes:
            self.stderr.write(self.style.ERROR(
                f"{len(problemes)} problème(s) — aucun import effectué :"
            ))
            for p in problemes:
                self.stderr.write(f"  - {p}")
            raise CommandError("Le fichier n'a pas été appliqué.")

        self.stdout.write(f"{len(lignes)} fourchette(s) valides.")
        for ligne in lignes:
            self.stdout.write(
                f"  {ligne['code']:<8} {ligne['libelle']:<28} "
                f"{_fr(ligne['min'])} – {_fr(ligne['max'])} {ligne['unite']}"
            )

        if options["essai"]:
            self.stdout.write("")
            self.stdout.write("Mode essai : rien n'a été enregistré.")
            return

        laboratoire = self._laboratoire(options.get("laboratoire"))
        aujourdhui = date.today()

        with transaction.atomic():
            # Les fourchettes en vigueur sont closes, jamais supprimées :
            # un bilan ancien doit rester interprétable avec ses propres bornes.
            closes = ReferenceIntervalle.objects.filter(
                laboratoire=laboratoire, date_fin__isnull=True
            ).update(date_fin=aujourdhui - timedelta(days=1))

            for ligne in lignes:
                ReferenceIntervalle.objects.create(
                    laboratoire=laboratoire,
                    code=ligne["code"],
                    libelle=ligne["libelle"],
                    unite=ligne["unite"],
                    norme_min=ligne["min"],
                    norme_max=ligne["max"],
                    sexe=ligne["sexe"],
                    age_min=ligne["age_min"],
                    age_max=ligne["age_max"],
                    date_debut=aujourdhui,
                )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"{len(lignes)} fourchette(s) chargée(s) pour {laboratoire.nom}."
        ))
        if closes:
            self.stdout.write(
                f"{closes} ancienne(s) fourchette(s) close(s) à la date de la veille."
            )

    # ------------------------------------------------------------------
    def _lire(self, chemin):
        contenu = chemin.read_text(encoding="utf-8-sig", errors="replace")
        separateur = ";" if contenu.count(";") > contenu.count(",") else ","
        lignes = []
        for numero, brut in enumerate(csv.reader(contenu.splitlines(), delimiter=separateur), 1):
            if not any(cellule.strip() for cellule in brut):
                continue
            if numero == 1 and "libell" in (brut[1] if len(brut) > 1 else "").lower():
                continue  # en-tête
            if len(brut) < COLONNES:
                brut = brut + [""] * (COLONNES - len(brut))
            code, libelle, unite, mini, maxi, sexe, age_min, age_max = brut[:COLONNES]
            lignes.append({
                "numero": numero,
                "code": code.strip().upper(),
                "libelle": libelle.strip(),
                "unite": unite.strip(),
                "min": mini,
                "max": maxi,
                "sexe": sexe.strip().upper(),
                "age_min": age_min,
                "age_max": age_max,
            })
        if not lignes:
            raise CommandError("Le fichier ne contient aucune ligne exploitable.")
        return lignes

    def _controler(self, lignes):
        problemes = []
        for ligne in lignes:
            n = ligne["numero"]
            try:
                ligne["min"] = _nombre(ligne["min"], n, "borne basse")
                ligne["max"] = _nombre(ligne["max"], n, "borne haute")
                ligne["age_min"] = _entier(ligne["age_min"], n, "âge min")
                ligne["age_max"] = _entier(ligne["age_max"], n, "âge max")
            except ValueError as erreur:
                problemes.append(str(erreur))
                continue

            if not ligne["code"]:
                problemes.append(f"ligne {n} : code manquant")
            if not ligne["libelle"]:
                problemes.append(f"ligne {n} : libellé manquant")
            if ligne["min"] is None and ligne["max"] is None:
                problemes.append(
                    f"ligne {n} ({ligne['libelle']}) : aucune borne — "
                    f"le paramètre serait toujours « à qualifier »"
                )
            if (
                ligne["min"] is not None
                and ligne["max"] is not None
                and ligne["min"] >= ligne["max"]
            ):
                problemes.append(
                    f"ligne {n} ({ligne['libelle']}) : borne basse ≥ borne haute, "
                    f"l'interprétation serait inversée"
                )

            sexe_saisi = ligne["sexe"]
            ligne["sexe"] = SEXE_VALIDES.get(sexe_saisi)
            if ligne["sexe"] is None:
                problemes.append(
                    f"ligne {n} : sexe « {sexe_saisi} » invalide (T, H ou F)"
                )

            # Le contrôle d'unité : c'est lui qui refuse une glycémie en g/L.
            message = incoherence_unite(
                ligne["libelle"], ligne["unite"], ligne["min"], ligne["max"]
            )
            if message:
                problemes.append(f"ligne {n} : {message}")
        return problemes

    def _laboratoire(self, nom):
        if nom:
            laboratoire, _ = Laboratoire.objects.get_or_create(nom=nom)
            return laboratoire
        existant = Laboratoire.objects.order_by("-id").first()
        if existant is None:
            raise CommandError(
                "Aucun laboratoire en base. Précisez --laboratoire \"Nom du labo\"."
            )
        return existant
