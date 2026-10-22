"""Accès aux mots de passe des comptes, depuis un fichier local.

Pourquoi un fichier et pas la conversation : un mot de passe affiché dans un
fil de discussion y reste. Le fichier vit à côté de l'application, il est
ignoré par Git, et il se supprime.

Format : une ligne par compte, `identifiant<TAB>mot de passe`. Les lignes
commençant par `#` sont ignorées.
"""

from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
FICHIER = BASE / "acces-comptes.txt"

ENTETE = (
    "# Accès à l'application Infirmerie\n"
    "# Un identifiant et un mot de passe par ligne, séparés par une tabulation.\n"
    "# Notez ces mots de passe, puis supprimez ce fichier.\n"
)


def lire():
    """Retourne {identifiant: mot de passe}. Vide si le fichier n'existe pas."""
    if not FICHIER.exists():
        return {}
    mots = {}
    for ligne in FICHIER.read_text(encoding="utf-8").splitlines():
        if not ligne.strip() or ligne.lstrip().startswith("#"):
            continue
        morceaux = ligne.split("\t")
        if len(morceaux) >= 2 and morceaux[0].strip():
            mots[morceaux[0].strip()] = morceaux[1].strip()
    return mots


def ecrire(comptes):
    """Écrit le fichier. `comptes` : liste de (identifiant, mot de passe, rôle)."""
    lignes = [ENTETE.rstrip("\n"), ""]
    for identifiant, mot_de_passe, role in comptes:
        lignes.append(f"{identifiant}\t{mot_de_passe}\t{role}")
    FICHIER.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    return FICHIER
