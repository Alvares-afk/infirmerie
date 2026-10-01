"""Sauvegarde de la base de donnees.

Usage :
  - double-clic sur sauvegarder.bat pour une sauvegarde
  - python sauvegarder.py
  - python sauvegarder.py --restaurer sauvegardes/infirmerie_2026-09-30_101500.db

Les sauvegardes sont horodatees et placees dans sauvegardes/. Les 30
dernieres sont conservees. Une sauvegarde sur le meme disque ne protege
pas d'une panne de disque : copiez-en une sur une cle USB.
"""

import shutil
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
DB = BASE / "db.sqlite3"
DOSSIER = BASE / "sauvegardes"
PREFIXE = "infirmerie_"
GARDER = 30


def sauvegarder():
    if not DB.exists():
        print("Base introuvable : lancez d'abord demarrer.bat pour la creer.")
        return None

    DOSSIER.mkdir(exist_ok=True)
    horodatage = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    cible = DOSSIER / f"{PREFIXE}{horodatage}.db"

    shutil.copy2(DB, cible)
    print(f"Sauvegarde creee : {cible.name} ({cible.stat().st_size / 1024:.0f} Ko)")

    # On ne conserve que les GARDER sauvegardes les plus recentes
    anciennes = sorted(
        (p for p in DOSSIER.glob(f"{PREFIXE}*.db") if p != cible),
        key=lambda p: p.name,
    )
    for ancienne in anciennes[: max(0, len(anciennes) - (GARDER - 1))]:
        ancienne.unlink()
        print(f"  ancienne sauvegarde supprimee : {ancienne.name}")

    return cible


def restaurer(chemin):
    source = Path(chemin)
    if not source.is_absolute():
        source = BASE / source
    if not source.exists():
        print(f"Fichier introuvable : {source}")
        return False

    # On archive l'etat courant avant de l'ecraser
    if DB.exists():
        # Securite : copie de la base courante avant remplacement
        archive = DOSSIER / f"avant_restauration_{datetime.now():%Y-%m-%d_%H%M%S}.db"
        DOSSIER.mkdir(exist_ok=True)
        shutil.copy2(DB, archive)
        print(f"Base courante archivee dans {archive.name}")

    shutil.copy2(source, DB)
    print(f"Base restauree depuis {source.name}")
    print("Redemarrez l'application pour prendre en compte la restauration.")
    return True


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--restaurer":
        restaurer(sys.argv[2])
    else:
        sauvegarder()
