"""Vérifie que la sauvegarde restaure vraiment — sur une copie, jamais sur les vraies données.

Une sauvegarde jamais restaurée n'est pas une sauvegarde : c'est une copie
dont on espère qu'elle servira. Cette commande fait le trajet complet dans un
répertoire temporaire :

    1. copie la base dans un bac à sable
    2. prend une empreinte du contenu (toutes les tables, toutes les lignes)
    3. sauvegarde
    4. modifie la copie (ajout d'un patient témoin)
    5. restaure
    6. vérifie que l'empreinte est revenue à l'identique et que le témoin a disparu

La base réelle n'est jamais ouverte en écriture. Le bac à sable est supprimé
à la fin, succès ou échec.

Usage :
    python manage.py verifier_restauration
    python manage.py verifier_restauration --base reel   # sur la base réelle
"""

import hashlib
import shutil
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from sauvegarder import _chemin_base, restaurer, sauvegarder


def empreinte(db):
    """Empreinte du contenu complet : nombre de lignes et valeurs, table par table."""
    h = hashlib.sha256()
    with closing(sqlite3.connect(db)) as c:
        tables = [
            r[0] for r in c.execute(
                "select name from sqlite_master where type='table' "
                "and name not like 'sqlite_%' order by name"
            )
        ]
        for table in tables:
            h.update(f"#{table}#".encode())
            lignes = c.execute(f'select * from "{table}"').fetchall()
            h.update(str(len(lignes)).encode())
            for ligne in sorted(lignes, key=repr):
                h.update(repr(ligne).encode("utf-8", "replace"))
    return h.hexdigest(), tables


class Command(BaseCommand):
    help = "Teste le cycle sauvegarde → modification → restauration, sans risque."

    def add_arguments(self, parser):
        parser.add_argument(
            "--base",
            default="demo",
            choices=["demo", "reel"],
            help="Base à éprouver (demo par défaut : jamais la réelle sans le dire).",
        )

    def handle(self, *args, **options):
        cle = options["base"]
        origine = _chemin_base(cle)
        if not origine.exists():
            raise CommandError(f"Base introuvable : {origine.name}")

        with tempfile.TemporaryDirectory(prefix="verif_restauration_") as tmp:
            bac = Path(tmp)
            copie = _chemin_base(cle, base=bac)
            shutil.copy2(origine, copie)
            sauvegardes = bac / "sauvegardes"

            avant, tables = empreinte(copie)
            self.stdout.write(f"Tables contrôlées : {len(tables)}")

            # 1. sauvegarde
            fichier = sauvegarder(cle, base=bac, dossier=sauvegardes)
            if fichier is None or not fichier.exists():
                raise CommandError("La sauvegarde n'a pas été créée.")
            self.stdout.write(f"1. Sauvegarde : {fichier.name}")

            # 2. modification volontaire
            with closing(sqlite3.connect(copie)) as c:
                c.execute(
                    "create table if not exists _temoin_restauration (v text)"
                )
                c.execute("insert into _temoin_restauration values ('present')")
            apres_mutation, _ = empreinte(copie)
            if apres_mutation == avant:
                raise CommandError(
                    "La modification témoin n'a rien changé : le test ne prouve rien."
                )
            self.stdout.write("2. Modification volontaire : un témoin a été ajouté")

            # 3. restauration
            if not restaurer(fichier, cle, base=bac, dossier=sauvegardes):
                raise CommandError("La restauration a échoué.")
            self.stdout.write("3. Restauration effectuée")

            # 4. vérification
            apres, _ = empreinte(copie)
            with closing(sqlite3.connect(copie)) as c:
                temoin = c.execute(
                    "select count(*) from sqlite_master "
                    "where type='table' and name='_temoin_restauration'"
                ).fetchone()[0]

            problemes = []
            if apres != avant:
                problemes.append(
                    "le contenu restauré diffère de la sauvegarde : "
                    "des données ont été perdues ou altérées"
                )
            if temoin:
                problemes.append(
                    "la modification faite après la sauvegarde est encore là : "
                    "la restauration n'a pas remplacé la base"
                )

            if problemes:
                for p in problemes:
                    self.stderr.write(self.style.ERROR(f"ECHEC : {p}"))
                raise CommandError("La restauration ne fait pas ce qu'elle annonce.")

            self.stdout.write(
                self.style.SUCCESS(
                    "4. Contenu identique à la sauvegarde, témoin disparu."
                )
            )

            # 5. le garde-fou entre les deux bases
            faux = sauvegardes / ("reel_2026-01-01_000000_000000.db"
                                  if cle == "demo" else
                                  "demo_2026-01-01_000000_000000.db")
            shutil.copy2(fichier, faux)
            if restaurer(faux, cle, base=bac, dossier=sauvegardes):
                self.stderr.write(self.style.ERROR(
                    "ECHEC : une sauvegarde de l'autre base a été acceptée."
                ))
                raise CommandError("Le cloisonnement entre les deux bases est rompu.")
            self.stdout.write(
                "5. Une sauvegarde de l'autre base est bien refusée."
            )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            "Restauration vérifiée. La base réelle n'a pas été modifiée."
        ))
