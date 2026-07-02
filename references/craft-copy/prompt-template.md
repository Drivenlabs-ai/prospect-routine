# Template de fiche de prompt de copy (référence craft-copy)

Chargée avant d'écrire une fiche. La fiche est concaténée telle quelle après la doctrine du moteur et le bloc du prospect, puis lue par l'agent d'écriture. Elle est en **XML** : les balises délimitent la fiche et ses sections sans ambiguïté dans un prompt assemblé de plusieurs morceaux.

## Structure canonique

```xml
<role>Qui écrit, à qui, sur quel registre (calibré sur le persona).</role>

<intention>Le job unique de CE message dans la séquence, et le principe non négociable de son rôle
(icebreaker : ouvre sur une douleur puis la solution ; relance : rend concret sans répéter la douleur ;
clôture : dernier message, offre la plus tangible).</intention>

<donnees_lead>
Les tokens Lemlist à ÉMETTRE tels quels dans le message (ex. {{firstName}}), et les signaux du prospect
à LIRE pour s'adapter (poste, headline, résumé…) avec le repli si un signal est vide. Ne jamais inventer
un détail absent.
</donnees_lead>

<offre>L'offre réelle et l'angle : ce que la solution fait, la palette de douleurs sur lesquelles taper
(liste ouverte : « ou toute autre douleur métier pertinente »). C'est l'ancre : l'agent ne propose que ce
qui est décrit ici.</offre>

<adaptation>Comment coller à ce prospect (taille, zone, spécialité) à partir de ses signaux, sans inventer
aucun fait.</adaptation>

<mise_en_forme>La forme visible du message, dont la longueur visée — la fiche est le seul endroit qui la
fixe, le moteur n'impose aucun plafond. Blocs courts séparés par une ligne vide, salutation seule sur sa
ligne, appel final seul sur sa ligne. Pas de pavé d'un bloc.</mise_en_forme>

<exemples>
<exemple>Un message complet, exactement au format voulu, sur un angle donné.</exemple>
<exemple>Un deuxième, sur un angle différent (la diversité évite que l'agent capte un tic commun).</exemple>
<exemple>Un troisième, encore un autre angle.</exemple>
</exemples>

<sortie>Le champ « message » contient uniquement le message à envoyer, sauts de ligne compris : aucun titre,
préambule, commentaire ni répétition.</sortie>
```

## Les deux natures de token

- **Token Lemlist à émettre** (ex. `{{firstName}}`) : il part littéralement dans le message et Lemlist le substitue à l'envoi. La fiche l'écrit là où il doit apparaître (« Bonjour {{firstName}}, »).
- **Signal du prospect à lire** (poste, headline, résumé, ville…) : l'agent le lit dans le bloc du prospect que le moteur ajoute, et s'en sert pour adapter. La fiche ne l'écrit pas comme un token à émettre.

## Ce qui est délibérément absent, et pourquoi

- **Pas de liste d'interdits qui redit la doctrine** (vouvoiement, pas d'emoji, pas de tiret, pas de jargon…) : le moteur les porte déjà (voir `rule-separation.md`). Les redire dans la fiche crée un doublon qui divergera.
- **Pas de critères de succès** : ce sont ceux du juge du moteur. Les mettre dans la fiche pousse l'agent à s'auto-noter au lieu d'écrire.
- **Pas d'étapes de raisonnement** : la copy est une tâche créative ; un raisonnement pas-à-pas fuit dans la sortie et sur-contraint. Énoncer l'intention et les contraintes, pas la procédure.

Une frontière à laquelle l'utilisateur tient s'écrit en **une contrainte courte portant sa raison**, dans la section concernée — jamais en contre-exemple. Un contre-exemple dans une fiche enseigne le pattern qu'il montre : ne jamais en mettre. Les exemples de `<exemples>` sont **positifs** et sont exactement la sortie voulue.

## Exemple de section (noms fictifs)

```xml
<exemples>
<exemple>Bonjour {{firstName}},

Retrouver les bons interlocuteurs vous prend des heures, pour beaucoup de pistes qui ne donnent rien.

Acme s'en charge : il remonte le bon contact et prépare la piste, vos équipes n'ont plus qu'à décrocher.

Ça vaudrait le coup d'en parler ?</exemple>
</exemples>
```
