"""Lance l'application sur le reseau local (tablette, second poste).

Le serveur n'ecoute QUE sur l'adresse IPv4 de la carte reseau du poste, pas
sur 0.0.0.0 : une machine qui a un VPN ou une carte virtuelle n'expose pas
l'application par ces interfaces-la. Les autres appareils du meme reseau
atteignent l'adresse affichee au demarrage.

L'adresse est detectee a chaque lancement : si le routeur en attribue une
autre demain (bail DHCP), il n'y a rien a reconfigurer.

Usage :
    ./.venv/Scripts/python.exe demarrer_reseau.py
    ./.venv/Scripts/python.exe demarrer_reseau.py --demo
"""

import os
import socket
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
PORT = int(os.environ.get("INFIRMERIE_PORT", "8000"))


def ip_locale():
    """Adresse IPv4 de l'interface qui porte la route par defaut.

    Connecter une socket UDP n'envoie aucun paquet : cela ne fait que
    demander au systeme quelle interface il utiliserait. C'est la seule
    methode fiable pour distinguer la vraie carte reseau des cartes
    virtuelles (VPN, Hyper-V, WSL) qui ont aussi une adresse IPv4.
    """
    sonde = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sonde.connect(("192.0.2.1", 80))  # adresse de documentation, jamais jointe
        adresse = str(sonde.getsockname()[0])
        if adresse and not adresse.startswith("127."):
            return adresse
    except OSError:
        pass
    finally:
        sonde.close()

    # Repli : resoudre le nom de la machine. Suffit sur un reseau isole.
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            adresse = info[4][0]
            if not adresse.startswith("127."):
                return adresse
    except OSError:
        pass
    return None


def main():
    demo = "--demo" in sys.argv

    adresse = ip_locale()
    if not adresse:
        print()
        print("  Aucune adresse reseau trouvee : ce poste n'est pas connecte")
        print("  a un reseau local. Brancher le cable Wi-Fi / Ethernet, ou")
        print("  utiliser demarrer_reel.bat (acces sur ce poste uniquement).")
        print()
        return 1

    # Le nom d'hote du poste est accepte en plus de l'adresse : certaines
    # tablettes resolvent DESKTOP-xxxx en .local, pas l'inverse.
    hotes = ["127.0.0.1", "localhost", adresse, socket.gethostname()]
    os.environ["INFIRMERIE_ALLOWED_HOSTS"] = ",".join(dict.fromkeys(hotes))
    os.environ.setdefault("INFIRMERIE_BASE", "demo" if demo else "reelle")

    base = "DEMONSTRATION" if demo else "DOSSIERS REELS"

    print()
    print("  ================================================")
    print(f"   INFIRMERIE - {base}")
    print("   Acces reseau local")
    print("  ================================================")
    print()
    print(f"   Depuis ce poste    : http://127.0.0.1:{PORT}")
    print(f"   Depuis un autre    : http://{adresse}:{PORT}")
    print()
    print("   Le second appareil doit etre sur le MEME reseau")
    print("   (meme box, meme Wi-Fi). Rien a installer dessus :")
    print("   un navigateur suffit.")
    print()
    print("   Laissez cette fenetre ouverte. Ctrl+C pour arreter.")
    print()

    commande = [
        sys.executable,
        "manage.py",
        "runserver",
        f"{adresse}:{PORT}",
    ]
    return subprocess.call(commande, cwd=str(BASE))


if __name__ == "__main__":
    sys.exit(main())
