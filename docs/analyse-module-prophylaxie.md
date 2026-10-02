# Module Prophylaxie — analyse et proposition de conception

Statut : **phase de conception**. Aucun fichier de l'application n'a été modifié.
Ce document propose ; il ne décide d'aucun contenu médical.

---

## 0. Point préalable : un terme à trancher

La demande mentionne « les bilansRockZero ». Le terme est ambigu :

- **RockZero** est un nom de **système d'analyse de proximité (POCT)** — donc
  cela désignerait des *bilans produits par ce type d'appareil*, avec pour
  caractéristique des **fourchettes propres au fabricant et à la cassette**,
  différentes de celles du laboratoire central.
- « bilans de rocks » au sens d'examens pedaliers / de rocks (bande roamane,
  testing d'effort…) : aucune interprétation médicale n'est possible ici.

**Conséquence pour la conception** : si RockZero est bien un POCT, c'est
exactement le cas qui justifie la paramétrisation par laboratoire (§2). La
suite du document traite ce cas. **À confirmer par l'établissement** avant
d'écrire le moindre modèle.

---

## 1. Contenu fonctionnel du module

Trois sous-domaines, à garder séparés dans le code et dans les écrans :

### 1.1 Rappels de vaccins

Sert la mission de l'agent : *« Rédiger des relances et rappels de vaccins,
restés en attente de validation »*.

- Enregistrer un vaccin réalisé (date, produit, lot, voie, site, soignant) —
  rattaché à la **consultation**, comme tout acte.
- Consulter l'historique vaccinal d'un patient (trié par date).
- Proposer un rappel : **un brouillon de `Relance` de type `VACCIN`**
  (le `TypeRelance.VACCIN` existe déjà dans `models.py`, inutilisé à ce jour).
  Jamais d'envoi automatique — la règle du module `relances.py` s'applique
  telle quelle.
- État du calendrier : à jour / à jour sous réserve / inconnu. Un dossier
  sans historique vaccin **n'est jamais** « à jour » : il est « inconnu ».

### 1.2 Bilans (sanguins, RockZero ou autre)

- Saisie rattachée à la consultation, comme aujourd'hui.
- **Interprétation contre les fourchettes du laboratoire émetteur**, plus une
  **trace figée** de la fourchette au moment de la saisie.
- Vue « RockZero » = un sous-ensemble de bilans, filtré sur l'appareil/labo.

### 1.3 Protocoles de prophylaxie

- Référentiel de protocoles **saisis par l'établissement** (titre, texte,
  périmètre, date de version, validateur).
- Un patient est **couvert par** un protocole, avec date de début.
- Génère des échéances de suivi, qui alimentent `Suivi` et donc le briefing.
- **Aucun protocole n'est créé d'office.** Le référentiel démarre vide : c'est
  l'établissement qui le remplit. Une base pré-remplie de protocoles serait
  exactement le genre de contenu médical inventé que la règle d'or interdit.

---

## 2. Modèle de données proposé

### 2.1 Le point central : rendre les fourchettes paramétrables par laboratoire

**Constat actuel** : `Mesure` porte `norme_min`, `norme_max`, `reference` en
dur, saisis à la main à chaque ligne. `seed_demo` en injecte des valeurs
figées. C'est le risque identifié : un résultat anormal peut passer pour
normal, soit parce que la fourchette est fausse, soit parce qu'aucune
fourchette n'a été saisie (→ valeur classée « normal » par défaut, voir §3.2).

**Réponse en trois couches**, du plus général au plus fin :

#### Couche 1 — `Laboratoire`

```
Laboratoire(nom, code, actif, date_validation,
            valide_par FK User, date_debut_validite, date_fin_validite)
```

- Un laboratoire = un émetteur de fourchettes (interne,.external, POCT).
- `date_validation` / `valide_par` : la fourchette est **signée**, pas
  simplement saisie. Exigé par `infirmerie-django` (« validées par un
  biologiste »).

#### Couche 2 — `ReferenceIntervalle` (fourchette par paramètre et par population)

```
ReferenceIntervalle(
    laboratoire FK -> Laboratoire,
    parametre,                       # texte libre, ex. "Hémoglobine"
    code_labo,                       # code exact du laboratoire, tel qu'imprimé
                                    #   sur le compte rendu
    unite,
    sexe,                            # "", "F", "M"  ("" = les deux)
    age_min, age_max,                # entiers, en années, null = non borné
    norme_min, norme_max,            # FloatField null ; les deux null = non chiffré
    texte_reference,                 # ex. "Négatif", "< 0,5" — SANS valeur par défaut
    date_debut, date_fin,            # versionnage
    valide_par FK User,
)
    unique_together (laboratoire, code_labo, sexe, age_min, age_max, date_debut)
```

Points de conception :

- **Sélection par priorité décroissante** : `code_labo` exact d'abord, puis
  `parametre` ; `sexe` spécifique avant `sexe=""` ; borne d'âge la plus
  étroite d'abord. La requête doit être **explicite et testée**, pas
  « le premier trouvé ».
- **`age_min`/`age_max` en années entières** : une conversion date de naissance
  → âge se fait au moment de la lecture, jamais stockée (le skill interdit
  l'âge stocké).
- **`norme_min` et `norme_max` nullables**, avec la contrainte applicative :
  les deux null sur une ligne `texte_reference` seulement ⇒ cette ligne
  **ne classe rien** (cf. `ValeurQualitative`).
- **Versionnage par dates** : changer une fourchette ne réécrit pas
  l'historique. Un bilan de 2023 continue de se lire avec la fourchette de 2023.

#### Couche 3 — `Mesure` : la trace figée

`Mesure` **conserve** `norme_min` / `norme_max` / `reference` (ne pas les
supprimer : ce sont les données du compte rendu), et gagne :

```
    reference_intervalle FK -> ReferenceIntervalle,  null=True, blank=True
    anomalite_figee            CharField, choices: bas|haut|inconnu|normal
   QualificationTexte :

    valeur                    # telle que rendue / dictée
    mesure_id FK -> Mesure,   # ligne quantitative à laquelle elle se rattache
    texte,                    # "négatif", "traces"…
    qualification,            # choix fermé : NEGATIF | TRACES | PRESENT | INDETERMINE
                                # (choices fournies — jamais de texte libre arbitraire)
```

Le double `anormalite` (calculée / figée) est ce qui permet de répondre à
« ce bilan était-il déjà signalé comme anormal en mars ? ».

### 2.2 Vaccins

```
Vaccin(nom, produit, code, actif)                       # référentiel des produits

InjectionVaccine(
    patient FK, consultation FK,                       # rattachée à la consultation
    vaccin FK, date, numero_lot, voie, site,
    statut,          # effectué | refus_contraindication | a_reprendre
    motif,           # texte du refus — OBLIGATOIRE si statut != effectué
    valide_par FK User,
)

StatutVaccin(                                        # calendrier, non statements
    patient FK, vaccin FK,
    statut,          # a_jour | a_preciser | echeance_proche | echeance_depassee
                       | inconnu | non_applicable
    date_reference,  # date pivot : dernière injection connue
    echeance,        # date BUT — calculée depuis le calendrier validé
    source,          # calendrier_id | saisie_manuelle
    motif,           # TOUJOURS renseigné : d'où vient la conclusion
)
```

**Séparation exigée** : `InjectionVaccine` = un **fait** (l'acte a eu lieu).
`StatutVaccin` = un **état**, qui peut être `inconnu`. Les confondre fait
inventer un calendrier à partir de données absentes.

### 2.3 Protocoles

```
Protocole(titre, version, texte, perimetre, population,
          date_debut_validite, date_fin_validite,
          valide_par FK User, source_document)

ProtocolePatient(patient FK, protocole FK,
                 date_debut, date_fin,
                 motif, valide_par)

ProtocoleEtape(protocole FK, ordre, intitule, periodicite_jours|null,
               delai_jours|null, obligatoire,
               precondition, texte_consigne)
```

Les deux modes de périodicité sont **disjoints** et l'un des deux est
obligatoire : `periodicite_jours` (récurrence) **ou** `delai_jours` (échéance
unique). Les deux null ⇒ l'étape est un point d'attention sans échéance
automatique, et l'interface doit le dire.

`precondition` est un texte **non interprété**. Le module ne l'exécute pas : il
ne sait pas évaluer une condition médicale. C'est le soignant qui qualifie.

### 2.4 Migrations

| # | Contenu | Note |
|---|---|---|
| `0004_laboratoire_referenceintervalle` | Labo + intervalles | **additive**, zéro risque |
| `0005_mesure_tracabilite` | `reference_intervalle`, `anomalite_figee`, `QualificationTexte` | null=True partout |
| `0006_vaccins` | `Vaccin`, `InjectionVaccine`, `StatutVaccin` | nouveau |
| `0007_protocoles` | `Protocole*`, `ProtocolePatient`, `ProtocoleEtape` | nouveau |
| `0008_rattachement_labo` | `Bilan.laboratoire` → FK `Laboratoire` | **la seule migration destructive** : `CharField` → `FK` |

⚠ `Bilan.laboratoire` est aujourd'hui un `CharField`. Le passage en FK
exige : champ temporaire, `RunPython` de correspondance exacte des libellés,
puis `RemoveField` + `AddField`. **Les libellés non reconnus deviennent
`laboratoire = NULL` avec un rapport** — jamais un nouveau laboratoire créé
à l'aveugle. L'établissement peut être plusieurs : prévoir `null=True`
sans `unique` pour ne pas bloquer la migration.

---

## 3. Règles de calcul

### 3.1 Interprétation d'une valeur

Ordre strict, en court-circuit :

1. `valeur` vide → `inconnu` / « non renseignée »
2. `valeur` non numérique (« négatif », « traces ») → `inconnu` /
   **« à qualifier »** — et **jamais** comparée à une fourchette
3. numérique, mais **aucune `ReferenceIntervalle` applicable** →
   `inconnu` / **« référence non paramétrée pour ce laboratoire »**
4. numérique + intervalle à **une seule** borne → cette seule borne s'applique
5. numérique + deux bornes → `bas` / `haut` / `normal`

Le point 3 est aujourd'hui le trou réel : dans l'implémentation actuelle,
`norme_min` et `norme_max` à `None` donnent `normal`. C'est un défaut de la
démo, pas une règle. **Proposé** : ne classer `normal` que si au moins une
borne existe **et** que la ligne a une source (`reference` non vide). Sinon
`inconnu`. ⚠ Cette règle durcit le comportement : la suite de tests existante
doit être relue (criterion 8 de la recette, 21 tests).

### 3.2 Date de rappel d'un vaccin

- Pivot = **dernière `InjectionVaccine`** de statut `effectué`.
- Si pivot existe : `echeance = pivot + N` où **N vient d'une ligne
  `CalendrierVaccinal` validée par l'établissement** — jamais d'une constante
  dans le code. Un jour = an ? non. **N est une donnée manquante** (§4).
- Si aucun pivot : statut `inconnu`, motif « aucun vaccin de ce type
  enregistré dans le dossier ». **Aucun `echeance` calculée.**
- Un protocole de rattrapage ou une contre-indication **saisie par le
  soignant** prime sur le calcul, et le motif l'explique.

### 3.3 Périodicité des étapes de protocole

- `periodicite_jours` : échéances = `date_debut + k × N`, à partir du début
  du protocole. Fait une fois → l'étape est marquée faite, pas recalculée.
- `delai_jours` : échéance unique = `date_debut + D`.
- `precondition` non interprétée : la périodicité est affichée avec son texte,
  et l'agent **ne conclut rien** dessus.
- Toute échéance générée devient un `Suivi` (déjà dans le modèle), donc
  notamment visible au briefing et aux relances.

### 3.4 Règle transverse : le champ motif est obligatoire

Toute ligne produite — statut vaccin, échéance, brouillon de relance —
porte `motif`, en termes factuels (« Injection DTP du 14/03/2022, calendrier
Biolys, échéance + 1825 j »). Rappelé par la spec §4.5 : pas de relance
sans motif. Un statut sans motif est interdit à la validation du formulaire.

---

## 4. Ce qui MANQUE et ne peut pas être inventé

**Aucun de ces éléments n'est devinable. Ils doivent être fournis par
l'établissement, par écrit, avec un validateur nommé.**

| # | Manque | Pourquoi l'application ne peut pas le supposer | Effet tant que c'est manquant |
|---|---|---|---|
| 1 | **Protocoles de prophylaxie réels** (texte, périmètre, périodicités) | Contenu médical propre à l'établissement. La spec LAB 04 les cite comme source autorisée, mais ils ne sont pas dans le dépôt. | Le référentiel démarre **vide**. Le module fonctionne, il n'affiche rien. |
| 2 | **Calendrier vaccinal officiel de l'établissement** (produit, doses, délais entre doses) | Un calendrier générique serait une donnée médicale inventée, et potentiellement périmée. | `CalendrierVaccinal` vide ⇒ **aucun rappel vaccin calculé**. Seuls les historiques saisis sont visibles. |
| 3 | **Fourchettes de référence réelles, par laboratoire et par population** | Le `docs/specification.md` §8 dit explicitement que les valeurs actuelles sont des « repères usuels » et doivent être validées par un biologiste. | Les valeurs actuelles restent des **repères de démonstration**, clairement étiquetés comme tels, et l'interface affiche « référence non validée » quand `valide_par` est vide. |
| 4 | **Liste des laboratoires réellement utilisés** + correspondance compte rendu ↔ laboratoire | Le seul `laboratoire="Laboratoire Biolys"` vient de la démo. | `Bilan.laboratoire` = NULL, et l'écran affiche « laboratoire non renseigné ». |
| 5 | **Signification de « RockZero »** (§0) | Ambiguïté de vocabulaire. | Le filtre « bilans RockZero » n'est pas implémenté. |
| 6 | **Correspondance des paramètres entre laboratoires** | « Hémoglobine » n'est pas le même code partout ; un alias non>mappé fait tomber la valeur en `inconnu` (règle 3.1-3), ce qui est **sûr mais bruyant**. | Un rapport listant les valeurs `inconnu` sert de backlog de mapping. |
| 7 | **Population concernée par les protocoles** (l'infirmerie vaccine-t-elle ? pour qui ?) | La spec §8 pose la question et la laisse ouverte. | Aucun protocole activé. |
| 8 | **Règles de priorité entre plusieurs protocoles** | Décision d'organisation. | Un patient couvert par deux protocoles → les deux échéances sont listées, sans arbitrage. |

Le module doit être concevable et livrable **avec ce tableau vide**. Un
« mode dégradé propre » fait partie de la spécification : le module affiche ce
qu'il sait, et signale le reste comme *à renseigner* — jamais de valeur par
défaut.

---

## 5. Implémentation par étapes

### Étape 1 — Référentiel laboratoire + fourchettes (le plus important)

`Laboratoire`, `ReferenceIntervalle`, migration `0004`, écran admin avec
`validé par` / date de validation, commande `verifier_references` qui liste
les `Bilan` dont le paramètre n'a **aucune** intervalle rattachée.
*Critère de fin* : plus aucune interprétation ne repose sur une valeur codée
en dur. Les repères de `seed_demo` sont **supprimés** de `Bilan`/`Mesure` et
remplacés par un `Laboratoire` « Démo — non validé » explicitement signalé.

### Étape 2 — Traçabilité de l'interprétation

`reference_intervalle`, `anomalite_figee`, `QualificationTexte`,
fonction de résolution d'intervalle **isolée et testée** (une fonction pure,
cas de test pour chaque branche de §3.1), durcissement de `anormalite`.
*Critère de fin* : un résultat sans référence est `inconnu`, jamais `normal`.

### Étape 3 — Vaccins

`Vaccin`, `InjectionVaccine` (formulaire, rattaché à la consultation),
`StatutVaccin`, historiquevaccinal, page patient. `CalendrierVaccinal`
**vide et administrable**, sans données pré-remplies. Extension de
`relances.py` : nouveau motif « rappel vaccin » si et seulement si un
`CalendrierVaccinal` validé existe — sinon le module n'en propose aucun.
*Critère de fin* : les rappels Villas ne peuvent être produits que depuis des
données validées, et le test « aucun envoi automatique » de `test_relances.py`
reste vert.

### Étape 4 — Protocoles

`Protocole`, `ProtocolePatient`, `ProtocoleEtape`, référentiel en lecture
seule pour les soignants, activation par un utilisateur habilité,
génération des `Suivi`.
*Critère de fin* : référentiel vide = application fonctionnelle mais muette.

### Étape 5 — Intégration

Lignes de `briefing.py` (rappel vaccin, protocole à échéance) au même niveau
d'exigence factuelle que l'existant — un test échoue si « probablement »,
« semble » ou « évoque » apparaissent. `verifier_pages` étendu aux nouveaux
écrans. Documentation : le tableau §4 comme **liste de points ouverts** dans
`docs/specification.md`.

### Ordre volontairement retenu

1. **Fourchettes paramétrables d'abord** — c'est le risque de sécurité
   clinique identifié ; les autres étapes ne font qu'ajouter des données
   à interpréter avec elles.
2. Le module reste **silencieux plutôt qu'inventif** à chaque étape.

---

## 6. Vérification attendue

```bash
./.venv/Scripts/python.exe manage.py check
./.venv/Scripts/python.exe manage.py test dossier
./.venv/Scripts/python.exe manage.py verifier_pages
```

Trois tests à écrire dès l'étape 2, qui figent la règle d'or :

1. Une `Mesure` numérique **sans intervalle applicable** → `inconnu`.
2. Une `Mesure` qualitative → `inconnu`, et **aucune** ligne de briefing.
3. Une valeur hors bornes sur un intervalle **d'un autre laboratoire** →
   l'interprétation n'emprunte pas la fourchette d'ailleurs.
