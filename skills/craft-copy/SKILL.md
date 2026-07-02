---
name: craft-copy
description: Déclencher quand l'utilisateur veut améliorer, affûter, réécrire ou créer la copy d'une campagne de prospection — le prompt qui génère un message (« réécris l'icebreaker », « le closing sonne faux », « la relance est trop générique / trop longue / pas assez directe », « change l'angle du 1er message », « rends le message plus percutant », « affûte la copy de la campagne X », « écris la copy d'une étape »). Couvre les prompts de copy (`prompts/<étape>.md` : icebreaker / relance / clôture / étapes custom), en création comme en amélioration. Ne pas déclencher pour créer une campagne de zéro (→ new-campaign), pour le ciblage / la structure de séquence / la config (→ edit-campaign), ni pour le prompt de qualification icpFit (→ edit-campaign).
---

# craft-copy — affûter les prompts de copy d'une campagne

## Vue d'ensemble

Améliore ou crée le prompt qui génère un message de prospection (`prompts/<étape>.md`). L'utilisateur exprime son intention en langage naturel ; toi (Claude de session) tu portes la complexité : tu clarifies avec lui, tu écris la fiche, tu la testes en conditions réelles avant de la garder. Il ne voit jamais un prompt brut ni du jargon de prompt-engineering — il juge des **messages**.

Deux étapes indissociables : comprendre & clarifier, puis tester en conditions réelles. Ne jamais écrire la fiche définitive sans avoir montré à l'utilisateur ce qu'elle produit, avant/après, et obtenu son aval.

**Commandes moteur** : via `uv run python scripts/routine.py <cmd>` (jamais `python3`).

## Étape 1 — Comprendre & clarifier

Résoudre la campagne : `resolve --registry <racine Prospection/campaigns-registry.json> --slug <ce que dit l'utilisateur>` → `campaign_id` + `config_path` (slug introuvable → demander lequel). Si l'appelant fournit déjà le `config_path` et les clés d'étape (campagne en cours de création par `new-campaign`, pas encore au registre), sauter `resolve` et travailler en mode création. Lire l'état actuel comme « déjà-possédé » : la fiche visée, la doctrine du moteur et le fichier voix de la campagne — pour ne pas dupliquer ce qu'ils portent déjà.

Puis clarifier le changement avec l'utilisateur, par le concret : proposer des messages candidats et des contre-exemples argumentés, le faire choisir, itérer jusqu'à une direction claire et une présélection d'exemples qu'il endosse. Méthode complète : `references/craft-copy/discovery-dialogue.md` — la charger avant d'agir.

Écrire (ou convertir) la fiche en **XML**, en n'y mettant que sa matière propre — chaque règle à un seul endroit. Où va chaque règle : `references/craft-copy/rule-separation.md`. Structure et balises de la fiche : `references/craft-copy/prompt-template.md`. Charger les deux avant d'écrire.

## Étape 2 — Tester en conditions réelles

Prouver que la nouvelle fiche produit ce qu'on attend, avant de la garder : rejouer le vrai agent d'écriture sur un échantillon frais de prospects, avec l'ancienne et la nouvelle fiche, et afficher les deux versions **côte à côte** pour que l'utilisateur compare et valide. La fiche définitive n'est écrite qu'après son aval, puis `verify` confirme la couverture. Flux détaillé (échantillon, assemblage des `args`, workflow `craft-copy-test`, affichage, garde d'écriture) : `references/craft-copy/test-loop.md` — la charger avant d'agir.

## Garanties

- **Copy uniquement.** Le skill n'écrit que des `prompts/<étape>.md` locaux — zéro mutation Lemlist.
- Le fichier voix n'est jamais écrit — c'est un actif de marque partagé au-delà de la prospection. Une instruction de ton transverse à toute la campagne → le signaler (« ça, c'est la voix ») et router, pas la figer dans une étape.
- Rien n'est gardé sans preuve. La fiche définitive n'est écrite qu'après le test avant/après et l'aval de l'utilisateur ; `verify` reste vert.
- Reformuler ou réécrire le **contenu** d'un message existant est du ressort de craft-copy — c'est la fiche qui génère ce contenu. Seul l'ajout, le retrait ou le réordonnancement d'une étape est un geste de structure → `edit-campaign`, qui renvoie ici pour le craft une fois la clé créée.

## Périmètre

Couvert : le craft des prompts de copy (icebreaker / relance / clôture / étapes custom), création et amélioration. Hors périmètre : créer une campagne (→ new-campaign) ; ciblage, structure de séquence, timing, canal, objet d'email (champ de séquence), config / état (→ edit-campaign) ; le prompt de qualification icpFit (→ edit-campaign).

## Référence

- Séparation des règles (où vit chaque règle) : `references/craft-copy/rule-separation.md`.
- Template de fiche (XML, balises, absences délibérées) : `references/craft-copy/prompt-template.md`.
- Dialogue de découverte (exemples / contre-exemples, bonnes pratiques par rôle, doctrine UX) : `references/craft-copy/discovery-dialogue.md`.
- Boucle de test (échantillon, workflow avant/après, validation) : `references/craft-copy/test-loop.md`.
- Contrat du workflow : `args = { sample, sequence_keys, prompts_before, prompts_after, model }` → `{ comparisons: [{ id, lead, before, after }] }`.
- Commandes moteur : `resolve`, `source --sample`, `verify`.
