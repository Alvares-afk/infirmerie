# Installer l'application Infirmerie

Ce document s'adresse à la personne qui installe le poste, pas à l'utilisatrice.

---

## 1. Ce qu'il faut

| Élément | Détail |
|---|---|
| Windows | 10 ou 11 |
| Python | 3.12 ou plus récent — <https://www.python.org/downloads/windows/> |
| Espace disque | 300 Mo environ |
| Réseau | aucun accès Internet nécessaire après l'installation |

**Pendant l'installation de Python, cocher « Add python.exe to PATH ».** Sans
cette case, rien ne fonctionnera et le message d'erreur sera obscur.

---

## 2. Installer

1. Copier le dossier de l'application à l'emplacement définitif, par exemple
   `C:\Infirmerie`. Éviter le Bureau et les dossiers synchronisés (OneDrive,
   Dropbox) : un fichier de base de données déplacé pendant une écriture se
   corrompt.

2. Ouvrir une invite de commandes **dans ce dossier** :

   ```
   cd C:\Infirmerie
   ```

3. Créer l'environnement Python et installer les dépendances :

   ```
   python -m venv .venv
   .venv\Scripts\python.exe -m pip install --upgrade pip
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

4. Créer la base de données :

   ```
   .venv\Scripts\python.exe manage.py migrate
   ```

5. Créer les trois comptes (sans aucun patient) :

   ```
   .venv\Scripts\python.exe manage.py creer_comptes
   ```

   Les comptes sont créés **sans mot de passe utilisable** : personne ne peut
   se connecter à ce stade, et c'est voulu. L'étape suivante est obligatoire.

6. Définir les mots de passe — **ils ne sont pas fournis avec le paquet** :

   ```
   .venv\Scripts\python.exe manage.py renouveler_mots_de_passe
   ```

   Les mots de passe sont écrits une seule fois dans `acces-comptes.txt`.
   Les noter, puis **supprimer ce fichier**.

7. Vérifier que les trois comptes se connectent :

   ```
   .venv\Scripts\python.exe manage.py verifier_connexion --mot-de-passe "<celui choisi>"
   ```

   La commande doit afficher « Tous les comptes se connectent. »

---

## 3. Lancer

Double-cliquer sur **`lancer.py`**. L'application s'ouvre dans le navigateur.

Pour un raccourci sur le Bureau : clic droit sur `lancer.py` → *Envoyer vers* →
*Bureau (créer un raccourci)*. Renommer le raccourci « Infirmerie ».

L'adresse `http://infirmerie` (sans numéro de port) demande une modification du
fichier hosts de Windows, réservée à l'administrateur : `installer_nom.bat`.

---

## 4. Sauvegardes

**À faire dès l'installation**, sinon rien n'est protégé.

- `sauvegarder_reel.bat` sauvegarde les vrais dossiers (`db_reelle.sqlite3`)
- `sauvegarder.bat` sauvegarde la base de démonstration

Planifier la première dans le Planificateur de tâches Windows, une fois par
jour, à une heure où le poste est allumé.

**Une sauvegarde sur le même disque ne protège pas d'une panne de disque.**
Copier régulièrement le contenu de `sauvegardes/` sur une clé USB.

Pour vérifier qu'une sauvegarde est réellement restaurable :

```
.venv\Scripts\python.exe manage.py verifier_restauration
```

---

## 5. Ce que ce paquet ne contient pas

**Aucune donnée patient.** La base est vide à l'installation. La base de
démonstration, si elle est utilisée, ne contient que des patients fictifs.

**Aucun mot de passe.** Voir l'étape 6.

**Le message quotidien de 6 h.** Il est produit par un ordonnanceur externe
(Hermes) installé sur le poste de développement, pas par l'application
elle-même. Sur ce poste, `manage.py point_du_jour` affiche le texte dans la
console, mais ne l'envoie nulle part. Pour l'envoyer, il faut soit installer
cet ordonnanceur, soit une tâche planifiée qui transmet la sortie.

---

## 6. Avant la mise en service réelle

- [ ] `verifier_connexion` passe pour les trois comptes
- [ ] Mots de passe notés, `acces-comptes.txt` supprimé
- [ ] Sauvegarde planifiée **et** restauration testée
- [ ] Fourchettes de biochimie chargées (`importer_fourchettes`) — sinon les
      résultats de biochimie resteront « à qualifier »
- [ ] Durée de conservation des dossiers définie avec l'établissement

---

## 7. En cas de problème

| Symptôme | Cause probable |
|---|---|
| `python` n'est pas reconnu | La case « Add to PATH » n'était pas cochée à l'installation |
| Page blanche ou erreur 400 | Adresse incorrecte : utiliser celle affichée par `lancer.py` |
| « Identifiant ou mot de passe incorrect » | Vérifier qu'on est bien sur **ce** poste, pas une autre copie de l'application |
| Le port est déjà pris | Une autre fenêtre de l'application est restée ouverte |
