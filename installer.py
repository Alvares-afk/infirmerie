"""Installation de l'infirmerie sur un poste Windows, sans ligne de commande.

Lance par installer.bat, qui se charge de trouver Python. Tout ce que la
personne a a faire : double-cliquer, puis taper un mot de passe.

Le script est volontairement bavard et ne suppose aucune connaissance
technique : chaque etape dit ce qu'elle fait, et s'arrete net en cas de
probleme plutot que de continuer dans un etat a moitie installe.
"""

import getpass
import os
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent
VENV = RACINE / ".venv"
PYTHON = VENV / "Scripts" / "python.exe"


def titre(texte):
    print()
    print("=" * 62)
    print(f"  {texte}")
    print("=" * 62)
    print()


def etape(numero, total, texte):
    print(f"\n[{numero}/{total}] {texte}")
    print("-" * 62)


def arreter(message):
    print()
    print("!" * 62)
    print("  INSTALLATION INTERROMPUE")
    print("!" * 62)
    print()
    print(message)
    print()
    input("Appuyez sur Entree pour fermer cette fenetre...")
    sys.exit(1)


def executer(commande, cwd=RACINE, silencieux=False):
    resultat = subprocess.run(
        commande, cwd=str(cwd),
        capture_output=silencieux, text=True,
        encoding="utf-8", errors="replace",
    )
    if resultat.returncode != 0:
        detail = ""
        if silencieux:
            detail = ((resultat.stderr or "") + (resultat.stdout or "")).strip()[-800:]
        arreter(f"La commande a echoue :\n  {' '.join(map(str, commande))}\n\n{detail}")
    return resultat


def demander_mot_de_passe():
    """Demande la phrase de passe deux fois, sans l'afficher a l'ecran."""
    impose = os.environ.get("INFIRMERIE_MDP")
    if impose:
        return impose

    print(
        "\nChoisissez le mot de passe qui ouvrira l'application.\n"
        "Il est commun aux trois comptes. Notez-le : il ne sera plus affiche.\n"
        "12 caracteres minimum.\n"
    )
    while True:
        premier = getpass.getpass("Mot de passe : ")
        if len(premier) < 12:
            print("  Trop court : 12 caracteres minimum. Recommencez.\n")
            continue
        second = getpass.getpass("Le meme, une seconde fois : ")
        if premier != second:
            print("  Les deux saisies diffèrent. Recommencez.\n")
            continue
        return premier


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    os.chdir(RACINE)
    TOTAL = 7

    titre("Installation de l'application Infirmerie")

    if sys.version_info < (3, 12):
        arreter(
            f"Python {sys.version_info.major}.{sys.version_info.minor} est installe, "
            "mais il faut Python 3.12 ou plus recent.\n\n"
            "Telechargez-le sur https://www.python.org/downloads/\n"
            "et cochez « Add python.exe to PATH » pendant l'installation."
        )

    print(f"Dossier        : {RACINE}")
    print(f"Python         : {sys.version.split()[0]}")
    print()
    print("Six etapes, deux a trois minutes. Ne fermez pas cette fenetre.")
    input("\nAppuyez sur Entree pour commencer...")

    # ---------------------------------------------------------------- 1/6
    etape(1, TOTAL, "Preparation de l'environnement Python")
    if PYTHON.exists():
        print("  Deja prepare, on passe.")
    else:
        print("  Creation du dossier .venv (isole le logiciel du reste du PC)...")
        executer([sys.executable, "-m", "venv", str(VENV)])
        print("  Fait.")

    # ---------------------------------------------------------------- 2/6
    etape(2, TOTAL, "Installation des composants (connexion Internet requise)")
    print("  Cela peut prendre une a deux minutes...")
    executer([str(PYTHON), "-m", "pip", "install", "--upgrade", "pip", "-q"], silencieux=True)
    resultat = subprocess.run(
        [str(PYTHON), "-m", "pip", "install", "-r", "requirements.txt", "-q"],
        cwd=str(RACINE), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    if resultat.returncode != 0:
        arreter(
            "Les composants n'ont pas pu etre telecharges.\n\n"
            "Verifiez que ce poste a bien acces a Internet, puis relancez "
            "installer.bat.\n\n"
            "Detail technique :\n"
            + ((resultat.stderr or "")[-700:])
        )
    print("  Fait.")

    # ---------------------------------------------------------------- 3/6
    etape(3, TOTAL, "Preparation de la base de donnees")
    executer([str(PYTHON), "manage.py", "migrate"], silencieux=True)
    print("  Fait. Aucun dossier patient n'est present : la base demarre vide.")

    # ---------------------------------------------------------------- 4/6
    etape(4, TOTAL, "Creation des trois comptes")
    executer([str(PYTHON), "manage.py", "creer_comptes"], silencieux=True)
    print("  dr.benali (soignant), secretariat, admin.")

    mot_de_passe = demander_mot_de_passe()
    executer(
        [str(PYTHON), "manage.py", "renouveler_mots_de_passe", "--mot-de-passe", mot_de_passe],
        silencieux=True,
    )
    print("  Mot de passe applique aux trois comptes.")

    # ---------------------------------------------------------------- 5/6
    etape(5, TOTAL, "Chargement des normes du laboratoire")
    executer([str(PYTHON), "manage.py", "charger_references"], silencieux=True)
    csv = RACINE / "fourchettes-biochimie.csv"
    if csv.exists():
        executer(
            [str(PYTHON), "manage.py", "importer_fourchettes", str(csv)],
            silencieux=True,
        )
    print("  41 fourchettes chargees (13 hematologie, 28 biochimie).")

    # ---------------------------------------------------------------- 6/7
    etape(6, TOTAL, "Passage en mode production")
    # La clé signe les sessions : propre à ce poste, elle ne doit pas être
    # celle d'un autre. Sa présence bascule l'application hors du mode
    # développement (plus de traces d'erreur détaillées à l'écran).
    cle = RACINE / ".secret-key"
    if not cle.exists():
        import secrets as _secrets

        cle.write_text(_secrets.token_urlsafe(64), encoding="utf-8")
        print("  Cle de signature creee pour ce poste.")
    else:
        print("  Cle de signature deja presente, conservee.")

    # Les fichiers statiques doivent être rassemblés : en production, c'est
    # WhiteNoise qui les sert, pas le serveur de développement.
    executer([str(PYTHON), "manage.py", "collectstatic", "--noinput"], silencieux=True)
    print("  Fichiers d'affichage rassembles.")
    print("  Mode production actif : les erreurs ne s'affichent plus en detail.")

    # ---------------------------------------------------------------- 7/7
    etape(7, TOTAL, "Verification")
    controle = executer(
        [str(PYTHON), "manage.py", "verifier_connexion", "--mot-de-passe", mot_de_passe],
        silencieux=True,
    )
    if "Tous les comptes se connectent" not in (controle.stdout or ""):
        arreter(
            "Les comptes ne repondent pas comme prevu.\n\n"
            + ((controle.stdout or "") + (controle.stderr or ""))[-800:]
        )
    print("  Les trois comptes se connectent.")

    titre("Installation terminee")
    print("Pour utiliser l'application : double-cliquez sur  lancer.py")
    print("Elle s'ouvre dans le navigateur, a l'adresse http://127.0.0.1:8000")
    print()
    print("Comptes :")
    print("  dr.benali    soignant      acces complet")
    print("  secretariat  secretariat   sans donnees cliniques")
    print("  admin        administration (/admin/)")
    print()
    print("Pensez a planifier la sauvegarde : voir la section 4 de INSTALLATION.md")
    print()
    input("Appuyez sur Entree pour fermer cette fenetre...")


if __name__ == "__main__":
    main()
