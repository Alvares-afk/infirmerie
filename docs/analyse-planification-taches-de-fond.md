# Planification automatique de tâches de fond — proposition de conception

Projet : `C:\Users\Alvarès\infirmerie-app` — Django 6.1.1 + SQLite, poste Windows local.
Référence : `docs/agent-spec-LAB04.txt` §5 (« Exécution planifiée (tâches de fond) après
validation finale de l'infirmier(e) »), Étape 4 (« préparer les brouillons de relance
(sans les envoyer) »).

**Statut : note de conception. Aucun fichier du projet n'a été modifié.**

---

## 0. Contrainte structurante, énoncée avant tout le reste

Le module `dossier/relances.py` n'écrit que des brouillons. Le test
`dossier/test_relances.py::test_13_aucun_envoi_reseau_dans_le_code` échoue si les mots
`requests`, `urllib`, `http.client`, `smtplib`, `sendmail`, `send_mail`, `EmailMessage`,
`socket` apparaissent dans ce fichier. Le modèle `Relance` porte lui-même la consigne :
un champ « envoyée » documente *un envoi fait ailleurs*, jamais une action automatique.

**La planification ne peut donc pas être une fonction d'envoi.** Elle est une fonction de
*production de brouillons*. Toute conception qui refuse cette symétrie est hors sujet,
quelle que soit sa qualité technique. Le test 13 doit être élargi à tous les nouveaux
fichiers de planification (§4).

---

## 1. Quelles tâches de fond sont justifiées — et lesquelles ne le sont pas

### 1.1 Justifiées (lecture, calcul, rédaction de brouillons)

| Tâche | Ce qu'elle fait | Pourquoi elle a du sens |
|---|---|---|
| **T1 — Rédiger les brouillons de relance** | Appelle `proposer_relances_global()` déjà existant. Échéance dépassée, bilan absent, suivi non fait. | C'est la tâche la plus justifiée : les trois faits sont **déjà dans le dossier**, aucun n'est déduit, et l'humain ne peut pas les manquer à l'œil sur 200 patients. Le brouillon ne part pas. |
| **T2 — Préparer le briefing du jour** | Appelle `briefing_du_jour()` déjà existant : allergies sévères, valeurs hors norme, suivis échus, bilans de plus de 12 mois. | Le point quotidien commence le matin ; l'avoir calculé la veille rend le soignant disponible dès l'ouverture. Risque nul : c'est un simple affichage. |
| **T3 — Signaler une panne silencieuse** | Vérifie que T1 et T2 ont bien tourné ; sinon produit une entrée visible. | Une planification qui échoue en silence est pire que l'absence de planification. Voir §5. |
| **T4 — Proposer la purge des brouillons périmés** | Marque les brouillons non validés vieux de plus de N mois. | Une boîte de brouillons qui grossit sans fin fait ignorer les messages utiles. **Action destructrice : à valider par l'infirmier(e), jamais automatique.** |

T1 et T2 ne demandent **aucun nouveau modèle de données métier** : les fonctions
existantes (`proposer_relances_global`, `briefing_du_jour`) sont déjà pures et testées.
C'est un point important : le risque de la planification est concentrated dans
l'ordonnanceur, pas dans la logique métier.

### 1.2 Ce qu'il ne faut PAS automatiser — liste explicite

Répondre « tout automatiser » serait la faute la plus coûteuse de la conception. Voici ce
qui est **exclu**, avec la raison :

- **L'envoi de quoi que ce soit** — e-mail, SMS, notification, quoi que ce soit. Sans
  discussion. C'est l'interdiction de la spec, et une relance envoyée à tort à un patient
  est un dommage réel et irréversible (patient inquiet, dossier réel, mentions
  administratives erronées diffusées hors du contrôle de l'infirmerie).
- **Toute interprétation clinique** : classer une valeur, conclure sur un état de santé,
  recommander un soin. Le briefing signale une valeur hors norme, il ne la commente pas.
  La règle d'or de la spec (aucune hallucination) interdit qu'une tâche de fond, exécutée
  sans personne devant l'écran, produise une conclusion médicale.
- **La création ou la modification d'un dossier patient** : pas de nouveau patient, pas de
  consultation, pas de bilan, pas de suivi. La planification ne fait que créer des
  brouillons et des rapports.
- **Marquer un `Suivi` comme `fait`**, ou une `Relance` comme `VALIDEE` / `ENVOYEE`.
  Ce sont des décisions humaines, et `validee_par` / `validee_le` sont précisément les
  champs qui portent cette décision. Une tâche de fond qui les remplirait fabriquerait une
  fausse trace d'audit.
- **La suppression d'un brouillon sans validation** : une relance validée puis non
  tracée est un trou dans le dossier. T4 reste une proposition, pas un nettoyage.
- **Les relances à patients inactifs** : `proposer_relances_global` filtre déjà `actif=True`.
  Une tâche qui contournerait ce filtre relancerait des patients sortis de l'infirmerie.
- **La sauvegarde automatique de la base** : `sauvegarder.py` existe et se lance à la main
  pendant que le poste est éveillé. Une copie SQLite pendant qu'un filtre écrit peut
produire un fichier corrompu — la sauvegarde nocturne automatique est un *piège*,
  pas une amélioration.

### 1.3 Le point qu'il faut trancher avec l'infirmier(e)

« Tâches de fond » dans la spec est formulé en abstrat. Ce que la spec **ne dit pas** :
à quelle fréquence, et à quelle heure. Trois lectures plausibles :

1. **matinale** — 6 h 30, pour que le briefing soit prêt à l'ouverture ;
2. **à la demande** — c'est-à-dire pas du tout planifiée ;
3. **toutes les nuits** — la formulation « tâche de fond » invite à cette lecture.

Je ne tranche pas : c'est une décision d'organisation, pas une décision technique. La note
suppose (1), et signale que (3) est explicitement déconseillée (§5.2).

---

## 2. Mécanisme technique adapté à un poste Windows local, sans serveur

### 2.1 Ce qui est écarté, et pourquoi

- **cron / crontab** : n'existe pas nativement sous Windows. Le portage (Cron via Git
  Bash, `schtasks`) est disponible mais l'utilisateur final d'une infirmerie n'installera
  pas Git Bash pour faire tourner un briefing.
- **Celery + Redis / RabbitMQ** : un broker à installer et à maintenir sur un poste de
  travail, pour quelques tâches qui prennent quelques secondes. Hors de proportion.
- **`runserver` en daemon** : `runserver` est un serveur de développement ; s'appuyer sur
  son cycle de vie pour déclencher des tâches est fragile par construction (il se relance,
  il s'arrête au premier Ctrl+C, il ne tourne pas quand le poste est éteint).
- **Le serveur Vercel** : le dépôt contient `.vercel` et le chemin `DATABASE_URL` (Postgres
  hébergé, patients fictifs). Un planificateur hébergé n'y existe pas sous la forme
  « processus qui tourne chez l'infirmier ». **La planification est donc une fonction
  locale, à aucun moment une fonction hébergée** — c'est aussi cohérent avec le fait que
  la base réelle est locale.

### 2.2 La solution proposée : Tâche de Planification Windows + commande Django

Trois éléments, tous déjà compatibles avec l'existant :

**(a) Une commande Django** `manage.py taches_de_fond` qui :
1. ouvre sa propre connexion SQLite et pose un verrou ;
2. exécute T1 puis T2 puis T3 ;
3. écrit une ligne d'exécution en base (§3) ;
4. retourne un code de sortie non nul en cas d'échec.

C'est la seule unité de logique. Elle est **testable directement** :
`manage.py test dossier` peut l'appeler sans Windows, sans dépendre du Planificateur.

**(b) Une tâche du Planificateur de tâches Windows** qui l'appelle :

```
schtasks /Create /TN "Infirmerie - taches de fond" /SC DAILY /ST 06:30 ^
        /TR "\"C:\...\infirmerie-app\.venv\Scripts\python.exe\" manage.py taches_de_fond" ^
        /RL LIMITED
```

Le Planificateur de tâches est présent sur toutes les versions de Windows 10/11. Il
s'exécute **que l'utilisateur soit connecté ou non** (`/RL LIMITED` suffit ; ne pas
demander de privilèges élevés). Trois réglages à poser dans l'interface ou par XML :
« Quelle que soit la fréquence, ne pas démarrer une nouvelle instance » et « Si la tâche
n'a pas démarré, démarrer dès que possible après un démarrage tardif ».

Ce qui n'est **pas** fait : un service Windows à installer (`pywin32`, installation
administrateur, désinstallation à prévoir). Pour trois tâches de dix secondes, le
Planificateur suffit, et il est réversible en une commande.

**(c) Un lanceur manuel** `taches_de_fond.bat`, miroir de `sauvegarder.bat`, pour que
l'infirmerie puisse déclencher la même chose à la main — c'est le filet de sécurité du §5.1.

### 2.3 Pourquoi pas « dans le code de la requête HTTP »

On pourrait déclencher les tâches à la première connexion de la journée (`AppConfig.ready`
non — plutôt une vérification dans une vue). C'est tentant : pas de configuration
Windows. Deux raisons de l'écarter :
- la première connexion peut ne jamais avoir lieu (poste éteint le lundi) ;
- une requête HTTP qui fait un travail de fond se retrouve bloquée, expire en 30 secondes,
  et le soignant voit une page lente. Le travail de fond n'a rien à faire dans le chemin
  d'une requête.

Une variante acceptable existe, à garder en tête : la vue d'accueil *lit* le dernier
résultat (T2) et affiche « briefing non généré aujourd'hui » si la date est dépassée.
Elle ne déclenche rien. C'est un affichage d'état, pas un déclencheur.

---

## 3. Modèle de données

Quatre tables sont proposées, mais **une seule est réellement nécessaire au premier
jalon** : `ExecutionTache`. Les trois autres évitent des antidatations fragiles.

### 3.1 `Tache` — le catalogue (le code, pas les données)

```python
class Tache(models.Model):
    class Categorie(models.TextChoices):
        RELANCE = "relance", "Brouillons de relance"
        BRIEFING = "briefing", "Briefing du point quotidien"
        SURVEILLANCE = "surveillance", "Contrôle de bon fonctionnement"

    cle = models.CharField("clé", max_length=40, unique=True)   # "relances", "briefing"
    libelle = models.CharField("libellé", max_length=100)
    categorie = models.CharField("catégorie", max_length=20, choices=Categorie.choices)
    active = models.BooleanField("active", default=True)
    # Le code de la tâche est référencé par son chemin de module, jamais stocké
    # comme du Python exécutable : c'est le garde-fou du §4.
    chemin = models.CharField("chemin de la fonction", max_length=200)
```

**Décision à assumer** : `chemin` est une chaîne, résolue par `import_string`, et la
liste blanche est du code, pas une donnée (§4). Le modèle ne doit jamais pouvoir élargir
la surface exécutable par une simple ligne en base.

### 3.2 `Planification` — quand, et dans quel état

```python
class Planification(models.Model):
    tache = models.ForeignKey(Tache, on_delete=models.PROTECT, related_name="planifications")
    heure = models.TimeField("heure", default=time(6, 30))
    jours_semaine = models.CharField("jours (0=lun…6=dim)", max_length=7, default="1111111")
    active = models.BooleanField("active", default=True)
    consecutive_echecs = models.PositiveSmallIntegerField("échecs consécutifs", default=0)
    derniere_execution = models.ForeignKey("ExecutionTache", null=True, blank=True,
                                           on_delete=models.SET_NULL, related_name="+")
```

Windows ne sait pas exprimer « 6 h 30 en semaine » dans le Planificateur de tâches ; c'est
donc Django qui porte la règle des jours (`jours_semaine`), et le Planificateur se contente
d'appeler tous les jours. `consecutive_echecs` est le compteur du §5.3.

### 3.3 `ExecutionTache` — la trace

```python
class StatutExecution(models.TextChoices):
    OK = "ok", "Terminée"
    ECHEC = "echec", "Échec"
    PARTIELLE = "partielle", "Terminée avec avertissement"
    REFUSEE = "refusee", "Refusée (garde-fou)"

class ExecutionTache(models.Model):
    tache = models.ForeignKey(Tache, on_delete=models.PROTECT, related_name="executions")
    planifiee_pour = models.DateTimeField("planifiée pour", db_index=True)
    debut = models.DateTimeField("début", auto_now_add=True)
    fin = models.DateTimeField("fin", null=True, blank=True)
    statut = models.CharField("statut", max_length=12, choices=StatutExecution.choices)
    executeur = models.CharField("exécuté par", max_length=60, default="planificateur")
    nb_brouillons = models.PositiveIntegerField("brouillons produits", default=0)
    nb_lignes_briefing = models.PositiveIntegerField("lignes de briefing", default=0)
    detail = models.TextField("détail", blank=True)
```

Trois remarques :

- **`executeur` distingue `planificateur` d'un `utilisateur`**. Une tâche de fond et un
  clic manuel produisent la même ligne de trace, mais la distinction doit exister : c'est la
  question « qui a fait ça ? » qu'on posera un jour.
- **Le journal ne contient aucun contenu médical.** `nb_brouillons` est un compte, pas un
  texte. La règle de `journalisation.py` s'applique intégralement : une trace d'exécution
  qui recopierait les objets d'un brouillon deviendrait un second fichier de données de
  santé.
- **`StatutExecution.REFUSEE`** n'est pas décoratif : c'est l'état dans lequel tombe
  l'exécution si le garde-fou du §4 refuse de tourner. Il faut pouvoir le voir.

### 3.4 `VerrouExecution` — un seul passage à la fois

Un `BooleanField` (`en_cours`) sur un modèle singleton suffit ; inutile de faire
plus. Deux volets :

- **fichier** : `FileLock` sur un `.lock` dans le répertoire du projet — empêche deux
  processus (Planificateur + clic manuel) de tourner simultanément, y compris si SQLite
  le verrouillerait déjà ;
- **base** : ligne unique `VerrouExecution(cle="taches_de_fond", en_cours=True, debut=...)`
  rafraîchie toutes les 30 s ; si `debut` date de plus de 15 minutes, le verrou est considéré
  comme orphelin et repris.

### 3.5 Ce qu'il ne faut **pas** modéliser

Une table `Notification`, une table `ParametreDePlanification` par utilisateur, un
`CRON_Expression` libre : le premier est un système de messagerie, le deuxième n'a pas de
demandeur identifié, le troisième déplace le risque vers une syntaxe que personne ne
relira.

---

## 4. Garantir que la planification ne peut jamais envoyer

C'est le point le plus important de la note. Cinq verrous, du plus faible au plus fort.

**V1 — Liste blanche de modules interdits, testée.** Le test 13 existe pour `relances.py`.
Il doit être généralisé à **tout le paquet de planification** :

```python
INTERDITS = ["requests", "urllib", "http.client", "smtplib", "socket",
             "send_mail", "EmailMessage", "sendmail"]
```

et porter sur `dossier/planification/**` **et** sur les modules importés par lui
(`relances.py`, `briefing.py`). Un test qui ne lit qu'un fichier laisse une porte ouverte
par le simple fait d'importer un helper réseau dans un autre fichier.

**V2 — Liste blanche positive des fonctions exécutables.** `chemin` (§3.1) ne peut pointer
que vers une fonction nommée `tache_...` déclarée dans un module d'une liste blanche
explicite. Un `import_string` générique sur une chaîne venant de la base est une
exécution arbitraire déguisée en configuration.

**V3 — Interdiction au niveau des modèles, pas seulement du code.** Garde-fou le plus
durable, parce qu'il survit au refactoring : **les tâches de fond n'ont aucun droit
d'écriture sur les champs `validee_par`, `validee_le`, `envoyee_le` et `Suivi.fait`.**
Concrètement, la couche d'exécution filtre les champs mis à jour, ou (mieux) passe par un
`save(update_fields=[...])` dont la liste est une constante du module. Écrire une seule
ligne qui touche `Suivi.fait` depuis du code de planification doit faire échouer un test
dédié, exactement comme le test 13 échoue sur un `import smtplib`.

**V4 — Environnement sans réseau au moment de l'exécution.** Le lanceur
`taches_de_fond.bat` s'exécute dans un environnement où les variables de configuration
SMTP et tout `DATABASE_URL` distant sont explicitement neutralisés. C'est une défense en
profondeur, pas une garantie : un poste Windows ne peut pas être facilement mis en coupure de réseau
pour un seul processus. **Cette limite doit être assumée et écrite dans la note**, pas
présentée comme une protection.

**V5 — Journalisation de toute production de brouillon.** Chaque brouillon créé par une
tâche de fond porte la trace de l'exécution qui l'a produit (`execution` FK sur `Relance`).
On sait donc, pour chaque brouillon du dossier, s'il vient d'un clic ou d'une exécution
planifiée. Sans cette FK, « qui a rédigé ce brouillon ? » est sans réponse.

**Pourquoi cinq.** V1 à V3 sont des contraintes de code, vérifiables par `manage.py test`.
V4 est une bonne pratique. V5 est une exigence d'audit. Aucune ne dépend d'une
configuration extérieure.

---

## 5. Risques

### 5.1 Une tâche qui tourne dans le vide

*Symptôme :* le Planificateur est créé, la commande est mal orthographiée ou le chemin du `.venv`
a changé après un déplacement de dossier. Le Planificateur exécute, l'erreur part dans
l'historique que personne n'ouvre, et aucun brouillon n'apparaît pendant trois mois. Le
soignant croit que la planification fonctionne.

*Contre-mesures :*
- `nb_brouillons` et `nb_lignes_briefing` sont affichés sur la page d'accueil avec la date
  de dernière exécution — **la santé de la planification est visible par l'infirmier(e),
  pas dans un fichier journal** ;
- le lanceur `.bat` manuel, exécutable sans rien configurer ;
- la commande écrit sur stdout, donc le Planificateur garde l'historique, mais c'est un
  complément, pas la détection ;
- **détecter le cas dégénéré où tout fonctionne et qu'il n'y a simplement rien à faire** :
  `nb_brouillons = 0` sur 30 jours est un résultat légitime, pas une panne. Les deux
  doivent se distinguer sur l'écran, sinon le soignant aprend à ignorer l'indicateur.

### 5.2 Une tâche qui tourne la nuit, sans surveillance

*Risques précis :*

- **La nuit, aucune donnée ne change** dans une infirmerie fermée. Une exécution nocturne
  ne produira donc **rien de plus** qu'une exécution matinale, pour le même coût. Elle
  augmente le risque sans augmenter la valeur. → exécution matinale, ou manuelle.
- **Une exécution sans personne devant l'écran qui échoue à 3 h** reste en échec jusqu'au
  matin ; si la cause est une base verrouillée, elle ne se résout pas seule.
- **Le verrou d'exécution peut devenir orphelin** si le poste est éteint au milieu d'une
  exécution (arrêt brutal, coupure). D'où la règle des 15 minutes (§3.4) : sans elle,
  la planification est bloquée définitivement et personne ne comprend pourquoi.
- **Un cas particulier** à refuser explicitement : la purge T4 la nuit, quand personne ne
  peut surveiller ce qu'elle supprime. T4 ne tourne qu'à la demande.

### 5.3 Une panne silencieuse

Trois modes distincts, trois réponses différentes :

| Mode | Détection | Réponse |
|---|---|---|
| La tâche ne démarre pas (poste éteint, tâche désactivée) | `derniere_execution` ancienne alors que l'heure est passée | Bandeau sur la page d'accueil : « briefing non généré aujourd'hui » |
| La tâche démarre et échoue | `StatutExecution.ECHEC` + trace | Message sur la page d'accueil, avec le message d'erreur |
| La tâche réussit mais ne produit rien | `nb_brouillons = 0` | **Rien** — c'est le fonctionnement normal |

`consecutive_echecs` passe à 3 : à ce seuil, on peut afficher un avertissement plus
visible (« la planification échoue depuis 3 exécutions »). Trois, et non un : un échec
isolé arrive — le poste a été redémarré au mauvais moment — et une alerte qui se déclenche
dessus devient elle-même un bruit, donc ignorée.

**Le cas limite qu'il faut dire** : si la planification est la seule chose qui génère les
brouillons, une panne de trois jours signifie trois jours de relances non rédigées. Est-ce
acceptable ? Oui, parce que le travail **n'est pas perdu** : `proposer_relances_global` peut
être relancé à la main et rattrape tout, puisque rien n'est daté de façon irréversible. C'est
un argument fort en faveur de cette architecture : **une tâche de fond idempotente et
relançable n'a pas de fenêtre de perte**. C'est aussi pour cela que T1 ne marque aucun suivi
comme fait — la seule chose qui ferait que le retard ne se rattrape jamais.

---

## 6. Implémentation par étapes

Chaque étape est vérifiable par une commande existante. **Rien n'est écrit avant d'être
testé.**

### Étape 0 — Reformuler la spec (30 min, sans code)
Écrire dans `docs/specification.md`, à côté du module de relances, la règle en une phrase :
*« Une tâche de fond produit des brouillons et des rapports. Elle n'envoie rien, n'interprète
aucun résultat, et ne modifie aucun état clinique. »* Puis faire **valider la fréquence et
l'heure** par l'infirmier(e) (§1.3). Sans cette validation, les étapes suivantes codent une
hypothèse.

### Étape 1 — Le catalogue et la trace (1 jour)
`Tache`, `Planification`, `ExecutionTache`, `VerrouExecution` + migration + données initiales
(migration `RunPython`, pas un `loaddata`).
*Vérification :* `manage.py test dossier` — un test qui crée une `Tache`, une
`Planification`, exécute une tâche bidon et vérifie la ligne d'exécution.

### Étape 2 — Le noyau d'exécution, sans ordonnanceur (1 jour)
`dossier/planification/execution.py` : `executer(tache)`, acquisition du verrou, boucle sur
les tâches du jour, écriture de l'`ExecutionTache`, gestion d'erreur par tâche
(une tâche qui échoue n'empêche pas les autres).
*Vérification :* `manage.py executer_taches --sec` (mode sec, écrit la trace, ne produit
rien) puis `manage.py test dossier`.

### Étape 3 — Le câblage sur les tâches réelles (1 jour)
Les trois fonctions `tache_relances()`, `tache_briefing()`, `tache_surveillance()` dans
`dossier/planification/taches.py`, appelant `proposer_relances_global()` et
`briefing_du_jour()` **tels quels** — pas de réécriture de la logique métier.
*Vérification :* `manage.py test dossier` — les 21 tests existants plus les nouveaux,
et le compte de `db.sqlite3` avant/après. Un test vérifie qu'un second passage immédiat ne
crée **aucun** brouillon supplémentaire (déduplication de `proposer_relances`).

### Étape 4 — Les garde-fous (½ jour, avant toute planification réelle)
- généralisation du test 13 à tout le paquet de planification **et** aux modules importés ;
- test interdisant l'écriture de `Suivi.fait`, `validee_par`, `validee_le`, `envoyee_le`
  depuis le code de planification (V3) ;
- liste blanche positive des chemins exécutables (V2).
*Vérification :* `manage.py test dossier`. **Cette étape n'est pas négociable et ne peut
pas être faite après la mise en place du Planificateur** : un garde-fou installé après
l'automatisation est un garde-fou que personne n'écrit.

### Étape 5 — La commande et le lanceur (½ jour)
`manage.py taches_de_fond` avec `--sec`, `--tache=<clé>`, `--force`.
`taches_de_fond.bat` à côté de `sauvegarder.bat`.
*Vérification :* `taches_de_fond.bat` lancé à la main, deux fois de suite ; la seconde ne
crée rien.

### Étape 6 — L'ordonnanceur Windows (½ jour)
Création de la tâche du Planificateur, **en mode désactivé d'abord**, testée à la main via
« Exécuter », puis activée.
*Vérification :* une seule exécution manuelle réussie ; la tâche apparaît dans le
Planificateur avec l'historique.

### Étape 7 — La visibilité (½ jour)
La page d'accueil affiche : date de dernière exécution par tâche, `nb_brouillons`,
`nb_lignes_briefing`, et le bandeau d'avertissement en cas d'échec répété. Écran
d'administration en lecture seule des 50 dernières exécutions.
*Vérification :* `manage.py verifier_pages` — l'accueil rend toujours, pour les trois rôles.

### Étape 8 — Recette (1 semaine en usage réel)
La planification tourne réellement pendant une semaine, à côté du travail manuel fait en
parallèle. On compare les brouillons produits. **On ne désactive pas la production manuelle
avant d'avoir vu une semaine de tâches planifiées conformes.**

### Ce qui reste hors de portée
Tout ce qui touche à l'envoi. Si un jour un envoi est demandé, c'est un autre projet, avec
un autre modèle de validation, et la décision appartient à l'infirmier(e) — pas à une
fonction qui tourne seule à 6 h 30.

---

## 7. Récapitulatif

| Question | Réponse |
|---|---|
| Quoi automatiser | Rédiger les brouillons, préparer le briefing, surveiller, proposer une purge |
| Quoi ne surtout pas | Envoyer, interpréter, créer ou modifier un dossier, valider, marquer un suivi fait, sauvegarder la base |
| Comment | Une commande Django + une tâche du Planificateur de tâches Windows + un lanceur `.bat` |
| Modèle de données | `Tache`, `Planification`, `ExecutionTache`, `VerrouExecution` ; `Relance.execution` pour la traçabilité |
| Comment garantir « jamais d'envoi » | 5 verrous : test réseau étendu, liste blanche de fonctions, interdiction d'écrire les champs de validation, environnement sans configuration d'envoi, traçabilité de chaque brouillon |
| Risque principal | La panne silencieuse — traitée par un indicateur visible par l'infirmier(e), pas par un fichier journal |
| Point à trancher | L'heure et la fréquence, par l'infirmier(e). Aucune exécution nocturne recommandée. |
