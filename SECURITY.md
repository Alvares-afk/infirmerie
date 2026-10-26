# Sécurité — ce que le code fait, et ce qu'il ne fait pas

Ce fichier existe parce qu'un analyseur automatique a signalé la ligne
`installer.py:57` (« l'IA peut lancer des commandes système »). Il faut
pouvoir répondre précisément, sans hausser les épaules et sans mentir.

## Le signalement

`installer.py` contient des appels `subprocess.run`. L'analyseur en déduit
qu'une intelligence artificielle pourrait lancer des commandes. C'est une
déduction, pas une observation.

Ce qui est vrai :

- l'installateur lance des commandes système ;
- il le fait pour créer un environnement Python, installer les dépendances
  et préparer la base — c'est sa fonction même.

Ce qui n'est pas vrai :

- **aucune IA n'intervient dans l'application.** Il n'y a ni modèle, ni
  appel réseau, ni génération de commande. Les commandes sont écrites dans
  le fichier, en clair ;
- **aucun texte extérieur ne devient une commande.** `commande` est
  toujours une liste construite à partir de constantes (`PYTHON`,
  `manage.py`, un sous-commande). Rien ne vient d'une page web, d'un
  fichier reçu ou d'une saisie libre ;
- **`shell=False` est explicite.** Aucun interpréteur n'est invoqué : il
  n'y a pas de shell où une chaîne pourrait être réinterprétée.

Ce qu'un analyseur ne peut pas voir : l'application n'ouvre **aucune**
connexion réseau. Un test le vérifie sur le module des relances. Le poste
ne peut donc ni recevoir d'ordre, ni laisser fuir un dossier.

## Ce qui a été durci à cette occasion

**Le mot de passe ne passe plus en argument de commande.** Un argument de
processus est lisible dans le gestionnaire de tâches par tout utilisateur de
la session ; une variable d'environnement n'est lisible que par le processus.
`renouveler_mots_de_passe` et `verifier_connexion` acceptent donc
`INFIRMERIE_MDP`, et l'installateur l'utilise. Trois tests le verrouillent.

**`shell=False` explicite** dans l'installateur, avec un commentaire qui dit
pourquoi : la prochaine personne qui touchera ce fichier saura que c'est
volontaire.

## Les en-têtes HTTP

`django.middleware.clickjacking.XFrameOptionsMiddleware` est actif, donc
`X-Frame-Options: DENY` : l'application ne peut pas être affichée dans un
cadre sur un autre site. Le signalement « page intégrable par n'importe quel
site » ne s'applique pas à cette configuration.

Il n'y a pas de politique de confidentialité parce qu'il n'y a **pas de
site public** : l'application tourne sur le poste du cabinet, en
`127.0.0.1`. Une politique de confidentialité ne protège rien sur un poste
que seul le personnel peut ouvrir ; ce qui protège, c'est le contrôle
d'accès et le journal.

## Les risques réels, assumés

| Risque | Réalité | Réponse |
|---|---|---|
| Mot de passe commun aux trois comptes | Choisi par l'utilisateur | Le journal distingue le compte, pas la personne. Rotation possible par `renouveler_mots_de_passe` |
| Pas de limitation des tentatives | Vrai | Le poste est local ; un attaquant doit déjà être devant l'écran. À traiter si l'accès distant est ouvert |
| Base SQLite non chiffrée | Vrai | BitLocker sur le poste ; mentionné dans la notice |
| Sauvegardes non chiffrées | Vrai | Elles contiennent les mêmes dossiers : même exigence de support |
| Règle pare-feu `public` | Le script existe dans le dépôt | Retiré du paquet client ; à corriger ou supprimer |

## Ce qui protège vraiment

- Rôles vérifiés **côté serveur** : le secrétariat ne peut pas ouvrir une
  page clinique, même en connaissant l'adresse.
- Journal d'accès en ajout seul : qui a lu quel dossier, quand, depuis
  quelle adresse.
- Purge impossible sans date explicite, sans `--confirmer`, et toujours
  tracée.
- Fourchettes de référence versionnées : un bilan ancien reste interprété
  avec les bornes de son époque.
- 149 tests, dont ceux qui vérifient qu'aucune relance ne part sans
  validation humaine.

## Signaler un problème

Les défauts de sécurité se signalent à l'éditeur du logiciel, pas sur un
forum public.
