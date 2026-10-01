# Application Infirmerie

Gestion des dossiers patients et des bilans de santé pour une infirmerie.
Application locale (Django + SQLite), prévue pour un poste Windows.

## Démarrer

Double-cliquer sur **`demarrer.bat`**, puis ouvrir <http://127.0.0.1:8000>

### Comptes de démonstration

| Rôle | Identifiant | Mot de passe |
|---|---|---|
| Soignant | `dr.benali` | `Infirmerie2026!` |
| Secrétariat | `secretariat` | `Infirmerie2026!` |
| Administrateur | `admin` | `Infirmerie2026!` |

Mot de passe commun aux trois : `Infirmerie2026!`

## Rôles

- **Secrétariat** — recherche et création de dossiers, saisie administrative.
  N'a **pas** accès au dossier clinique, aux constantes ni aux résultats.
  Le contrôle est fait côté serveur : un lien direct vers l'URL renvoie
  une erreur 403, pas seulement une page masquée.
- **Soignant** — accès complet : consultations, bilans, prescription,
  lecture des constantes.
- **Administrateur** — accès complet + interface Django à `/admin/`.

Les rôles sont portés par des groupes Django (`secretariat`, `soignant`).
Un compte sans groupe n'a accès à rien : c'est le choix sûr par défaut.

## Ce que fait l'application

**Dossiers patients** — identité, allergies, médecin traitant, suivi.
Numéro de dossier attribué automatiquement (`INF-0001`).

**Consultations** — datées, rattachées à un patient, avec motif, diagnostic,
observations, prescription et constantes (tension, pouls, température,
SpO₂, poids, taille). L'IMC est calculé à la volée. Une taille ou un poids
hors limites plausibles est refusé par le formulaire plutôt que stocké tel quel.

**Bilans de santé** — rattachés à une consultation, donc datés dans le temps :
on peut répondre à « quel était son bilan en mars ? ». Chaque mesure porte sa
propre fourchette de référence ; une valeur hors norme est signalée en rouge
ou orange selon qu'elle est haute ou basse. Une valeur non chiffrée
(« négatif ») est marquée *à qualifier* plutôt que classée à tort.

**Alertes** — allergies affichées en bandeau sur chaque fiche ; valeurs hors
norme et bilans de plus de 12 mois remontés sur l'accueil.

**Suivis** — tâches avec échéance, signalées en retard une fois échues.

**Synthèse imprimable** — page HTML prête à imprimer en PDF, avec bandeau
d'allergies, dernières consultations et bilans annotés. C'est le document à
transmettre à un spécialiste.

## Sauvegarde

Double-cliquer sur **`sauvegarder.bat`**. Les 30 dernières sauvegardes sont
conservées dans `sauvegardes/`.

Restauration :
```
python sauvegarder.py --restaurer sauvegardes/infirmerie_2026-09-30_101500.db
```

À faire régulièrement, et copier une sauvegarde sur une clé USB : une
sauvegarde restée sur le même disque ne protège pas d'une panne de disque.
À tester une fois : restaurer pour de vrai, pour vérifier que ça marche.

## Accès distant

L'application n'écoute que sur `127.0.0.1` : elle n'est **pas** exposée sur
Internet. Pour y accéder depuis l'extérieur, configurer un VPN sur le routeur
ou la box (WireGuard, ou le VPN intégré de la box fibre). On se connecte alors
au réseau de l'infirmerie par tunnel chiffré. **Ne pas ouvrir un port
vers cette application** : les données de santé n'ont pas à être accessibles
depuis l'extérieur du bâtiment par une IP publique.

## Structure

```
conf/                  réglages, routes
dossier/
  models.py            Patient, Consultation, Bilan, Mesure, Allergie, Suivi
  views.py             vues et contrôle des permissions
  permissions.py       rôles secrétariat / soignant
  forms.py             formulaires de saisie
  tests.py             21 tests de parcours et de permissions
  management/commands/
    seed_demo.py       données de démonstration
    verifier_pages.py  rend chaque écran et affiche son code de réponse
templates/dossier/     écrans
sauvegarder.py         sauvegarde / restauration
```

## Journal d'accès

Toute ouverture de dossier, création, modification, suppression, export et
connexion est journalisée dans `JournalAcces` (visible dans
l'administration Django, section « Journal d'accès », en lecture seule).

**Le journal ne contient aucune donnée clinique** : ni valeur biologique, ni
constante, ni nom de patient. Il référence le dossier (`INF-0001`) et
l'utilisateur, pas le contenu. C'est volontaire : un journal contenant les
résultats serait lui-même un fichier de données de santé à protéger. Deux
tests verrouillent cette propriété.

Un échec d'écriture du journal **ne bloque pas** l'accès : le dossier reste
accessible, l'incident est signalé sur la console. Bloquer l'accès sur une
panne de journal rendrait l'infirmerie inutilisable.

Désactivation : `INFIRMERIE_JOURNAL=0`.

## Vérifications

```
python manage.py test dossier      # 32 tests
python manage.py verifier_pages    # rend les 12 écrans pour les 2 rôles
python manage.py verifier_connexion
```

## Mise en service réelle

Créer un fichier `secret.env` **hors du dépôt**, et le charger avant de
lancer :

```
set INFIRMERIE_SECRET_KEY=<50 caractères aléatoires ou plus>
set INFIRMERIE_DEBUG=0
```

Générer une clé :
```
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

L'application **refuse de démarrer** en mode production sans clé : c'est
voulu, pour qu'un poste mis en service sans cette configuration reste
inutilisable plutôt qu'exposé.

Ce qui est fait et vérifié :

- [x] `SECRET_KEY` hors du fichier de configuration, lue depuis l'environnement
- [x] `DEBUG` piloté par l'environnement
- [x] Journal d'accès en place, en lecture seule dans l'administration
- [x] Permissions contrôlées côté serveur, testées
- [x] Aucune donnée clinique dans le journal ni dans les URL
- [x] Accès distant uniquement par VPN, jamais de port ouvert

À faire avec l'établissement :

- [ ] Changer le mot de passe du compte `admin`
- [ ] Choisir le VPN avec l'informaticien
- [ ] Migrer vers PostgreSQL si le volume le justifie
- [ ] Fourchettes de référence validées par un biologiste
- [ ] Définir la durée de conservation et le sort des données au départ d'un patient
- [ ] Procédure de purge du journal (la commande existe, la politique reste à fixer)
