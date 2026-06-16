---
spec: 02 — W2 lemlist-setup + contrat de variables
statut: à valider — dédup/duplicate vérifiés doc Lemlist 2026-06-15
date: 2026-06-15
dépend de: docs/specs/01-routine-engine.md
---

# Spec 02 — W2 lemlist-setup (création de campagne par duplication)

Matérialise une verticale dans Lemlist : une campagne + sa séquence multicanal + une liste audience,
puis l'enregistre. Construit sur le principe SSoT renforcé : **Lemlist est la seule source de vérité
de la structure de campagne. Le local n'en stocke rien et ne la synchronise jamais.**

## 0. Principe SSoT (renforcé)

- **La structure (séquence, étapes, canaux, délais, variables référencées) vit UNIQUEMENT dans Lemlist.**
  Aucun flow local, aucun champ `sequence` en local. Une modif faite dans Lemlist n'a rien à « répercuter »
  côté local — il n'y a pas de copie à tenir à jour.
- **Pas de sync gérée par Claude.** Le seul accord local↔Lemlist = un fichier prompt par variable de
  message. Et cet accord se **lit depuis Lemlist** (sens unique), il ne s'écrit jamais vers Lemlist.
- **Création par duplication d'un template Lemlist**, pas par construction locale. Le flow par défaut
  vit dans une campagne template Lemlist (maintenue en UI), qu'on duplique.

**Template par défaut** = la campagne **agence-immo** existante (séquence : visite profil → invitation
sans note → icebreaker → followup → closing, full LinkedIn ; les 3 messages portent `{{icebreaker}}`,
`{{followup}}`, `{{closing}}`). Son `campaign_id` = `template_id`, figé dans la config plugin / le registre.

## 1. Fait vérifié — `POST /campaigns/{id}/duplicate` (doc 2026-06-15)

*« Full copy including sequence steps, schedules, and AI variable templates. CRM settings not
duplicated. Created in draft state, lead counts reset to zero. »* Corps : `{name}`. Renvoie le nouveau
`campaign_id` (+ `sequenceId`). → la séquence et les références `{{variables}}` voyagent ; la campagne
naît vide et en draft. La liste audience n'est PAS dupliquée (CRM exclu) → on la crée à part.

## 2. W2 — procédure du routeur (pas un workflow `.workflow.js`)

W2 est **déterministe** (aucun sous-agent) → ce n'est pas un script de l'outil Workflow (réservé au fan-out d'agents, c.-à-d. W3). C'est une **procédure orchestrée par le routeur** : il enchaîne les commandes moteur ci-dessous avec un point de revue humain au smoke. Spec 2 livre donc les **capacités** (commandes moteur + gardes) ; le câblage vit dans le routeur (spec finale).

```
W2(verticale, template_id)   [idempotent, reprise via status.w2_steps]
  1. duplicate-campaign(template_id, name=verticale)   → campaign_id (+ sequenceId)
  2. create-list(name)                                  → list_id (audience non synchronisée)
  3. verify(campaign_id, prompts_dir)                   → conformance prompts ↔ variables séquence
  4. smoke : load-lead 1 lead (spec 1) + revue humaine
  5. register-campaign                                  → campaign.json (ids + chemins) + registre
```

Idempotence (garde-fou stress-test §11.3) : chaque étape franchie est inscrite dans `status.w2_steps[]` ;
au re-run, on saute ce qui est fait (check-exists pour la liste, w2_steps pour le reste) — jamais de
campagne dupliquée deux fois.

## 3. Le contrat de variables (cœur de robustesse)

Trois bouts doivent porter les **mêmes clés** : la séquence Lemlist référence `{{icebreaker/followup/closing}}`,
les prompts s'appellent `icebreaker.md / followup.md / closing.md`, le moteur pose des variables de lead
des mêmes clés. **Source unique des clés = la séquence Lemlist** (lue par `fetch`). Le local s'y conforme.

### 3.1 `verify` — commande moteur, sens unique

Lit les variables référencées dans la séquence de la campagne (via Lemlist), les confronte aux prompts
présents dans `prompts_dir`. Rapporte : `aligned` (toutes les variables ont un prompt), `missing_prompts`
(variable sans prompt → bloquant), `orphan_prompts` (prompt sans variable → avertissement). **Jamais
d'écriture vers Lemlist** : Lemlist est la vérité, le local se conforme.

### 3.2 Hook de conformance — `PostToolUse` (le harnais vérifie, pas Claude)

Un hook **`PostToolUse`** (composant plugin) se déclenche dès qu'une **édition d'un fichier campagne**
(prompt `prompts/*.md` ou `campaign.json`) est détectée, et lance `verify` sur la verticale concernée —
pour faire remonter toute dérive local↔séquence au moment exact où elle peut s'introduire, sans que Claude
ait à y penser. Best-effort (ignore si hors ligne / pas de clé). Le run (W3) refait `verify` en pré-launch
(le moment critique côté Lemlist).

### 3.3 Garde dure au launch (exigence non négociable)

**Jamais lancer un lead dont les variables custom ne sont pas remplies.** Le moteur `launch` **relit les
variables réelles du lead dans Lemlist par id** (`GET /leads?id=…`, fonctionne sans email — nos leads sont
LinkedIn-only) et **refuse** tout lead dont une variable requise (dérivée de la séquence) est **vide ou
absente**. Couvre même une variable vidée en UI entre le load et le launch. Filet final : la garde native de
Launch Lead. Un lead non conforme est rapporté, jamais validé silencieusement.

## 4. Surface moteur ajoutée (spec 02)

| Commande | Rôle | Sortie |
|---|---|---|
| `duplicate-campaign` | `POST /campaigns/{template_id}/duplicate` (name) | `{campaign_id, sequence_id}` |
| `create-list` | crée la liste audience | `{list_id}` |
| `verify` | conformance prompts ↔ variables séquence (sens unique) | `{aligned, missing_prompts, orphan_prompts}` |
| `register-campaign` | écrit `campaign.json` (ids + chemins) + entrée registre, atomique | confirmation |
| `fetch` (spec 1, étendu) | expose les **variables référencées** de la séquence | `{…, sequence_variables}` |

**Révisions spec 01 (cascade du principe SSoT)** :
- `campaign.json` perd `sequence` (logique campagne = drift local). Les clés de messages se dérivent du
  `fetch` Lemlist. `load_config` charge les prompts présents ; `verify` les confronte aux variables réelles.
- `launch` renforcé : garde dure « variables remplies » — relit le lead par id (`GET /leads?id=`) et refuse si une clé requise est vide (§3.3). Nouveau wrapper `lemlist.get_lead(key, lead_id)`.

## 5. Tests (pytest + workflow)

- `duplicate-campaign` : route `/campaigns/{id}/duplicate`, passe `name`, parse `campaign_id`/`sequence_id`.
- `create-list` / `register-campaign` : écriture atomique campaign.json + append registre, idempotence.
- `verify` : aligned / missing_prompts (bloquant) / orphan_prompts (warning) ; lit les variables depuis un
  `fetch` mocké, ne fait aucune écriture Lemlist.
- `launch` (renforcé) : refuse un lead à variable vide ; accepte un lead conforme.
- W2 : idempotence (re-run saute les `w2_steps` faits), pas de double duplication.

## 6. Hors-scope (specs suivantes)

Le sourcing/scoring/rédaction (W3, spec 03), les graders, W1 (interactif), le routeur. W2 ne fait que
créer la structure et garantir le contrat ; il ne remplit pas la campagne.
