# Spécification fonctionnelle — Application Infirmerie

Version 1.0 · document de référence pour le cadrage fonctionnel.

Décrit **ce que l'application doit faire**, indépendamment de la technique.
L'installation et l'usage sont dans le `README.md`.

---

## 1. Origine du besoin

Deux problèmes constatés à l'infirmerie :

1. **Le suivi des dossiers patients** — l'information d'un patient est
   dispersée : papier, fichiers, souvenirs, relevés de laboratoire conservés
   à part.
2. **Le bilan de santé** — quand on cherche un résultat, on ne sait pas
   s'il date de trois semaines ou de trois ans.

C'est le même problème vu de deux angles : **l'information existe mais on ne
sait plus à quel moment elle vaut.**

## 2. Périmètre

### Dans le périmètre (version 1)

- Fiche patient : identité, coordonnées, allergies, médecin traitant
- Historique des consultations
- Bilan de santé daté, avec interprétation des valeurs
- Suivi des tâches à relancer
- Synthèse imprimable pour transmission à un tiers

### Hors périmètre (version 1)

- Agenda des rendez-vous
- Stocks de médicaments et posologie automatique
- Interopérabilité avec un logiciel métier existant
- Télétransmission vers un laboratoire

Ces sujets sont identifiables mais chacun représente un chantier à part
entière. Les traiter maintenant élargirait la surface sans lever la
difficulté centrale.

## 3. Utilisateurs

| Profil | Rôle | Périmètre |
|---|---|---|
| Secrétariat | Accueil, administratif | Crée et retrouve les dossiers. **N'accède pas** aux données cliniques. |
| Soignant | Personnel soignant | Accès complet : consultations, bilans, prescription, constantes. |
| Administrateur | Gestion | Accès complet + administration technique. |

### Décision : le secrétariat n'accède pas aux données cliniques

Le secrétariat gère l'administratif mais n'a pas à connaître les résultats
biologiques ni les constantes du patient. Ce n'est pas une précaution
d'interface : **le contrôle est appliqué côté serveur**. Un utilisateur
secretariat qui saisit directement l'URL d'un dossier clinique reçoit une
erreur — il n'obtient rien.

Conséquence : la liste des patients reste visible depuis l'accueil
(le secrétariat doit pouvoir identifier une personne), mais le contenu
clinique ne l'est pas.

## 4. Fonctions

### 4.1 Fiche patient

| Champ | Obligatoire | Remarque |
|---|---|---|
| Nom, prénom | oui | Recherche insensible à la casse et aux accents |
| Date de naissance | oui | Une date future est refusée |
| Sexe | oui | Féminin, Masculin, Autre |
| Téléphone, email, adresse | non | |
| N° de dossier | auto | Attribué si laissé vide, format `INF-0001` |
| Médecin traitant | non | |
| Allergies | non | Substance, réaction observée, gravité |
| Suivis | non | Description + échéance |

**Pourquoi la gravité d'une allergie est structurée** et non en texte libre :
une allergie sévère doit s'afficher différemment d'une allergie légère. Un
champ libre ne permet pas de trier ni d'alerter.

**Pourquoi l'âge est calculé** et non saisi : un âge stocké devient faux.

### 4.2 Consultation

Rattachée à un patient, datée. Contenu : date, motif, diagnostic,
observations, prescription, et les constantes (tension, pouls, température,
SpO₂, poids, taille).

L'IMC est calculé à partir du poids et de la taille, pas saisi.

**Contrôle de plausibilité** : une taille hors de 50–250 cm ou un poids hors
de 1–400 kg sont refusés par le formulaire, avec un message. On laisse
passer une erreur de frappe de « 1800 » pour un poids de 18 kg, un IMC
calculé dessus n'aurait aucun sens et se retrouverait dans le dossier.

**Statut** : ouverte ou clôturée. Permet de distinguer une consultation en
cours d'un compte rendu terminé.

### 4.3 Bilan de santé

Rattaché à une consultation, donc daté et rattaché à son contexte.

C'est le point de conception central : **le bilan n'est pas attaché au
patient, mais à la consultation**. On peut ainsi répondre à « quel était son
bilan en mars ? », ce qui est la question réellement posée lors d'un suivi.

Chaque mesure comporte : paramètre, valeur, unité, norme basse, norme haute,
référence.

**Interprétation automatique** — chaque valeur est classée contre ses normes :

- dans les normes → affichée neutre
- au-dessus / en dessous → signalée, avec la valeur mise en évidence
- **valeur non chiffrée** (mention « négatif », « traces ») → marquée
  *à qualifier*, jamais classée à tort comme normale

Ce dernier point est une décision de conception : une mention qualitative
n'est pas une valeur. La classer « normale » par défaut serait un risque —
une négativité se lirait comme un résultat rassurant.

Les fourchettes dépendent du dosage, du sexe et parfois de l'âge : elles
sont donc portées par la mesure, pas par un réglage global.

### 4.4 Alertes

- **Allergies** : bandeau en tête de chaque fiche, et à la création d'une
  consultation, au moment de prescrire
- **Valeurs hors norme** : remontées sur l'accueil
- **Bilans périmés** : un bilan de plus de douze mois est signalé comme à
  renouveler
- **Suivis en retard** : une tâche échue et non faite apparaît à l'accueil

### 4.5 Suivis

Tâche avec description et échéance. Trois états : à faire, en retard, fait.

### 4.6 Synthèse imprimable

Document destiné à un tiers (spécialiste, médecin traitant). Contenu :
bandeau d'allergies, dernières consultations, bilans annotés avec
l'interprétation.

**Pourquoi ce document** : c'est le format de sortie du système. Sans lui, la
synthèse se refait à la main, et l'application ne sert qu'à l'intérieur.

## 5. Exigences non fonctionnelles

| Exigence | Choix retenu | Pourquoi |
|---|---|---|
| Installation | Locale, sans serveur externe | Les données de santé ne quittent pas l'infirmerie |
| Accès distant | VPN | Voir section 6 |
| Hors connexion | Aucun accès si le réseau tombe | Un dossier inaccessible vaut mieux qu'un dossier non chiffré exposé |
| Rôles | Contrôle serveur | Un accès ne dépend pas d'un élément d'écran |
| Comptes sans rôle | Aucun accès | Le défaut est le refus, pas l'autorisation |
| Sauvegarde | Automatique, 30 générations conservées | Restaurable par une personne non technique |
| Session | Expire en fin de journée | Poste d'infirmerie partagé |
| Langue | Français | |

## 6. Sécurité et confidentialité

**Données de santé.** Le dossier d'une infirmerie relève du secret médical.
Trois mesures retenues :

1. **Pas d'exposition réseau.** L'application n'écoute que sur la machine
   locale. L'accès distant passe par un VPN : on se connecte au réseau de
   l'infirmerie par tunnel chiffré. Aucune IP publique n'est mise en
   correspondance avec l'application.
2. **Contrôle des accès côté serveur**, testé par des cas dédiés.
3. **Sauvegardes chiffrées à la source** : elles ne quittent pas l'infirmerie.

**À faire valider avant mise en service** : le protocole exact, la durée de
conservation, et le traitement des données après départ d'un patient. Ces
points engagent l'établissement, pas seulement l'outil.

## 7. Traçabilité

Toute modification porte un horodatage. Les consultations sont attribuées au
compte qui les a saisies.

## 8. Points ouverts

À trancher avec l'établissement :

- **Fourchettes de référence** — les valeurs actuelles sont des repères
  usuels. Elles doivent être alignées sur les normes du laboratoire utilisé,
  ideally validées par un biologiste.
- **Soins dispenser** — l'infirmerie a-t-elle des Duties d'injection, de
  vaccination, de plaie ? Cela ouvrirait sur un module pansements, avec ses
  propres dates de contrôle. Non traité en version 1.
- **Mainlevée de secret** — qui, et selon quelles conditions ? La version 1
  ne le couvre pas.
- **Nomenclature** — faut-il reprendre le vocabulaire du logiciel actuel ?

## 9. Critères de recette

La version 1 est validée si :

1. Un patient peut être créé, retrouvé, et son dossier rouvert
2. Une consultation est saisie avec ses constantes, et l'IMC calculé
3. Un bilan est saisi, et une valeur hors norme est signalée
4. Une mention non chiffrée n'est pas classée comme normale
5. Un compte secrétariat obtient un refus sur une URL de dossier clinique
6. Une synthèse imprimable contient le bandeau d'allergies et les bilans
7. Une sauvegarde est prise puis restaurée, et les données sont intactes
8. Les vingt et un tests automatisés passent
