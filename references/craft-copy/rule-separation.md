# Séparation des règles par nature (référence craft-copy)

Chargée avant d'écrire ou modifier une fiche de prompt de copy. Détermine **où** chaque règle vit, pour qu'une règle n'existe qu'à un seul endroit — sinon deux copies divergent à la première édition et la fiche se contredit.

## Deux axes indépendants

Une règle a une **portée** (pour qui elle est vraie) et une **application** (qui la fait respecter). La portée décide où la règle vit ; l'application décide qui la vérifie. Ne pas confondre les deux.

```
PORTÉE                                          APPLICATION
Universelle → vraie pour toute campagne         Garde déterministe → code, blocage dur
Transverse  → vraie pour toute la campagne        (vide, tiret cadratin, markdown, séparateur)
              (le ton, la voix)                  Juge → rejette + fait régénérer
Spécifique  → propre au rôle d'une étape         Rédacteur → simple consigne (doctrine + fiche)
```

## Où vit chaque règle

Une fiche de prompt d'étape ne porte **que** sa matière propre. Pour chaque règle candidate, appliquer dans l'ordre :

1. **Universelle** (vraie pour toute campagne — vouvoiement, pas d'emoji, pas de tiret cadratin, pas de markdown, pas d'invention, pas de jargon/cliché, pas d'ouverture par une question ou par « je », une idée par message, ≤ 1 point d'exclamation… ; liste indicative, la doctrine du moteur fait foi) → elle vit dans le **moteur** (doctrine d'écriture + rubrique du juge + garde déterministe). **Ne jamais la recopier dans une fiche.** Manquante et souhaitable → c'est une évolution du moteur, pas un ajout dans une fiche.
2. **Transverse à la campagne** (le ton, le registre, la voix de marque) → elle vit dans le **fichier voix** de la campagne, déjà injecté avant chaque étape. Ne jamais la répéter dans chaque fiche. Une instruction de ton qui vaut pour tous les messages → signaler que c'est la voix, router vers ce fichier, ne pas la baker dans une étape.
3. **Propre au rôle de l'étape** (l'intention du message, l'offre et l'angle, la palette de douleurs, la façon de s'adapter au prospect, la mise en forme visible, les exemples) → elle vit dans la **fiche d'étape**. C'est sa seule matière légitime.

## Raffinement d'un universel

Une fiche peut **préciser ou durcir** un universel (ex. « aucun chiffre du tout » là où le moteur interdit seulement les chiffres non étayés) — autorisé tant que ça ne **contredit pas** ce que le moteur enforce. Une consigne de fiche qui contredit un enforcement du moteur est un bug (la fiche promet ce que le moteur refuse) : corriger à la source, pas dans la fiche.

## Détecter et retirer un doublon

En éditant une fiche existante, repérer toute règle qui est en fait un universel (déjà dans le moteur) ou du ton transverse (déjà dans la voix) : la retirer. Le résultat doit lire comme si la fiche avait toujours été propre — pas de trace de la règle retirée. Le test avant/après (voir `test-loop.md`) prouve que retirer un doublon ne dégrade pas la copy : le moteur enforce toujours l'universel.
