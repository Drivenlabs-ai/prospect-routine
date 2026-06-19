---
spec: 04 — icp-check (passe d'alignement icpFit au setup)
statut: workflow livré et testé (TDD) — 2026-06-19 ; généré depuis workflows/lib/icp-check-core.js, gardé par tests/js/icp-check-workflow-sync.test.js
date: 2026-06-18
dépend de: docs/specs/01-routine-engine.md, docs/specs/03-sourcing.md
---

# Spec 04 — `icp-check` : aligner le jugement Haiku au setup

Avant qu'une verticale parte en prod, on **vérifie que le prompt `icpFit` (qui tourne sur Haiku dans le
run W3) juge comme on veut**. Pas de gate statistique, pas de dataset labellisé : un **mini-workflow de
test** fait juger un échantillon de prospects par Haiku et rend les verdicts bruts ; **Claude de la
session** (l'agent qui tient l'intention ICP au setup) les relit, repère les ratés, ajuste le prompt et
relance, jusqu'à alignement. La validation finale est humaine.

C'est une **passe d'itération au setup**, pas une brique de prod. Elle remplace l'idée de « graders »
lourde (holdout, métriques) écartée comme sur-ingénierie à cette échelle.

## 0. La frontière déterministe ↔ agentique

- **Le script du workflow** = orchestration pure : fan-out du scoring sur l'échantillon, agrégation des
  verdicts. Zéro outil, zéro I/O.
- **Les sous-agents** = l'intelligence : le **même** prompt `icpFit` qu'en prod, sur **Haiku**, sortie
  structurée `{qualifie, raison}`. C'est ce qu'on teste.
- **Le jugement d'alignement** = **Claude de la session** (hors workflow), qui tient l'intention ICP
  issue du setup, compare les verdicts à cette intention, et pilote l'itération du prompt. Pas d'agent
  juge dans le workflow.
- **L'I/O déterministe** (constituer l'échantillon, charger le prompt) = le moteur/routeur **autour** du
  workflow, qui passe l'échantillon + le prompt en `args` — exactement comme W3 passe `candidats`.

## 1. Le flux (boucle de setup, pilotée par Claude de session)

```
SETUP (Claude de session tient l'intention ICP)
  prompt icpFit + échantillon (~15 prospects sourcés)
       ↓ args = { prompt_icpFit, sample:[leads], model }
  WORKFLOW icp-check.workflow.js
       run   pipeline · 1 sous-agent icpFit / prospect (Haiku, parité prod) → {qualifie, raison}
       ↓ rend { verdicts:[{lead, qualifie, raison}] }
  Claude de session : compare les verdicts à l'intention ICP
       ├─ désalignés → ajuste le prompt icpFit (fichier local) → relance le workflow
       └─ alignés    → sign-off humain → le prompt part en prod (W1 flip dry_run plus tard)
```

Aucune boucle automatique dans le workflow : il rend des verdicts, point. L'itération (relire, ajuster,
relancer) est conduite par Claude de session, bornée par le jugement humain — pas de coût qui s'emballe.

## 2. Le mini-workflow (`workflows/icp-check.workflow.js`)

```js
export const meta = { name:"icp-check", description, phases:["run"] }

// args = { prompt_icpFit, sample:[lead…], model }
return await runCheck({ agent, pipeline, args })   // orchestration testée dans la lib
```

Côté lib (`icp-check-core.js`, testée), l'orchestration est `runCheck(env)` — un seul étage :

```js
async function runCheck(env) {
  const { agent, pipeline, args } = env
  const verdicts = await pipeline(args.sample,
    lead => agent(buildScorePrompt(args.prompt_icpFit, lead),
                  { schema: VERDICT_SCHEMA, model: args.model || "haiku", phase:"run" })
              .then(v => pairVerdict(lead, v)))   // raccroche le prospect à son verdict (calcul pur)
  return { verdicts }
}
```

**Contrat args / return**

```jsonc
args = {
  "prompt_icpFit": "…le prompt à tester (template interpolable)…",
  "sample": [ { "linkedinUrl","fullName","jobTitle","companyName","location","summary","headline" } ],
  "model": "haiku"        // optionnel, défaut "haiku" (parité prod)
}
// rend :
{ "verdicts": [ { "lead": {…}, "qualifie": true, "raison": "…" } ] }
```

L'échantillon est fourni par le routeur/moteur (sourcing People DB existant, spec 03 `source`) — le
workflow ne source rien.

## 3. Parité & pattern de build (réutilise W3)

Le test n'a de sens que si l'échantillon est jugé **exactement** comme en prod : **même
`buildScorePrompt`, même `VERDICT_SCHEMA`, même Haiku** que `workflows/lib/sourcing-core.js`. La parité
est **verrouillée par un test de parité** (sortie identique sur le même prospect, schéma `deepEqual`).
Le mécanisme exact (copie verrouillée par le test, ou extraction d'un `score-core` partagé inliné par
les deux générateurs) est tranché au plan — l'invariant est : *zéro divergence avec le scoring de prod*.

Même pattern que spec 03 : logique dans `workflows/lib/icp-check-core.js` (pur, testé `node --test`) →
`icp-check.workflow.js` **généré** self-contained (runtime sandboxé : pas de `require`/`import`) → garde
de synchro `committed === généré`.

## 4. Modèle

`run = Haiku` — **parité stricte avec la prod**. Le `model` est surchargeable par `args` mais le défaut
et l'usage normal, c'est Haiku (tester un autre modèle que celui qui tournera fausse l'alignement).

## 5. Tests (`node --test`)

- Parité : `buildScorePrompt` d'`icp-check` == celui de `sourcing-core` (même sortie, même lead) ;
  `VERDICT_SCHEMA` `deepEqual`.
- Pur : `pairVerdict(lead, {qualifie, raison})` → `{lead, qualifie, raison}` (raccroche bien le prospect,
  tolère un verdict nul/incomplet).
- Workflow : run mocké de `runCheck` (agent injecté rendant des verdicts canon) → vérifie la forme
  `{verdicts:[{lead,qualifie,raison}]}` et l'ordre/complétude sur l'échantillon. Le runner LLM n'est pas
  unit-testé.
- Synchro : `committed === buildWorkflowSource()` (workflow généré).

## 6. Hors-scope

- **GATE 2** (validation des prompts de **messages**) et tout grader statistique (holdout, métriques,
  IC) — écartés. La rubrique messages tourne déjà par-run dans W3 (spec 03).
- **W1** (création interactive) qui appellera cette passe au setup, et le **routeur** qui constitue
  l'échantillon et invoque le workflow.
- Le **sourcing de l'échantillon** (réutilise `source`, spec 03) et la **signature humaine** de
  l'alignement (acte manuel au setup).
