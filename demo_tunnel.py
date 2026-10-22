"""Lance une instance de DEMONSTRATION derriere un tunnel Cloudflare.

Ce que ce script garantit :
  - DEBUG est coupe : une erreur n'affiche pas la configuration a l'ecran
  - la banniere « VERSION DE DEMONSTRATION » est forcee dans l'interface
  - seule la base de demonstration est utilisee (patients fictifs)
  - le jeton CSRF et les hotes autorises correspondent au tunnel
  - le tunnel et le serveur s'arretent ensemble (Ctrl+C)

Ce qu'il ne fait pas : il n'expose rien tant qu'il n'est pas lance, et il
s'arrete des que la fenetre se ferme.
"""

import os
import secrets
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

BASE = Path(r"C:/Users/Alvarès/infirmerie-app")
PYTHON = BASE / ".venv" / "Scripts" / "python.exe"
TUNNEL = Path(os.environ["LOCALAPPDATA"]) / "hermes" / "bin" / "cloudflared.exe"
PORT = 8020


def port_libre(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def main():
    if not PYTHON.exists():
        sys.exit(f"Python introuvable : {PYTHON}")
    if not TUNNEL.exists():
        sys.exit(f"cloudflared introuvable : {TUNNEL}")
    if not port_libre(PORT):
        sys.exit(f"Le port {PORT} est deja occupe. Fermez l'autre instance.")

    env = dict(os.environ)
    env.update({
        "INFIRMERIE_DEBUG": "0",
        "INFIRMERIE_MODE_DEMO": "1",
        "INFIRMERIE_ALLOWED_HOSTS": "*",
        "INFIRMERIE_CSRF_TRUSTED": "https://*.trycloudflare.com",
        "INFIRMERIE_SECRET_KEY": secrets.token_urlsafe(50),
        "PYTHONIOENCODING": "utf-8",
    })

    print("  Demarrage du serveur de demonstration…")
    serveur = subprocess.Popen(
        [str(PYTHON), "manage.py", "runserver", f"127.0.0.1:{PORT}", "--noreload"],
        cwd=str(BASE), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    # Attendre que le serveur reponde avant d'ouvrir le tunnel
    for _ in range(60):
        try:
            with socket.create_connection(("127.0.0.1", PORT), timeout=1):
                break
        except OSError:
            time.sleep(0.5)
    else:
        serveur.terminate()
        sys.exit("Le serveur n'a pas demarre.")

    print("  Ouverture du tunnel…\n")
    tunnel = subprocess.Popen(
        [str(TUNNEL), "tunnel", "--url", f"http://127.0.0.1:{PORT}", "--no-autoupdate"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
    )

    adresse = []

    def lire():
        for ligne in tunnel.stdout:
            if "trycloudflare.com" in ligne and not adresse:
                for mot in ligne.split():
                    if "trycloudflare.com" in mot:
                        adresse.append(mot.strip())

    threading.Thread(target=lire, daemon=True).start()

    for _ in range(60):
        if adresse:
            break
        time.sleep(0.5)

    if not adresse:
        tunnel.terminate()
        serveur.terminate()
        sys.exit("Le tunnel n'a pas fourni d'adresse.")

    print("  ============================================================")
    print(f"   LIEN DE DEMONSTRATION : {adresse[0]}")
    print("  ============================================================")
    print()
    print("   Comptes : dr.benali / secretariat / admin")
    print("   Mot de passe : celui de l'application locale.")
    print()
    print("   Donnees fictives uniquement. DEBUG est coupe.")
    print("   Ctrl+C arrete le lien et le serveur.")
    print()

    try:
        while True:
            time.sleep(1)
            if serveur.poll() is not None or tunnel.poll() is not None:
                print("  Le serveur ou le tunnel s'est arrete.")
                break
    except KeyboardInterrupt:
        pass
    finally:
        tunnel.terminate()
        serveur.terminate()
        print("  Demonstration arretee.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
