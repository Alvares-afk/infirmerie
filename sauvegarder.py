"""Sauvegarde de la base de donnees.

Deux bases coexistent, et il faut sauvegarder la bonne :

  db.sqlite3          — demonstration (patients fictifs)
  db_reelle.sqlite3   — vrais dossiers patients

Usage :
  - double-clic sur sauvegarder.bat        (demonstration)
  - double-clic sur sauvegarder_reel.bat   (vrais dossiers)
  - python sauvegarder.py                 (demonstration)
  - python sauvegarder.py --reel
  - python sauvegarder.py --restaurer <fichier> [--reel]

Les sauvegardes sont horodatees et placees dans sauvegardes/, avec un
prefixe par base (demo_ ou reel_). Les 30 dernieres de chaque base sont
conservees. Une sauvegarde sur le meme disque ne protege pas d'une panne de
disque : copiez-en une sur une cle USB.
"""

import shutil
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
DOSSIER = BASE / "sauvegardes"
GARDER = 30

BASES = {
    "demo": BASE / "db.sqlite3",
    "reel": BASE / "db_reelle.sqlite3",
}


def _prefixe(cle):
    """Chaque base a son propre prefixe : on ne confond jamais les deux."""
    return "reel_" if cle == "reel" else "demo_"


def sauvegarder(cle="demo"):
    db = BASES[cle]
    if not db.exists():
        nom = "dossiers reels" if cle == "reel" else "demonstration"
        print(f"Base {nom} introuvable ({db.name}).")
        print("Lancez d'abord demarrer_reel.bat ou demarrer_demo.bat.")
        return None

    DOSSIER.mkdir(exist_ok=True)
    prefixe = _prefixe(cle)
    horodatage = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    cible = DOSSIER / f"{prefixe}{horodatage}.db"

    shutil.copy2(db, cible)
    print(f"Sauvegarde creee : {cible.name} ({cible.stat().st_size / 1024:.0f} Ko)")

    # Rotation : uniquement les sauvegardes de CETTE base
    anciennes = sorted(
        (p for p in DOSSIER.glob(f"{prefixe}*.db") if p != cible),
        key=lambda p: p.name,
    )
    for ancienne in anciennes[: max(0, len(anciennes) - (GARDER - 1))]:
        ancienne.unlink()
        print(f"  ancienne sauvegarde supprimee : {ancienne.name}")

    return cible


def restaurer(chemin, cle="demo"):
    source = Path(chemin)
    if not source.is_absolute():
        source = BASE / source
    if not source.exists():
        print(f"Fichier introuvable : {source}")
        return False

    # Refus explicite : restaurer une sauvegarde de demonstration dans la
    # base des vrais dossiers y ecraserait des dossiers patients.
    if source.name.startswith("reel_"):
        type_source = "reel"
    elif source.name.startswith("demo_"):
        type_source = "demo"
    else:
        type_source = None

    if type_source is not None and type_source != cle:
        libelle_src = "dossiers reels" if type_source == "reel" else "demonstration"
        libelle_cible = "dossiers reels" if cle == "reel" else "demonstration"
        print(f"Refus : {source.name} est une sauvegarde {libelle_src},")
        print(f"et vous visez la base {libelle_cible}.")
        print("Une restauration ne franchit jamais les deux bases.")
        return False

    db = BASES[cle]

    if db.exists():
        # Archive de securite : la base courante n'est jamais perdue
        archive = DOSSIER / (
            f"{_prefixe(cle)}avant_restauration_{datetime.now():%Y-%m-%d_%H%M%S}.db"
        )
        DOSSIER.mkdir(exist_ok=True)
        shutil.copy2(db, archive)
        print(f"Base courante archivee dans {archive.name}")

    shutil.copy2(source, db)
    print(f"Base restauree depuis {source.name}")
    print("Redemarrez l'application pour prendre en compte la restauration.")
    return True


if __name__ == "__main__":
    args = sys.argv[1:]
    cle = "reel" if "--reel" in args else "demo"
    args = [a for a in args if a != "--reel"]

    if len(args) >= 2 and args[0] == "--restaurer":
        restaurer(args[1], cle)
    else:
        sauvegarder(cle)
