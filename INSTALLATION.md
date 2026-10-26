# Installer l'application Infirmerie

Deux publics, deux chemins :

- **La personne qui installe le poste** lit ce document.
- **La personne qui utilisera l'application** a une fiche d'une page :
  `INSTALLER-EN-5-ETAPES.pdf`, à imprimer et à lui remettre.

---

## 1. Ce qu'il faut

| Élément | Détail |
|---|---|
| Windows | 10 ou 11 |
| Python | 3.12 ou plus récent — <https://www.python.org/downloads/windows/> |
| Espace disque | 300 Mo environ |
| Réseau | Internet **pendant** l'installation, aucun accès ensuite |

**Pendant l'installation de Python, cocher « Add python.exe to PATH ».** Sans
cette case, rien ne fonctionnera et le message d'erreur sera obscur.

---

## 2. Installation simple (recommandée)

1. Copier le dossier à l'emplacement définitif : `C:\Infirmerie`. Éviter le
   Bureau et les dossiers synchronisés (OneDrive, Dropbox) : une base de
   données déplacée pendant une écriture se corrompt.

2. **Double-cliquer sur `installer.bat`.**

3. Appuyer sur Entrée, puis saisir le mot de passe deux fois quand il le
   demande. Rien ne s'affiche pendant la frappe.

L'installateur enchaîne alors sept étapes :

| # | Étape | Ce qu'elle fait |
|---|---|---|
| 1 | Environnement | Crée `.venv`, isolé du reste du PC |
| 2 | Composants | Télécharge Django et ses dépendances |
| 3 | Base | Prépare une base vide, aucun dossier patient |
| 4 | Comptes | Crée `dr.benali`, `secretariat`, `admin` et applique le mot de passe |
| 5 | Fourchettes | Charge 13 paramètres d'hématologie et 28 de biochimie |
| 6 | Production | Crée la clé de signature du poste et rassemble les fichiers d'affichage |
| 7 | Vérification | Contrôle que les trois comptes se connectent |

**Si une étape échoue, l'installation s'arrête.** Elle ne laisse jamais un
poste à moitié configuré : le message indique quoi faire.

> Le mot de passe n'est **jamais** écrit sur le disque. Il n'existe que dans
> la tête de la personne qui le saisit.

---

## 3. Annexe : installation manuelle

Pour un poste où l'installateur ne peut pas être utilisé, ou pour recommencer
une étape après une erreur.

```
cd C:\Infirmerie
python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py creer_comptes
.venv\Scripts\python.exe manage.py renouveler_mots_de_passe --mot-de-passe "<phrase choisie>"
.venv\Scripts\python.exe manage.py charger_references
.venv\Scripts\python.exe manage.py importer_fourchettes fourchettes-biochimie.csv
.venv\Scripts\python.exe manage.py collectstatic --noinput
```

Puis créer la clé de signature du poste, qui bascule l'application en mode
production (plus de traces d'erreur détaillées à l'écran) :

```
.venv\Scripts\python.exe -c "import secrets,pathlib; pathlib.Path('.secret-key').write_text(secrets.token_urlsafe(64))"
```

Contrôles :

```
.venv\Scripts\python.exe manage.py verifier_connexion --mot-de-passe "<phrase choisie>"
.venv\Scripts\python.exe manage.py verifier_unites
```

Attendu : « Tous les comptes se connectent. » et « Aucune incohérence détectée ».

---

## 4. Lancer

Double-cliquer sur **`lancer.py`**. L'application s'ouvre dans le navigateur.

Pour un raccourci sur le Bureau : clic droit sur `lancer.py` → *Envoyer vers* →
*Bureau (créer un raccourci)*. Renommer le raccourci « Infirmerie ».

L'adresse `http://infirmerie` (sans numéro de port) demande une modification du
fichier hosts de Windows, réservée à l'administrateur : `installer_nom.bat`.

---

## 5. Tâches automatiques

### Sauvegarde — à faire le jour de l'installation

Double-cliquer sur **`installer_sauvegarde.bat`**. Une tâche Windows est créée :
chaque lundi à 12h30, `sauvegarde_auto.bat` copie `db_reelle.sqlite3` dans
`sauvegardes/` et écrit une ligne dans `sauvegardes\journal_sauvegarde.log`.

Heure différente : `installer_sauvegarde.bat 18:00`.

Vérifier qu'elle tourne vraiment : attendre le lendemain, puis ouvrir
`journal_sauvegarde.log`. Un journal vide au bout d'une semaine signifie que
la tâche ne s'exécute pas.

**Une sauvegarde sur le même disque ne protège pas d'une panne de disque.**
Copier régulièrement `sauvegardes/` sur une clé USB.

Contrôler qu'une sauvegarde est restaurable :

```
.venv\Scripts\python.exe manage.py verifier_restauration
```

### Point du jour

Double-cliquer sur **`installer_point_du_jour.bat`** : chaque matin à 7h30,
`point_du_jour_local.bat` écrit `sorties\point-du-jour-<date>.pdf`.

Le PDF reste sur le poste, il n'est envoyé nulle part. Si le poste est éteint à
l'heure prévue, Windows ne rattrape pas : relancer `point_du_jour_local.bat` à
la main.

**Le message de 6 h sur téléphone n'existe pas sur ce poste.** Il est produit
par un ordonnanceur externe installé sur le poste de développement.

---

## 6. Conservation des dossiers

Aucune purge automatique n'est armée. Quand la durée de conservation est
arrêtée avec l'établissement, la commande existe :

```
.venv\Scripts\python.exe manage.py purger --avant 2021-01-01
```

Sans `--confirmer`, elle affiche seulement ce qu'elle supprimerait. Avec,
elle supprime et inscrit l'opération au journal d'accès — trace qui, elle,
n'est jamais effacée.

**Ne jamais lancer cette commande sur une base dont la sauvegarde n'a pas été
vérifiée.**

---

## 7. Ce que ce paquet ne contient pas

**Aucune donnée patient.** La base est vide à l'installation.

**Aucun mot de passe.**

**Aucun outil d'ouverture réseau** (tunnel, règle de pare-feu). L'accès
distant passe par un VPN, jamais par une IP publique.

---

## 8. Avant la mise en service réelle

- [ ] Les trois comptes se connectent
- [ ] Mot de passe noté, fiche d'accès rangée
- [ ] Sauvegarde planifiée **et** restauration testée
- [ ] Point du jour planifié (ou décision de ne pas l'utiliser)
- [ ] Durée de conservation des dossiers définie avec l'établissement
- [ ] Chiffrement du disque (BitLocker) activé si le poste est transportable

---

## 9. En cas de problème

| Symptôme | Cause probable |
|---|---|
| `python` n'est pas reconnu | La case « Add to PATH » n'était pas cochée à l'installation |
| L'installateur s'arrête à l'étape 2 | Pas d'accès Internet sur ce poste |
| Page blanche ou erreur 400 | Adresse incorrecte : utiliser celle affichée par `lancer.py` |
| L'application s'affiche sans style | `collectstatic` n'a pas été exécuté (annexe, section 3) |
| « Identifiant ou mot de passe incorrect » | Vérifier qu'on est bien sur **ce** poste, pas une autre copie |
| Le port est déjà pris | Une autre fenêtre de l'application est restée ouverte |
