# SP-B — Édition de la séquence : Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendre la séquence d'une campagne existante éditable en langage naturel (contenu, structure, timing, canal) via l'API Lemlist, en gardant les prompts d'agents locaux synchronisés ; Lemlist reste source de vérité, et le moteur refuse toute mutation sur une campagne qui tourne.

**Architecture:** Moteur fin + orchestration NL (comme SP-A). Le moteur gagne quatre wrappers d'I/O Lemlist de mutation de séquence (`lemlist.py`), un module de logique déterministe (`sequence.py` : gate d'éditabilité + aplatissement lisible de la séquence), et leurs commandes CLI gardées. Le jugement (intention NL → mutations, rédaction de la copy, rédaction/ajustement des prompts) vit dans la skill `edit-campaign` étendue. `verify.py` reste read-only et réutilisé tel quel pour la couverture du contrat de variables.

**Tech Stack:** Python 3 (moteur + pytest) via `uv`. Skill + référence + routeur = Markdown lus par un modèle. Aucun changement JS.

## Global Constraints

- **Python via `uv` uniquement** — jamais `python3` / `pip`. Tests : `uv run --with pytest python -m pytest -q`.
- **Suites vertes avant chaque commit** — Python (ci-dessus) ET JS (`node --test 'tests/js/**/*.test.js'`, inchangé ici, doit rester vert).
- **Un commit par tâche. NE PAS pusher.** Branche : `v1.5-sp-b-edit-sequence` (déjà créée, stackée sur SP-A).
- **Commentaires Python en français** — comme les fichiers voisins du moteur.
- **Lemlist = source de vérité** — aucune représentation locale de la séquence ; les wrappers ne hardcodent aucun schéma de body (pass-through générique : le body est construit en session, à partir de la doc live `/lemlist`).
- **`verify.py` reste read-only** — SP-B ne le modifie pas ; le chemin d'écriture de séquence est neuf et séparé.
- **Gate dur** — toute commande de mutation de séquence/horaire refuse si la campagne a `status == "running"` (ou état inconnu). Le run et le sourcing n'écrivent jamais la séquence.
- **Fichiers lus par un modèle** (SKILL.md, référence, routeur) — invoquer `superpowers:writing-prompts` ET `plugin-dev:skill-development` AVANT de les écrire (Tasks 4–5).

---

### Task 1: Wrappers d'I/O de mutation de séquence (lemlist.py)

**Files:**
- Modify: `scripts/prospect_engine/lemlist.py` (ajouter 4 wrappers après `get_campaign_sequences`)
- Test: `tests/test_lemlist.py`

**Interfaces:**
- Consumes: `api_call(method, route, key, body=None)` (existant).
- Produces (pass-through générique, modèle C) :
  - `add_step(key, sequence_id, body) -> (status, res)` — `POST /sequences/{sequence_id}/steps`
  - `update_step(key, sequence_id, step_id, body) -> (status, res)` — `PATCH /sequences/{sequence_id}/steps/{step_id}`
  - `delete_step(key, sequence_id, step_id) -> (status, res)` — `DELETE /sequences/{sequence_id}/steps/{step_id}`
  - `update_schedule(key, schedule_id, body) -> (status, res)` — `PATCH /schedules/{schedule_id}`

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à `tests/test_lemlist.py` (le helper `FakeResp` et le pattern monkeypatch `api_call` existent déjà) :

```python
def test_add_step_route_method_body(monkeypatch):
    cap = {}
    def fake(method, route, key, body=None, **kw):
        cap.update(method=method, route=route, body=body); return 200, {"_id": "stp_1"}
    monkeypatch.setattr(lemlist, "api_call", fake)
    lemlist.add_step("KEY", "seq_1", {"type": "email", "subject": "S", "message": "M"})
    assert cap["method"] == "POST" and cap["route"] == "/sequences/seq_1/steps"
    assert cap["body"] == {"type": "email", "subject": "S", "message": "M"}


def test_update_step_route_method_body(monkeypatch):
    cap = {}
    def fake(method, route, key, body=None, **kw):
        cap.update(method=method, route=route, body=body); return 200, {}
    monkeypatch.setattr(lemlist, "api_call", fake)
    lemlist.update_step("KEY", "seq_1", "stp_9", {"type": "email", "message": "M2"})
    assert cap["method"] == "PATCH" and cap["route"] == "/sequences/seq_1/steps/stp_9"
    assert cap["body"] == {"type": "email", "message": "M2"}


def test_delete_step_route_method_no_body(monkeypatch):
    cap = {}
    def fake(method, route, key, body=None, **kw):
        cap.update(method=method, route=route, body=body); return 200, {"ok": True}
    monkeypatch.setattr(lemlist, "api_call", fake)
    lemlist.delete_step("KEY", "seq_1", "stp_9")
    assert cap["method"] == "DELETE" and cap["route"] == "/sequences/seq_1/steps/stp_9"
    assert cap["body"] is None


def test_update_schedule_route_method_body(monkeypatch):
    cap = {}
    def fake(method, route, key, body=None, **kw):
        cap.update(method=method, route=route, body=body); return 200, {}
    monkeypatch.setattr(lemlist, "api_call", fake)
    lemlist.update_schedule("KEY", "skd_1", {"start": "09:00", "end": "17:00"})
    assert cap["method"] == "PATCH" and cap["route"] == "/schedules/skd_1"
    assert cap["body"] == {"start": "09:00", "end": "17:00"}
```

- [ ] **Step 2: Lancer pour vérifier l'échec**

Run: `uv run --with pytest python -m pytest tests/test_lemlist.py -q -k "add_step or update_step or delete_step or update_schedule"`
Expected: FAIL — `AttributeError: module 'prospect_engine.lemlist' has no attribute 'add_step'`.

- [ ] **Step 3: Implémenter les 4 wrappers**

Dans `scripts/prospect_engine/lemlist.py`, après `get_campaign_sequences` :

```python
def add_step(key, sequence_id, body):
    """Ajoute une étape à une séquence. `body` porte `type` (requis) + champs selon le type
    (cf. doc live `/lemlist`). Pass-through : aucun schéma hardcodé ici."""
    return api_call("POST", f"/sequences/{sequence_id}/steps", key, body)


def update_step(key, sequence_id, step_id, body):
    """Édite une étape (subject/message/delay…). `type` figure dans `body` mais reste immuable côté
    Lemlist (changer de canal = delete + recreate)."""
    return api_call("PATCH", f"/sequences/{sequence_id}/steps/{step_id}", key, body)


def delete_step(key, sequence_id, step_id):
    """Supprime une étape. Lemlist refuse (400) si la campagne tourne — le gate l'attrape avant l'appel."""
    return api_call("DELETE", f"/sequences/{sequence_id}/steps/{step_id}", key)


def update_schedule(key, schedule_id, body):
    """Édite une fenêtre d'envoi (start/end/weekdays/timezone/secondsToWait — cf. doc live `/lemlist`)."""
    return api_call("PATCH", f"/schedules/{schedule_id}", key, body)
```

- [ ] **Step 4: Lancer pour vérifier le passage**

Run: `uv run --with pytest python -m pytest tests/test_lemlist.py -q`
Expected: PASS.

- [ ] **Step 5: Suite complète + commit**

Run: `uv run --with pytest python -m pytest -q`
Expected: tous PASS.

```bash
git add scripts/prospect_engine/lemlist.py tests/test_lemlist.py
git commit -m "lemlist — wrappers mutation de séquence (add/update/delete step, update schedule) (TDD)"
```

---

### Task 2: Module `sequence.py` — gate d'éditabilité + aplatissement

**Files:**
- Create: `scripts/prospect_engine/sequence.py`
- Test: `tests/test_sequence.py`

**Interfaces:**
- Consumes: rien (logique pure sur des dicts).
- Produces:
  - `CampaignActive(Exception)` — levée quand la séquence n'est pas éditable.
  - `ensure_editable(campaign) -> status` — lève `CampaignActive` si `campaign["status"] == "running"` ou si `status` absent ; sinon renvoie le `status`.
  - `summarize(sequences_res) -> [ {sequence_id, step_id, type, delay, subject, message} ]` — aplatit la réponse `get_campaign_sequences` (dict de séquences keyées par id) en gardant le `sequence_id` par étape (nécessaire pour cibler les mutations).

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `tests/test_sequence.py` :

```python
"""Édition de séquence : gate d'éditabilité + aplatissement lisible."""
import pytest
from prospect_engine import sequence


def test_ensure_editable_blocks_running():
    with pytest.raises(sequence.CampaignActive):
        sequence.ensure_editable({"status": "running"})


def test_ensure_editable_blocks_unknown_status():
    with pytest.raises(sequence.CampaignActive):
        sequence.ensure_editable({})


def test_ensure_editable_allows_paused_and_draft():
    assert sequence.ensure_editable({"status": "paused"}) == "paused"
    assert sequence.ensure_editable({"status": "draft"}) == "draft"


def test_summarize_flattens_keyed_sequences_with_ids():
    res = {
        "seq_1": {"steps": [
            {"_id": "stp_1", "type": "email", "delay": 0, "subject": "Hi", "message": "{{icebreaker}}"},
            {"_id": "stp_2", "type": "linkedinSend", "delay": 2, "message": "{{followup}}"},
        ]},
    }
    out = sequence.summarize(res)
    assert out == [
        {"sequence_id": "seq_1", "step_id": "stp_1", "type": "email", "delay": 0,
         "subject": "Hi", "message": "{{icebreaker}}"},
        {"sequence_id": "seq_1", "step_id": "stp_2", "type": "linkedinSend", "delay": 2,
         "subject": None, "message": "{{followup}}"},
    ]


def test_summarize_tolerates_non_dict():
    assert sequence.summarize("oops") == []
```

- [ ] **Step 2: Lancer pour vérifier l'échec**

Run: `uv run --with pytest python -m pytest tests/test_sequence.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'prospect_engine.sequence'`.

- [ ] **Step 3: Implémenter `sequence.py`**

Créer `scripts/prospect_engine/sequence.py` :

```python
"""Édition de séquence — logique déterministe.

Gate d'éditabilité (on ne mute jamais une campagne qui tourne) + aplatissement lisible de la séquence
pour montrer l'état et connaître les ids à muter. L'I/O Lemlist vit dans lemlist.py ; le jugement
(intention NL → mutations, copy, prompts) vit en session. On n'écrit jamais la séquence depuis le run.
"""


class CampaignActive(Exception):
    """La campagne envoie (ou état inconnu) : muter sa séquence est interdit — la mettre en pause d'abord."""


def ensure_editable(campaign):
    """Garde dure avant toute mutation de séquence. Refuse `running` (envoi actif ; éditer pendant l'envoi
    a un effet non documenté sur les leads en cours) et l'état inconnu (on ne mute pas à l'aveugle). Les
    autres états (paused, draft, ended, archived, errors) ne sont pas en envoi actif → éditables."""
    status = (campaign or {}).get("status")
    if status == "running":
        raise CampaignActive("campagne active (running) — mets-la en pause avant d'éditer la séquence")
    if status is None:
        raise CampaignActive("état de campagne inconnu — édition refusée par sécurité")
    return status


def summarize(sequences_res):
    """Aplatit la réponse get_campaign_sequences (dict {sequence_id: {steps: [...]}}) en une liste plate
    d'étapes portant leur `sequence_id` et `step_id` — de quoi montrer la séquence et cibler les mutations."""
    out = []
    seqs = sequences_res if isinstance(sequences_res, dict) else {}
    for seq_id, seq in seqs.items():
        if not isinstance(seq, dict):
            continue
        for st in seq.get("steps") or []:
            out.append({
                "sequence_id": seq_id,
                "step_id": st.get("_id"),
                "type": st.get("type"),
                "delay": st.get("delay"),
                "subject": st.get("subject"),
                "message": st.get("message"),
            })
    return out
```

- [ ] **Step 4: Lancer pour vérifier le passage**

Run: `uv run --with pytest python -m pytest tests/test_sequence.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Suite complète + commit**

Run: `uv run --with pytest python -m pytest -q`
Expected: tous PASS.

```bash
git add scripts/prospect_engine/sequence.py tests/test_sequence.py
git commit -m "sequence — gate d'éditabilité (refuse running) + aplatissement lisible (TDD)"
```

---

### Task 3: Commandes CLI séquence (lecture + mutations gardées)

**Files:**
- Modify: `scripts/prospect_engine/cli.py` (import `sequence` ; commandes `cmd_sequence`, `cmd_add_step`, `cmd_update_step`, `cmd_delete_step`, `cmd_edit_schedule` ; helper `_editable_or_stop` ; sous-parsers)
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `lemlist.{get_campaign, get_campaign_sequences, add_step, update_step, delete_step, update_schedule}` (Task 1), `sequence.{ensure_editable, summarize, CampaignActive}` (Task 2), `config.{load_cfg_only, read_key}` (existants).
- Produces: commandes `sequence`, `add-step`, `update-step`, `delete-step`, `edit-schedule`. Les 4 mutations passent par `_editable_or_stop(key, campaign_id)` (lit `get_campaign`, applique le gate, `raise SystemExit` si non éditable) AVANT l'appel de mutation. Body lu depuis `--input` (chemin de fichier), comme `load-lead`.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à `tests/test_cli.py` :

```python
def test_cmd_sequence_summarizes(monkeypatch, tmp_path, capsys):
    from prospect_engine import cli, config, lemlist
    cfg = {"api_key_file": "x", "campaign_id": "cam_1"}
    monkeypatch.setattr(config, "load_cfg_only", lambda p: cfg)
    monkeypatch.setattr(config, "read_key", lambda p: "KEY")
    monkeypatch.setattr(lemlist, "get_campaign_sequences",
                        lambda key, cid: (200, {"seq_1": {"steps": [{"_id": "stp_1", "type": "email",
                                                                     "delay": 0, "message": "{{icebreaker}}"}]}}))
    class A: config = "x"
    cli.cmd_sequence(A())
    out = json.loads(capsys.readouterr().out)
    assert out["steps"][0]["sequence_id"] == "seq_1" and out["steps"][0]["step_id"] == "stp_1"


def test_cmd_add_step_blocked_when_campaign_running(monkeypatch, tmp_path):
    from prospect_engine import cli, config, lemlist
    cfg = {"api_key_file": "x", "campaign_id": "cam_1"}
    monkeypatch.setattr(config, "load_cfg_only", lambda p: cfg)
    monkeypatch.setattr(config, "read_key", lambda p: "KEY")
    monkeypatch.setattr(lemlist, "get_campaign", lambda key, cid: (200, {"status": "running"}))
    called = {"add": False}
    monkeypatch.setattr(lemlist, "add_step", lambda *a, **k: called.__setitem__("add", True) or (200, {}))
    body = tmp_path / "b.json"; body.write_text(json.dumps({"type": "email", "subject": "S", "message": "M"}))
    class A:
        config = "x"; sequence_id = "seq_1"; input = str(body)
    with __import__("pytest").raises(SystemExit):
        cli.cmd_add_step(A())
    assert called["add"] is False  # mutation jamais appelée si campagne active


def test_cmd_add_step_passes_when_paused(monkeypatch, tmp_path, capsys):
    from prospect_engine import cli, config, lemlist
    cfg = {"api_key_file": "x", "campaign_id": "cam_1"}
    monkeypatch.setattr(config, "load_cfg_only", lambda p: cfg)
    monkeypatch.setattr(config, "read_key", lambda p: "KEY")
    monkeypatch.setattr(lemlist, "get_campaign", lambda key, cid: (200, {"status": "paused"}))
    cap = {}
    monkeypatch.setattr(lemlist, "add_step",
                        lambda key, sid, body: cap.update(sid=sid, body=body) or (200, {"_id": "stp_9"}))
    body = tmp_path / "b.json"; body.write_text(json.dumps({"type": "email", "subject": "S", "message": "M"}))
    class A:
        config = "x"; sequence_id = "seq_1"; input = str(body)
    cli.cmd_add_step(A())
    out = json.loads(capsys.readouterr().out)
    assert cap["sid"] == "seq_1" and cap["body"]["type"] == "email" and out["status"] == 200


def test_cli_delete_step_blocked_on_running_via_subprocess(tmp_path, monkeypatch):
    # Intégration parseur : la commande existe et exige ses flags.
    cfg = _campaign(tmp_path)
    r = run("delete-step", "--config", cfg, "--sequence-id", "seq_1", "--step-id", "stp_1")
    # Sans réseau réel le get_campaign échoue → état inconnu → gate STOP (returncode ≠ 0).
    assert r.returncode != 0
```

- [ ] **Step 2: Lancer pour vérifier l'échec**

Run: `uv run --with pytest python -m pytest tests/test_cli.py -q -k "sequence or step"`
Expected: FAIL — `AttributeError: module 'prospect_engine.cli' has no attribute 'cmd_sequence'` (et `invalid choice` pour le sous-parser).

- [ ] **Step 3: Implémenter les commandes + le gate + les sous-parsers**

Dans `scripts/prospect_engine/cli.py` : ajouter `sequence` à la ligne d'import du package :

```python
from prospect_engine import config, delivery, dedup, lemlist, receipts, sequence, sourcing, state, verify
```

Ajouter les commandes (après `cmd_source`) :

```python
def _editable_or_stop(key, campaign_id):
    """Lit l'état de la campagne et applique le gate dur. STOP si elle tourne (ou état illisible)."""
    _, camp = lemlist.get_campaign(key, campaign_id)
    try:
        sequence.ensure_editable(camp if isinstance(camp, dict) else {})
    except sequence.CampaignActive as e:
        raise SystemExit(f"STOP: {e}")


def cmd_sequence(a):
    cfg = config.load_cfg_only(a.config)
    key = config.read_key(cfg["api_key_file"])
    _, res = lemlist.get_campaign_sequences(key, cfg["campaign_id"])
    _emit({"steps": sequence.summarize(res)})


def cmd_add_step(a):
    cfg = config.load_cfg_only(a.config)
    key = config.read_key(cfg["api_key_file"])
    _editable_or_stop(key, cfg["campaign_id"])
    body = json.loads(Path(a.input).read_text(encoding="utf-8"))
    st, res = lemlist.add_step(key, a.sequence_id, body)
    _emit({"status": st, "result": res})


def cmd_update_step(a):
    cfg = config.load_cfg_only(a.config)
    key = config.read_key(cfg["api_key_file"])
    _editable_or_stop(key, cfg["campaign_id"])
    body = json.loads(Path(a.input).read_text(encoding="utf-8"))
    st, res = lemlist.update_step(key, a.sequence_id, a.step_id, body)
    _emit({"status": st, "result": res})


def cmd_delete_step(a):
    cfg = config.load_cfg_only(a.config)
    key = config.read_key(cfg["api_key_file"])
    _editable_or_stop(key, cfg["campaign_id"])
    st, res = lemlist.delete_step(key, a.sequence_id, a.step_id)
    _emit({"status": st, "result": res})


def cmd_edit_schedule(a):
    cfg = config.load_cfg_only(a.config)
    key = config.read_key(cfg["api_key_file"])
    _editable_or_stop(key, cfg["campaign_id"])
    body = json.loads(Path(a.input).read_text(encoding="utf-8"))
    st, res = lemlist.update_schedule(key, a.schedule_id, body)
    _emit({"status": st, "result": res})
```

Enregistrer les sous-parsers dans `build_parser()` (après le parser `source`) :

```python
    p = sub.add_parser("sequence"); p.add_argument("--config", required=True); p.set_defaults(fn=cmd_sequence)
    p = sub.add_parser("add-step"); p.add_argument("--config", required=True); p.add_argument("--sequence-id", required=True, dest="sequence_id"); p.add_argument("--input", required=True); p.set_defaults(fn=cmd_add_step)
    p = sub.add_parser("update-step"); p.add_argument("--config", required=True); p.add_argument("--sequence-id", required=True, dest="sequence_id"); p.add_argument("--step-id", required=True, dest="step_id"); p.add_argument("--input", required=True); p.set_defaults(fn=cmd_update_step)
    p = sub.add_parser("delete-step"); p.add_argument("--config", required=True); p.add_argument("--sequence-id", required=True, dest="sequence_id"); p.add_argument("--step-id", required=True, dest="step_id"); p.set_defaults(fn=cmd_delete_step)
    p = sub.add_parser("edit-schedule"); p.add_argument("--config", required=True); p.add_argument("--schedule-id", required=True, dest="schedule_id"); p.add_argument("--input", required=True); p.set_defaults(fn=cmd_edit_schedule)
```

- [ ] **Step 4: Lancer pour vérifier le passage**

Run: `uv run --with pytest python -m pytest tests/test_cli.py -q -k "sequence or step"`
Expected: PASS.

- [ ] **Step 5: Suite complète + commit**

Run: `uv run --with pytest python -m pytest -q`
Expected: tous PASS.

```bash
git add scripts/prospect_engine/cli.py tests/test_cli.py
git commit -m "cli — commandes séquence (lecture + add/update/delete-step + edit-schedule, gate dur) (TDD)"
```

---

### Task 4: Skill `edit-campaign` — section « Modifier la séquence » + référence

**Files:**
- Modify: `skills/edit-campaign/SKILL.md` (frontmatter `description` + nouvelle section « Modifier la séquence » + section « Périmètre »)
- Create: `references/edit-campaign/sequence-edit.md`

**Interfaces:**
- Consumes (commandes livrées) : `sequence`, `add-step`, `update-step`, `delete-step`, `edit-schedule` (Task 3) ; `verify` (existant) ; workflow néant (la copy/les prompts sont rédigés en session via `/lemlist`).
- Produces: un flux prose qui déclenche sur l'intention « modifier la séquence » et orchestre le flux gardé (gate → preview deux-faces → mutations → sync prompts → verify).

Pas de test unitaire (prose). Vérification = relecture + déclenchement.

- [ ] **Step 1: Invoquer `superpowers:writing-prompts` ET `plugin-dev:skill-development`**

Charger les deux skills avant d'écrire (fichiers lus par un modèle ; SKILL.md doit rester lean, détail en référence — progressive disclosure).

- [ ] **Step 2: Étendre la `description` du frontmatter**

Dans `skills/edit-campaign/SKILL.md`, ajouter à la `description` des déclencheurs séquence, sans résumé de workflow. Remplacer la phrase de périmètre actuelle « Couvre les filtres People DB et le prompt icpFit. » par :

```
Couvre le ciblage (filtres People DB + prompt icpFit) et la séquence (contenu d'un message, ajout/retrait/réordonnancement d'étapes, timing, canal) — « modifie la séquence », « reformule l'icebreaker », « ajoute une relance », « espace les relances », « passe l'étape 2 en LinkedIn ».
```

- [ ] **Step 3: Ajouter la section « Modifier la séquence » (lean, renvoie à la référence)**

Dans `skills/edit-campaign/SKILL.md`, après la section ciblage (avant « Périmètre »), ajouter :

```markdown
## Modifier la séquence

Éditer ce que dit/fait la séquence d'une campagne : contenu d'un message, structure (ajout / retrait /
réordonnancement d'étapes), timing (délais + fenêtres d'envoi), canal d'une étape. Lemlist reste la source
de vérité : on lit la séquence live, on applique les mutations par API, on ne stocke jamais la séquence en
local.

**Gate dur : la campagne ne doit pas tourner.** Le moteur refuse toute mutation si `status == running` —
mets la campagne en pause d'abord (geste séparé). Éditer une séquence en cours d'envoi a un effet non
documenté sur les leads déjà engagés.

Éditer une étape et **synchroniser les prompts d'agents locaux** est indissociable : une étape ajoutée ou
un message qui introduit un nouveau `{{var}}` exige un prompt `prompts/<var>.md`, sinon la variable sort
vide et le lead ne part pas. `verify` garde la couverture en fin de flux.

Flux détaillé (gate, preview à deux faces, contrat de variables, recreate de canal, résolution du
schedule) : `references/edit-campaign/sequence-edit.md` — le charger avant d'agir.
```

- [ ] **Step 4: Mettre à jour la section « Périmètre »**

Dans `skills/edit-campaign/SKILL.md`, la section « Périmètre » liste la séquence comme non couverte. La réécrire :

```markdown
## Périmètre

Couvert : le ciblage (filtres + icpFit) et la séquence (contenu, structure, timing, canal). Pas encore
couvert :
- la config et l'état (pause/reprise, réglages campagne, cadence de sourcing, modèles) ;
- dupliquer une verticale vers un nouveau segment puis ajuster.
```

- [ ] **Step 5: Écrire la référence `references/edit-campaign/sequence-edit.md`**

Créer `references/edit-campaign/sequence-edit.md` (contenu cible ; ajuster la formulation au passage writing-prompts, garder la substance) :

```markdown
# Modifier la séquence — flux détaillé (référence edit-campaign)

Chargé par `edit-campaign` pour éditer la séquence d'une campagne. Lemlist = source de vérité : on lit la
séquence live, on mute par API, aucune représentation locale. Commandes moteur via
`uv run python scripts/routine.py <cmd>`. Les schémas exacts des bodies (par type d'étape, par champ de
schedule) se lisent sur la doc live via `/lemlist` §séquence — ne pas les deviner.

## Flux (ordre = garde)

1. **resolve** la campagne → `campaign_id` + `config_path`.
2. **lire** la séquence et l'état : `sequence --config <config_path>` → étapes avec `sequence_id`,
   `step_id`, `type`, `delay`, `subject`, `message`. (Le moteur lit aussi l'état ; les mutations le
   re-vérifient.)
3. **gate** : si la campagne tourne, les commandes de mutation s'arrêtent (STOP). Le dire à l'utilisateur :
   « mets la campagne en pause d'abord » (pause = geste séparé, hors edit-campaign).
4. **comprendre** l'intention NL → traduire en mutations concrètes (quelles étapes, quels champs).
5. **preview à deux faces + accord explicite** (mutation live = action sortante) :
   (a) les changements de séquence ; (b) les prompts locaux à créer/ajuster/signaler-orphelin.
   Avertir si des leads sont déjà en cours de séquence (effet non documenté).
6. **appliquer** :
   - contenu / objet / délai → écrire le body dans un fichier, puis `update-step --config <config_path>
     --sequence-id <id> --step-id <id> --input <chemin>`.
   - ajout → `add-step --config <config_path> --sequence-id <id> --input <chemin>` (body avec `type` +
     champs requis ; position via `index`).
   - retrait → `delete-step --config <config_path> --sequence-id <id> --step-id <id>`.
   - réordonnancement → `update-step` avec `index`.
   - timing fenêtres → résoudre le `schedule_id` (via la doc live `/lemlist` : depuis la campagne), puis
     `edit-schedule --config <config_path> --schedule-id <id> --input <chemin>`.
   - canal → `type` immuable : `delete-step` puis `add-step` (recreate), en re-posant `index`, `delay`,
     contenu. Le signaler explicitement dans le preview.
7. **synchroniser les prompts locaux** (premier rang) : pour chaque `{{var}}` custom du nouveau jeu, créer
   `prompts/<var>.md` si l'étape est nouvelle, ajuster si l'étape éditée change l'angle (craft `/lemlist`) ;
   une étape retirée peut laisser un prompt orphelin → le signaler.
8. **verify** : `verify --config <config_path>` → `aligned` (zéro `missing_prompts`). Sinon créer/ajuster le
   prompt manquant et re-verify.
9. **confirmer** : nouvelle séquence + couverture du contrat de variables OK.

## Gardes

- Jamais de mutation sur une campagne `running` (gate moteur dur).
- Jamais de mutation sans preview + accord explicite.
- `verify` reste read-only : il constate la couverture, il n'écrit pas vers Lemlist. L'alignement d'angle
  d'un prompt est une responsabilité de craft, pas garanti par verify.
- Mutation partielle (une étape passe, la suivante échoue) → s'arrêter, re-lire la séquence (`sequence`),
  rapporter l'état réel ; Lemlist porte la vérité.
```

- [ ] **Step 6: Vérifier le déclenchement et la cohérence**

Relire : la `description` porte des déclencheurs séquence concrets sans résumé de workflow ; la section SKILL reste lean (renvoie à la référence) ; la référence ne hardcode aucun schéma de body (renvoie à `/lemlist`) ; aucune affirmation fausse sur l'API.

- [ ] **Step 7: Suites vertes + commit**

Run: `uv run --with pytest python -m pytest -q && node --test 'tests/js/**/*.test.js'`
Expected: tous PASS (aucun code touché — garde-fou).

```bash
git add skills/edit-campaign/SKILL.md references/edit-campaign/sequence-edit.md
git commit -m "edit-campaign — section + référence « modifier la séquence » (Lemlist-direct, gate, sync prompts)"
```

---

### Task 5: Routeur + README — bascule séquence en « couvert »

**Files:**
- Modify: `skills/prospect-routine/SKILL.md` (table « Trois intentions » + section « Créer / Modifier » + table « Références »)
- Modify: `README.md` (bullet `skills/edit-campaign/`)

**Interfaces:**
- Consumes: la skill `edit-campaign` étendue (Task 4).
- Produces: un routeur qui route les éditions de séquence vers `edit-campaign`.

Pas de test unitaire (prose). Vérification = relecture.

- [ ] **Step 1: Invoquer `superpowers:writing-prompts`**

Charger `superpowers:writing-prompts` avant d'éditer ces fichiers.

- [ ] **Step 2: Mettre à jour la table « Trois intentions » du routeur**

Dans `skills/prospect-routine/SKILL.md`, remplacer les deux lignes :

```
| modifier le ciblage d'une campagne | skill `edit-campaign` (filtres People DB + prompt icpFit) |
| modifier la séquence / la config / dupliquer | pas encore couvert — le dire, ne rien muter à la main |
```

par :

```
| modifier le ciblage ou la séquence d'une campagne | skill `edit-campaign` (ciblage + séquence) |
| modifier la config ou dupliquer une verticale | pas encore couvert — le dire, ne rien muter à la main |
```

- [ ] **Step 3: Mettre à jour la section « Créer / Modifier » du routeur**

Remplacer les deux puces « Modifier le ciblage » et « Modifier la séquence… » par :

```markdown
- **Modifier le ciblage ou la séquence** d'une campagne existante → skill `edit-campaign`. Ciblage (filtres
  People DB + prompt icpFit) : 100% local. Séquence (contenu, structure, timing, canal) : mutation directe
  de Lemlist, campagne en pause obligatoire, prompts locaux resynchronisés.
- **Modifier la config / l'état, ou dupliquer** une verticale → pas encore construit. Le dire à
  l'utilisateur ; ne pas muter à la main.
```

- [ ] **Step 4: Mettre à jour la table « Références » du routeur**

Dans la table « Références — charge avant d'agir », remplacer la ligne `Modifier le ciblage` par :

```
| Modifier le ciblage ou la séquence | skill `edit-campaign` (la séquence charge `references/edit-campaign/sequence-edit.md`) |
```

- [ ] **Step 5: Mettre à jour le README**

Dans `README.md`, §Composants, remplacer le bullet `skills/edit-campaign/` par :

```
- `skills/edit-campaign/` — **SP-A + SP-B** : modifie une campagne existante — ciblage (filtres People DB + prompt `icpFit`, 100% local) et séquence (contenu / structure / timing / canal, mutation directe Lemlist sur campagne en pause, prompts resynchronisés). Moteur : primitive `cursor` + wrappers de mutation de séquence.
```

Et dans §Statut, remplacer « l'édition du ciblage (`edit-campaign`, SP-A) est livrée ; séquence (SP-B), config/état (SP-C), dupliquer-segment (SP-D) restent au backlog. » par :

```
l'édition du ciblage (SP-A) et de la séquence (SP-B) via `edit-campaign` sont livrées ; config/état (SP-C) et dupliquer-segment (SP-D) restent au backlog.
```

- [ ] **Step 6: Vérifier la cohérence**

Run: `grep -n "pas encore couvert\|backlog" skills/prospect-routine/SKILL.md README.md`
Expected: la séquence n'apparaît plus comme non couverte ; seuls config/dupliquer (SP-C/SP-D) restent listés en attente.

- [ ] **Step 7: Suites vertes + commit**

Run: `uv run --with pytest python -m pytest -q && node --test 'tests/js/**/*.test.js'`
Expected: tous PASS.

```bash
git add skills/prospect-routine/SKILL.md README.md
git commit -m "routeur + README — édition de séquence couverte par edit-campaign (SP-B)"
```

---

## Self-Review

**Spec coverage** (`docs/superpowers/specs/2026-06-23-edit-campaign-sequence-design.md`) :
- Lemlist-direct, aucune représentation locale → Tasks 1/3 (wrappers + commandes mutent Lemlist ; rien stocké). ✓
- Gate dur « campagne en pause » côté moteur → Task 2 (`ensure_editable` refuse running/inconnu) + Task 3 (`_editable_or_stop` avant chaque mutation). ✓
- 4 types d'édition (contenu/structure/timing/canal) → Task 1 wrappers + Task 4 référence (canal = delete+recreate). ✓
- Sync des prompts locaux en premier rang + verify couverture → Task 4 (flux étape 7–8 ; verify réutilisé). ✓
- Garde sortante (preview + accord) + avertissement leads-en-cours → Task 4 (étape 5). ✓
- Invariant `verify` read-only / run n'écrit jamais la séquence → non modifié (verify intact) ; chemin d'écriture neuf et séparé (Tasks 1/3). ✓
- Où ça vit (extension edit-campaign + référence ; routeur bascule) → Tasks 4/5. ✓
- Schémas de body non hardcodés (golden rule) → Task 1 (pass-through) + Task 4 (renvoi `/lemlist`). ✓

**Placeholder scan** : chaque step de code porte le code réel ; prose cible verbatim. Le seul renvoi externe (schémas de body / résolution schedule_id → doc live `/lemlist`) est délibéré (golden rule du skill), pas un TBD. ✓

**Type consistency** : `add_step(key, sequence_id, body)`, `update_step(key, sequence_id, step_id, body)`, `delete_step(key, sequence_id, step_id)`, `update_schedule(key, schedule_id, body)` cohérents entre Task 1 (def), tests, et Task 3 (appels). `ensure_editable(campaign)->status` / `CampaignActive` / `summarize(res)->list` cohérents entre Task 2 (def), tests, et Task 3 (`_editable_or_stop`, `cmd_sequence`). Commandes CLI (`sequence`, `add-step`, `update-step`, `delete-step`, `edit-schedule`) cohérentes entre Task 3 et les références Task 4. ✓

**Ordre / dépendances** : Task 1 (wrappers) → Task 2 (gate/summarize, indépendant) → Task 3 (CLI, consomme 1+2) → Task 4 (skill, référence les commandes de 3) → Task 5 (routeur, route vers 4). ✓
