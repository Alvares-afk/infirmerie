# -*- coding: utf-8 -*-
"""Lanceur de l'application Infirmerie.

Choisit une adresse locale disponible et demarre le serveur :
  - http://infirmerie        si le nom est enregistre et le port 80 libre
  - http://infirmerie:8000   si le nom est enregistre mais le port 80 pris
  - http://127.0.0.1:8000    sinon (nom non enregistre)

Le nom "infirmerie" s'enregistre une seule fois avec installer_nom.bat.
"""
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser

NOM = "infirmerie"
HOSTS = r"C:\Windows\System32\drivers\etc\hosts"


def port_libre(port):
    """Vrai si le port est disponible sur 127.0.0.1."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def nom_enregistre():
    """Vrai si le nom 'infirmerie' figure dans le fichier hosts de Windows."""
    try:
        with open(HOSTS, "r", encoding="utf-8", errors="ignore") as f:
            for ligne in f:
                ligne = ligne.strip()
                if ligne.startswith("#"):
                    continue
                champs = ligne.split("#", 1)[0].lower().split()
                if len(champs) >= 2 and champs[0] == "127.0.0.1" and NOM in champs[1:]:
                    return True
    except OSError:
        pass
    return False


def choisir_port(nom_ok=False):
    """Port 80 uniquement avec le nom simple ; sinon 8000, puis 8010-8049."""
    ports = ([80] if nom_ok else []) + [8000] + list(range(8010, 8050))
    for port in ports:
        if port_libre(port):
            return port
    return None


def ouvrir_navigateur(url, pret):
    """Ouvre le navigateur quand le serveur repond."""
    for _ in range(120):
        if pret.wait(0.5):
            webbrowser.open(url)
            return


def main():
    nom_ok = nom_enregistre()
    port = choisir_port(nom_ok)
    if port is None:
        print("  Aucun port local disponible pour l'application.")
        print("  Fermez l'autre fenetre de l'application puis relancez.")
        input("  Entree pour quitter.")
        return 1

    if nom_ok:
        adresse = "http://%s" % NOM if port == 80 else "http://%s:%d" % (NOM, port)
    else:
        adresse = "http://127.0.0.1:%d" % port

    hotes = "127.0.0.1,localhost,%s" % NOM
    origines = "http://%s,http://%s:%d" % (NOM, NOM, port)
    os.environ["INFIRMERIE_ALLOWED_HOSTS"] = hotes
    os.environ["INFIRMERIE_CSRF_TRUSTED"] = origines

    print()
    print("  ================================================")
    print("   Application : %s" % adresse)
    print("  ================================================")
    if not nom_ok:
        print()
        print("   Le nom simple 'infirmerie' n'est pas enregistre.")
        print("   Pour l'activer : double-cliquez installer_nom.bat")
        print("   (une seule fois), puis relancez l'application.")
    if port != 80 and nom_ok:
        print()
        print("   Le port 80 est pris par un autre programme :")
        print("   l'adresse porte donc le numero %d." % port)
    print()
    print("   Laissez cette fenetre ouverte. Ctrl+C pour arreter.")
    print("   Si la page ne s'ouvre pas, copiez l'adresse Application ci-dessus.")
    print()

    pret = threading.Event()

    def surveiller():
        for _ in range(240):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    pret.set()
                    return
            except OSError:
                time.sleep(0.5)

    threading.Thread(target=surveiller, daemon=True).start()
    threading.Thread(target=ouvrir_navigateur, args=(adresse, pret), daemon=True).start()

    manage = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manage.py")

    # Sur un poste installé (clé de signature présente), l'application sert
    # les VRAIS dossiers. Sans cela, un double-clic sur lancer.py ouvrirait
    # la base de démonstration : les comptes créés à l'installation n'y sont
    # pas, et la connexion échoue sans explication.
    environnement = dict(os.environ)
    if os.path.exists(os.path.join(os.path.dirname(manage), ".secret-key")):
        environnement.setdefault("INFIRMERIE_BASE", "reelle")

    try:
        return subprocess.call(
            [sys.executable, manage, "runserver", "127.0.0.1:%d" % port],
            env=environnement,
        )
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
