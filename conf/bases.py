"""Gestion des bases de données multiples.

Deux bases coexistent volontairement :

  db.sqlite3          — patients de démonstration (fictifs)
  db_reelle.sqlite3   — vos vrais dossiers

Pourquoi deux bases plutôt qu'une seule :
  - les patients fictifs servent à tester l'application sans risque
  - les vrais dossiers ne doivent jamais se mélanger à de la donnée fictive
  - une erreur sur la démo ne peut pas atteindre les vraies données
  - sauvegarder ou restaurer l'une n'affecte pas l'autre

Choisir la base : définir INFIRMERIE_BASE, ou laisser vide pour la démo.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

BASE_DEMO = BASE_DIR / "db.sqlite3"
BASE_REELLE = BASE_DIR / "db_reelle.sqlite3"

# Nom de la base choisie. Vide = base de démonstration.
#   set INFIRMERIE_BASE=reelle
BASE_CHOISIE = os.environ.get("INFIRMERIE_BASE", "").strip().lower()

BASE_UTILISEE = BASE_REELLE if BASE_CHOISIE == "reelle" else BASE_DEMO


def base_courante() -> Path:
    return BASE_UTILISEE


def est_base_reelle() -> bool:
    return BASE_CHOISIE == "reelle"
