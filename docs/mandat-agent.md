# Mandat de l'agent — ce qu'il a le droit de décider

Document à signer avant toute activation en mode `--appliquer`.
Tant qu'il n'est pas signé, l'agent tourne en simulation et n'agit pas.

---

## 1. Les parties

**Le responsable de l'infirmerie** délègue à l'agent les décisions listées
ci-dessous, dans les limites fixées.

**L'agent** est un programme du logiciel. Il n'utilise aucune intelligence
artificielle : il applique des règles écrites, choisit parmi un catalogue
fermé, et trace chaque décision.

## 2. Ce qui est délégué

### Classe A — administratif, sans effet sur le patient

| Action | Effet | Réversible |
|---|---|---|
| Préparer une relance pour un suivi en retard | Crée un brouillon, en attente de validation | Oui |
| Préparer une relance pour un bilan de plus de douze mois | Crée un brouillon, en attente de validation | Oui |

### Classe B — clinique, réversible, tracé

| Action | Effet | Réversible |
|---|---|---|
| Programmer un contrôle après une valeur hors bornes | Crée un suivi à échéance | Oui, tant qu'il n'est pas fait |

**Délais proposés** — à confirmer ou corriger par le praticien, ils engagent
sa responsabilité :

| Paramètre | Délai de contrôle |
|---|---|
| Ferritine, hémoglobine | 21 jours |
| TSH | 42 jours |
| Glycémie, HbA1c | 90 jours |
| Tout autre paramètre | 90 jours |

Une seule décision par patient et par bilan, même si plusieurs valeurs sont
hors bornes : l'agent ne choisit pas laquelle compte.

## 3. Ce qui n'est jamais délégué

Ces actions **n'existent pas** dans le catalogue. Aucune option de ligne de
commande ne peut les activer :

- envoyer un message à un patient ;
- modifier ou supprimer une mesure, une consultation, un bilan ;
- valider une relance à la place d'un soignant ;
- purger un dossier ;
- créer, modifier ou désactiver un compte.

Toute tentative d'exécution d'une action hors catalogue lève une erreur. Un
test vérifie qu'aucune action de classe C ne peut y entrer.

## 4. Contrôle humain

- Une décision appliquée apparaît dans la page **Agent**, avec la règle, le
  motif et l'objet créé.
- Elle peut être **annulée** : le brouillon ou le suivi créé est retiré.
- L'annulation **échoue volontairement** si un soignant a déjà validé la
  relance ou marqué le suivi comme fait. À partir de là, la décision est
  humaine, l'agent n'a plus la main.

## 5. Journal

Chaque décision est enregistrée dans `DecisionAgent` : date, règle, action,
classe, patient, motif, mode, objet créé. Les décisions ne se suppriment
pas ; elles s'annulent, ce qui laisse la trace qu'elles ont existé.

Les actions effectivement exécutées sont aussi inscrites au journal d'accès
général, avec l'acteur « agent ».

## 6. Révocation

À tout moment, sans préavis :

```
python manage.py agent_decision            # retour à la simulation seule
```

Pour désactiver complètement : ne pas appeler `--appliquer`, et retirer la
tâche planifiée correspondante. Les décisions déjà prises restent visibles
et annulables.

## 7. Révision

**Tous les mois**, passer :

```
python manage.py agent_comparer --jours 30
```

Trois indicateurs :

- **taux d'accord humain** — s'il est bas, la règle est mal calibrée ;
- **décisions non suivies** — une règle que personne ne suit doit être
  retirée, sinon elle apprend à ignorer les alertes ;
- **décisions annulées** — si le taux monte, l'autonomie doit reculer.

## 8. Responsabilité

L'agent ne signe rien. Les décisions qu'il prend restent sous la
responsabilité du praticien qui a signé ce mandat. Le journal existe pour
permettre de reconstituer, après coup, ce qui a été décidé, par quelle
règle, et sur quelles données.

---

**Signé le** : ______________

**Par** : ______________________________

**Classes autorisées** : ☐ A seule ☐ A et B

**Révision prévue le** : ______________
