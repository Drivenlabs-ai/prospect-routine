---
name: edit-campaign
description: Déclencher quand l'utilisateur veut modifier une campagne de prospection existante — son ciblage (« affine le ciblage de X », « vise plutôt les Y », « exclus les Z », « resserre l'ICP », « change les filtres », « le ciblage est trop large ») ou sa séquence (« modifie la séquence », « reformule l'icebreaker », « ajoute une relance », « espace les relances », « passe l'étape 2 en LinkedIn », « change l'objet du 1er mail »). Couvre les filtres People DB, le prompt icpFit, et les étapes / timing / canaux de la séquence. Ne pas déclencher pour créer une campagne (→ new-campaign) ni pour le run quotidien (→ prospect-routine) ; modifier la config / l'état ou dupliquer une verticale n'est pas encore couvert.
---

# edit-campaign — modifier une campagne existante

## Vue d'ensemble

Modifie une campagne existante sur deux facettes : **le ciblage** (qui on contacte) et **la séquence** (ce
qu'on dit, dans quel ordre, à quel rythme, sur quel canal). L'utilisateur exprime son intention en langage
naturel ; toi (Claude de session) tu portes la complexité — tu traduis, tu valides, tu n'écris qu'après son
accord. Il ne voit jamais un `filterId`, un `stepId` ni un objet JSON.

Frontière à garder en tête : **le ciblage est 100% local** (filtres + icpFit, lus par le moteur au run,
Lemlist n'est pas touché) ; **la séquence vit dans Lemlist** et l'éditer la mute par API, sous garde
(campagne en pause, accord explicite).

**Commandes moteur** : via `uv run python scripts/routine.py <cmd>` (jamais `python3`).

## Modifier le ciblage

Affine qui une campagne cible. Deux leviers, tous deux locaux :

| Levier | Rôle | Où |
|---|---|---|
| Filtres People DB | ciblage dur : qui entre dans le funnel | `campaign.json` → `filters` |
| Prompt icpFit | ciblage mou : qui passe le jugement IA parmi les sourcés | `prompts/icpFit.md` |

### Flux

```
1. resolve     resolve --registry <Prospection/campaigns-registry.json> --slug <ce que dit l'utilisateur>
                → campaign_id + config_path. Slug introuvable → demander lequel (le registre les liste).
2. lire        l'état actuel : filters (campaign.json) + prompts/icpFit.md + fichiers d'intelligence
                (icp.md, persona.md, triggers.md) pour le contexte. Vérifier edit_in_progress (status) :
                si true, une édition est restée inachevée — le signaler et repartir proprement.
3. comprendre  reformuler l'intention jusqu'à être sûr de ce qui change dans le ciblage.
4. traduire    nouveaux filtres People DB (craft /lemlist §3 ; valider filterId/valeurs via
                get-database-filters) et/ou icpFit ajusté. Ne rien écrire encore.
5. valider     status --config <config_path> --set edit_in_progress=true
                source --config <config_path> --target <N> → taille du nouveau pool (total) + échantillon
                  total 0 ou exhausted → filtre trop étroit ou invalide : corriger, ne pas committer.
                workflow icp-check : args = { prompt_icpFit: <icpFit ajusté>, sample: <candidats>,
                  model: "haiku" } → lire les verdicts, comparer à l'ICP visé, itérer. Boucle bornée, accord humain.
                abandon à ce stade → status --config <config_path> --set edit_in_progress=false (rien n'a été écrit)
6. committer   après accord explicite : écrire les nouveaux filters (campaign.json) + le nouvel icpFit.md.
                filtres changés → cursor --config <config_path> --reset (cf. Règle du curseur pour le pourquoi)
                icpFit seul modifié → pas de reset (le pool est inchangé)
                status --config <config_path> --set edit_in_progress=false
7. confirmer   résumer : ancien → nouveau ciblage, nouvelle taille de pool, état du curseur.
```

### Règle du curseur

Changer les filtres change le pool : le `page_cursor` (position dans l'ancien ordre) devient caduc. Le
remettre à 1 (`cursor --config <config_path> --reset`) pour re-balayer le nouveau pool depuis le début.
Coût : re-score one-shot des survivants ; jamais de double-contact (le filtre `out` « déjà en campagne »
et les receipts couvrent). Changer l'icpFit seul ne touche pas le pool — pas de reset.

### Garanties (ciblage)

- Ciblage = 100% local : zéro mutation Lemlist, zéro launch, zéro contact.
- Validation avant écriture : la taille de pool et icp-check sur échantillon frais précèdent tout commit.
  L'alléger pour un ajustement trivial est un choix explicite, jamais un saut silencieux.
- `filters` et `icpFit.md` ne sont écrits qu'après validation et accord.
- `edit_in_progress` (status.json) marque une édition en cours — `true` pendant, `false` au commit ou à
  l'abandon ; il porte la reprise si une édition est interrompue.

## Modifier la séquence

Édite ce que dit/fait la séquence : contenu d'un message, structure (ajout / retrait / réordonnancement
d'étapes), timing (délais + fenêtres d'envoi), canal d'une étape. Lemlist reste la source de vérité : on
lit la séquence live, on la mute par API, on ne stocke jamais la séquence en local.

Gate dur : la campagne ne doit pas tourner. Le moteur refuse toute mutation si `status == running` —
mets la campagne en pause d'abord (geste séparé). Éditer une séquence en cours d'envoi a un effet non
documenté sur les leads déjà engagés.

Éditer une étape et synchroniser les prompts d'agents locaux est indissociable : une étape ajoutée ou un
message qui introduit un nouveau `{{var}}` exige un prompt `prompts/<var>.md`, sinon la variable sort vide
et le lead ne part pas. `verify` garde la couverture en fin de flux.

Flux détaillé (gate, preview à deux faces, contrat de variables, recreate de canal, résolution du
schedule) : `references/edit-campaign/sequence-edit.md` — le charger avant d'agir.

## Périmètre

Couvert : le ciblage (filtres People DB + prompt icpFit) et la séquence (contenu, structure, timing,
canal). Pas encore couvert :
- la config et l'état (pause/reprise, réglages campagne, cadence de sourcing, modèles) ;
- dupliquer une verticale vers un nouveau segment puis ajuster.

## Référence

- Ciblage — craft ICP → filtres People DB : `/lemlist` §3 (filterId / in / out, get-database-filters).
- Séquence — flux détaillé : `references/edit-campaign/sequence-edit.md` ; craft copy / séquence : `/lemlist`.
- Contrat icp-check : `args = {prompt_icpFit, sample, model:"haiku"}` → `{verdicts:[{lead, qualifie, raison}]}`.
- Commandes moteur — ciblage : `resolve`, `source` (renvoie `total`), `status --set edit_in_progress`,
  `cursor --reset`. Séquence : `sequence`, `add-step`, `update-step`, `delete-step`, `edit-schedule`, `verify`.
