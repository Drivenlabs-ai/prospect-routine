---
spec: 01 — moteur (routine.py)
statut: à valider
date: 2026-06-14
dépend de: docs/architecture.md
---

# Spec 01 — Le moteur (`scripts/routine.py`)

Le socle. Seul point d'IO Lemlist déterministe **et** seul gardien de l'état machine. Zéro LLM, zéro décision métier. Tout ce qui est piloté par un modèle (sourcing, scoring, rédaction) vit dans les workflows et appelle ce moteur pour écrire dans Lemlist ou dans l'état.

Décisions de cadrage actées : **livraison en commande composite** (`deliver-lead` encaisse la chaîne complète, reprise et anti-saturation à l'intérieur), **réécriture ciblée** (on garde les primitives saines du v1, on supprime tout le chemin « colonnes + liste synchronisée » invalidé par le smoke test, on reconstruit la livraison sur le modèle C).

---

## 1. La surface — sous-commandes

| Commande | Rôle | Entrée | Sortie |
|---|---|---|---|
| `prepare` | Bootstrap d'un run : charge config + prompts + état, vérifie l'auth | `--config`, `--date` | `{date, config, seenIds, prompts, dry_run}` (STOP si auth/prompt KO) |
| `resolve` | Pont slug ↔ campaign_id via le registre | `--slug` ou `--campaign-id`, `--registry` | `{slug, campaign_id, folder, channels, status, config_path}` |
| `fetch` | Photo lecture-seule d'une campagne Lemlist | `--campaign-id` | `{campaign, sequence, leads, counts}` |
| `dedup-check` | Filtre exclusivité + opt-out + déjà-vus | `--input` (prospects), `--campaign-id`, `--registry` | `{allowed[], excluded[{lead, reason}]}` |
| `deliver-lead` | **Livraison composite (modèle C)** d'un lead | `--input` (1 lead + variables), `--campaign-id`, `--list-id`, `[--confirm]` | `{ok, lead_id, stage_reached, skipped, receipt}` |
| `commit-state` | Enregistre les déjà-vus + l'historique du run | `--sourced-file`, `--true`, `--false`, `--date` | confirmation + total seen |
| `status` | Lit/écrit la machine d'état (reprise des workflows) | `--get` ou `--set k=v` | `status.json` courant |
| `log` | Ajoute une entrée au journal | `--entry-file` | confirmation |

`resolve`, `commit-state`, `status`, `log` prennent aussi `--config` (chemin du `campaign.json` de la verticale) d'où le moteur lit `state_dir`, `api_key_file`, etc.

**Ce qui disparaît du v1** (mort avec le modèle A) : `push` (variante colonnes), `check-fields`, `verify-sync`, `record-push`, `build_push_plan`, `expected_columns`, `missing_fields`, `contact_payload` (la partie colonnes). Le compteur `pushed` de l'historique est remplacé par le **ledger de reçus** (cf. §4).

**Ce qui survit, réutilisé tel quel** : le client HTTP anti-WAF (`api_call`, User-Agent obligatoire, retry 429), l'écriture d'état atomique (`save_state`), `merge_seen`, `is_clean_message` (filet anti-message-cassé avant livraison), `_paginate`, `read_key`, `load_config` (chargement `campaign.json` + prompts).

---

## 2. `deliver-lead` — la livraison composite (cœur de la spec)

Une opération atomique au niveau lead. Le workflow W3 boucle dessus, il ne pilote jamais les appels API un par un.

### Séquence (modèle C « charger puis lancer »)

```
deliver-lead(lead, variables, campaign_id, list_id)
  0. lire le ledger de reçus ──► déjà livré pour cette campagne ?  ─oui─► { skipped: true }
  1. upsert-contact        POST /contacts                 → contact_id   (dédup natif linkedinUrl)
  2. add-to-list           POST /contacts/lists/{id}/...  → contact dans l'audience (liste NON synchronisée)
  3. create-lead           POST /campaigns/leads          → lead_id      (deduplicate:true ; marche campagne en pause)
  4. set-variables         POST /leads/{id}/variables     → variables free-form posées (pas de colonnes pré-déclarées)
  5. launch-lead           POST /leads/review/{id}        → lead passe en file d'envoi (garde native : refuse si variable manquante)
  ──► écrire le reçu (stage_reached, contact_id, lead_id) ──► { ok: true, lead_id }
```

### Garanties

- **Idempotence par construction.** Avant de livrer, le moteur lit le ledger ; si le prospect a déjà un reçu `launched` pour cette campagne → il saute. Un run coupé puis relancé reprend exactement où il s'est arrêté, zéro doublon, zéro re-contact.
- **Reprise au niveau étape.** Le reçu mémorise `contact_id` / `lead_id` et l'étape atteinte. Sur reprise d'un lead à mi-chaîne, on ne refait pas les étapes déjà passées (et `deduplicate:true` sur create-lead est un second filet).
- **Anti-saturation interne.** Throttle ≤ 20 req/2s entre appels, retry unique sur 429. C'est dans le moteur, pas dans le workflow.
- **Filet message.** Un lead dont une variable est structurellement cassée (`is_clean_message` faux) est rejeté avant l'étape 1 — jamais livré à moitié.

### Dry-run

Si `dry_run: true` dans la config **ou** absence de `--confirm` → aucun appel réseau, le moteur renvoie le plan d'actions (les 5 étapes qu'il *aurait* faites). Le push réel exige explicitement `dry_run: false` **et** `--confirm` (la verticale est « armée »). Identité de garde héritée du v1.

### Variables de lead, pas colonnes

Le modèle C écrit les messages comme **variables de lead free-form** (`POST /leads/{id}/variables`) : auto-créées, aucune colonne CRM à pré-déclarer en UI. C'est ce qui tue `check-fields` et le mur « colonne UI-only » du modèle A.

---

## 3. `dedup-check` — exclusivité stricte + opt-out

Décision actée : **un prospect, une seule campagne active**. `dedup-check` écarte un prospect si :

| Raison | Source de vérité |
|---|---|
| `already_seen` | ledger de reçus local de la verticale |
| `in_other_campaign` | membership cross-campagne (Lemlist *get-many-contacts*) croisé au registre |
| `opted_out` | ressource *unsubscribes* Lemlist |
| `already_in_campaign` | déjà présent dans la campagne courante |

Sortie : `{allowed[], excluded[{lead, reason}]}`. Le workflow W3 ne tente de livrer que `allowed`. Conséquence fonctionnelle : pas de chevauchement entre verticales, respect mécanique des désinscriptions.

---

## 4. État machine — trois fichiers, un dossier

Tout vit dans `~/.claude/prospect-routine/<slug>/` (jamais le Drive) :

| Fichier | Contenu | Écrit par |
|---|---|---|
| `state.json` | `seen_lead_ids` (fenêtre glissante bornée), `history`, `last_run` | `commit-state` |
| `status.json` | phases franchies (`phase1_done`, `w2_steps`, `edit_in_progress`, `last_run`) — reprise des workflows | `status` |
| `receipts.jsonl` | **ledger** : 1 ligne par lead livré `{ts, lead_key, contact_id, lead_id, campaign_id, stage, ok}` | `deliver-lead` |

`lead_key` = `linkedinUrl` (identité stable). Le ledger est la source d'idempotence ET le compteur de pushes (remplace le champ `pushed` de l'historique v1). Écriture append-only ; lecture = scan filtré par `campaign_id`.

`seen_lead_ids` reste borné à une fenêtre glissante (`seen_ids_inline_max`, défaut 3000) : il ne sert qu'à l'exclusion au sourcing, la garantie « jamais deux fois » est tenue par le ledger + le dédup natif Lemlist.

---

## 5. Contrats de config & registre

```jsonc
// campaign.json (verticale, Drive) — lu par le moteur
{ "campaign_id":"cam_…", "slug":"agence-immo", "list_id":"clt_…",
  "state_dir":"~/.claude/prospect-routine/agence-immo",
  "api_key_file":"~/.claude/linkedin-prospect.local.md",
  "sequence":["icebreaker","followup","closing"],
  "dry_run":false, "seen_ids_inline_max":3000 }

// campaigns-registry.json (racine Prospection, Drive) — lu par resolve & dedup-check
[ { "slug":"agence-immo", "campaign_id":"cam_…", "folder":"Agence Immo",
    "channels":["linkedin","email"], "status":"active", "config_path":"…/campaign.json" } ]
```

Le moteur **lit** ces fichiers, il ne les possède pas (SSoT : l'intelligence métier vit dans le Drive).

---

## 6. Surface API Lemlist mobilisée

`POST /contacts` (upsert) · `POST /contacts/lists/{id}/entities` (add-to-list) · `POST /campaigns/leads` (create-lead, `deduplicate:true`) · `POST /leads/{id}/variables` (set-variables) · `POST /leads/review/{id}` (launch) · `GET /contacts` (membership) · `GET` unsubscribes · `GET /campaigns/{id}` + `/leads` (fetch). Tous via `api_call` (User-Agent obligatoire, retry 429).

---

## 7. Gestion d'erreur

- **Pré-vol** : `GET /team` au démarrage de `prepare`/run → STOP si auth KO. Prompt manquant/vide → STOP (jamais de run à prompt vide).
- **Par lead** : une étape qui échoue arrête *ce* lead (reçu à `stage_reached`), n'interrompt pas le lot ; l'erreur est collectée et rendue. Le lead reprendra au prochain run.
- **Volume** : au-delà de 100 livraisons en un seul appel hors routine → exige `--force` (volume inhabituel = probable erreur).
- **Écritures d'état** : toujours atomiques (tmp + replace), jamais de state corrompu.

---

## 8. Tests (pytest, `tests/`)

Cibler les fonctions pures et les transitions, mocker `api_call` :

- `deliver-lead` : idempotence (reçu existant → skip), reprise à mi-chaîne (stage_reached respecté), dry-run (zéro appel réseau), filet message (variable cassée → rejet), throttle/retry 429.
- `dedup-check` : chaque raison d'exclusion isolée + combinées.
- `commit-state` : fenêtre glissante de `seen_lead_ids`, atomicité.
- `resolve` : slug connu / inconnu / via campaign_id inverse.
- `status` : get/set, reprise.

Cible : conserver et adapter les tests v1 encore pertinents, ajouter la couverture modèle C. Lancement : `uv run --with pytest python -m pytest`.

---

## 9. Hors-scope (specs ultérieures)

Le sourcing People DB, le scoring `icpFit`, la rédaction, l'orchestration de lot, les graders : tout ça est dans les workflows (specs 02+). Le moteur ne fait que l'IO et l'état — il est appelé, il ne décide pas.
