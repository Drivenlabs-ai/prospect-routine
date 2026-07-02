# Dialogue de découverte (référence craft-copy, étape 1)

Chargée pour comprendre et clarifier le changement voulu avant d'écrire la fiche. But : extraire l'intention et le goût de l'utilisateur par du concret, jusqu'à ce que la direction soit claire.

## Le médium, ce sont des exemples

L'utilisateur juge mieux sur des messages que sur des abstractions. Le geste :

- Proposer, dans un message amont, des **messages candidats** concrets — plusieurs variantes qui font varier l'angle, l'ouverture, la douleur, le ton, l'appel — **et** des **contre-exemples argumentés** (une version + la raison précise pour laquelle elle rate).
- Puis, via **AskUserQuestion**, faire choisir ce qui résonne (une variante, un mélange, ou « autre chose »).
- Itérer sur le retour jusqu'à converger.

En améliorant une fiche existante, amorcer le dialogue sur la **copy réelle qu'elle produit aujourd'hui** (générée via le test, voir `test-loop.md`) : on discute d'un message réel, pas d'une idée.

Sortie du dialogue : une **présélection validée** — environ 3 exemples que l'utilisateur endosse. Ces 3 exemples deviennent les few-shots de la section `<exemples>` de la fiche. Les contre-exemples restent dans le dialogue : ils ont révélé la frontière du goût, leur leçon s'écrit en contrainte dans la fiche, ils ne sont jamais recopiés dedans.

## La structure d'un message, par rôle d'étape

Point de départ à faire réagir, pas gabarit figé — l'angle gagnant peut sortir de la liste (« ou toute autre approche pertinente »). La structure dépend du rôle :

- **Icebreaker** : saluer, ouvrir sur une douleur réelle et reconnaissable (personnalisée au prospect), montrer la solution avec son résultat, finir sur un appel court et basse pression.
- **Relance** : reprendre l'angle de l'icebreaker et le rendre concret (ce que le prospect verrait au quotidien), sans répéter la douleur ni réécrire le premier message.
- **Clôture** : dire que c'est le dernier message, offrir la chose la plus tangible (une démonstration sur son propre cas), laisser une porte de sortie digne.

Bonnes pratiques courantes, à **challenger** plutôt qu'appliquer :
- Remercier pour la connexion ne vaut que sur LinkedIn après acceptation, et frôle le cliché — l'éviter si ça sonne creux.
- Un résultat **chiffré** n'est admis que s'il est réel et vérifiable ; sinon, un résultat **qualitatif** est le défaut sûr (une promesse chiffrée inventée est refusée par le moteur).
- Ouvrir par une question ou par « je » est proscrit ; clore par une question courte est bon.

## Ce que l'utilisateur voit

L'utilisateur n'est pas ingénieur de prompt. Devant lui : des **messages** et des décisions de goût ou de direction. La mécanique reste en coulisses. Ne pas employer devant lui : « few-shot », « rubrique », « workflow », « prompt d'étape », « doctrine », « échantillon ». Parler de « la fiche du message », « des versions », « le test ».
