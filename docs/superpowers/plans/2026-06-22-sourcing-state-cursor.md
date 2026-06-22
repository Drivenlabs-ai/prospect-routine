# Sourcing-state (marque-page + exclusion « déjà en campagne ») — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remplacer la mémoire locale cassée `seen_lead_ids` par un curseur de page qui avance dans le pool People DB (ordre stable) + une exclusion native des leads déjà en campagne via le filtre `out`.

**Architecture:** `source()` devient *une page au curseur* (page = `page_cursor`, size = lot du run) et renvoie `next_cursor` ; `cmd_source` persiste le curseur. Les leads déjà en campagne sont exclus par un filtre natif `{filterId:"leadLinkedInUrl", in:[], out:[…]}`, construit depuis les contacts Lemlist de la campagne. `seen_lead_ids` est supprimé de bout en bout.

**Tech Stack:** Python (stdlib uniquement, `uv run`), pytest. Moteur `scripts/prospect_engine/`. Source de vérité du design : `docs/superpowers/specs/2026-06-22-sourcing-state-cursor-design.md`.

## Global Constraints

- Python via `uv run` — jamais `pip` / `python3` direct. Suite : `uv run --with pytest python -m pytest -q`.
- TDD strict ; tests verts avant chaque commit ; un commit par tâche ; **ne pas pousser** (commits locaux).
- La correction « jamais contacter 2× » est déjà tenue par les `receipts` (skip au load) + le `deduplicate=true` natif — **ne pas la réimplémenter** dans cette couche.
- Clé de dédup du sourcing = `linkedinUrl`.
- Plafond du filtre `out` Lemlist ≈ 1000 URLs (3000 → 400) ; borner le set d'exclusion sous ce plafond.
- Ordre du pool People DB stable entre runs (vérifié) → le curseur de page est fiable.
- Clean-slate sur les fichiers édités (pas de trace de l'ancien comportement).

---

### Task 1 : `source()` page-based au curseur + `cmd_source` persiste le curseur

**Files:**
- Modify: `scripts/prospect_engine/sourcing.py` (signature + corps de `source`)
- Modify: `scripts/prospect_engine/cli.py` (`cmd_source`, ~lignes 80-85)
- Test: `tests/test_sourcing.py` (réécrit), `tests/test_cli.py` (ajout d'un test unitaire `cmd_source`)

**Interfaces:**
- Produces: `sourcing.source(key, filters, cursor, target, *, exclude=()) -> {"candidats": list, "limitation": int|None, "next_cursor": int, "exhausted": bool}`. `cmd_source` lit `state.page_cursor`, appelle `source`, écrit `state.page_cursor = next_cursor`.
- Consumes: `lemlist.search_people(key, filters, page, size)` (existant), `sourcing._project` (existant).

- [ ] **Step 1 : Réécrire `tests/test_sourcing.py`**

```python
"""Sourcing People DB : une page au curseur, exclusion native, projection, fin de pool."""
from prospect_engine import lemlist, sourcing


def _r(url, name="X Y", title="Gérant", company="Agence"):
    return {"lead_linkedin_url": url, "full_name": name, "title": title,
            "current_exp_company_name": company, "location": "Lyon", "lead_id": url[-1]}


def _page(*urls, limitation=1999):
    return (200, {"results": [_r(u) for u in urls], "limitation": limitation})


def test_source_projects_result_to_lead(monkeypatch):
    monkeypatch.setattr(lemlist, "search_people", lambda *a, **k: _page("https://lk/a"))
    out = sourcing.source("KEY", [], cursor=1, target=1)
    lead = out["candidats"][0]
    assert lead["linkedinUrl"] == "https://lk/a"
    assert lead["fullName"] == "X Y" and lead["jobTitle"] == "Gérant" and lead["companyName"] == "Agence"


def test_source_fetches_cursor_page_and_advances(monkeypatch):
    seen = {}
    def fake(key, filters, page, size):
        seen["page"], seen["size"] = page, size
        return _page("https://lk/a", "https://lk/b")
    monkeypatch.setattr(lemlist, "search_people", fake)
    out = sourcing.source("KEY", [], cursor=4, target=2)
    assert seen["page"] == 4 and seen["size"] == 2
    assert out["next_cursor"] == 5


def test_source_injects_out_filter_from_exclude(monkeypatch):
    cap = {}
    def fake(key, filters, page, size):
        cap["filters"] = filters
        return _page("https://lk/b")
    monkeypatch.setattr(lemlist, "search_people", fake)
    sourcing.source("KEY", [{"filterId": "country", "in": ["France"], "out": []}],
                    cursor=1, target=5, exclude={"https://lk/a"})
    out_f = [f for f in cap["filters"] if f["filterId"] == "leadLinkedInUrl"]
    assert out_f and out_f[0]["in"] == [] and out_f[0]["out"] == ["https://lk/a"]


def test_source_excludes_urls_client_side(monkeypatch):
    monkeypatch.setattr(lemlist, "search_people", lambda *a, **k: _page("https://lk/a", "https://lk/b"))
    out = sourcing.source("KEY", [], cursor=1, target=5, exclude={"https://lk/a"})
    assert [c["linkedinUrl"] for c in out["candidats"]] == ["https://lk/b"]


def test_source_dedups_within_page(monkeypatch):
    monkeypatch.setattr(lemlist, "search_people", lambda *a, **k: _page("https://lk/a", "https://lk/a"))
    out = sourcing.source("KEY", [], cursor=1, target=5)
    assert len(out["candidats"]) == 1


def test_source_marks_exhausted_on_short_page(monkeypatch):
    monkeypatch.setattr(lemlist, "search_people", lambda *a, **k: _page("https://lk/a"))
    out = sourcing.source("KEY", [], cursor=1, target=50)
    assert out["exhausted"] is True and out["next_cursor"] == 2


def test_source_not_exhausted_on_full_page(monkeypatch):
    monkeypatch.setattr(lemlist, "search_people", lambda *a, **k: _page("https://lk/a", "https://lk/b"))
    out = sourcing.source("KEY", [], cursor=1, target=2)
    assert out["exhausted"] is False


def test_source_propagates_limitation(monkeypatch):
    monkeypatch.setattr(lemlist, "search_people", lambda *a, **k: _page("https://lk/a", limitation=42))
    out = sourcing.source("KEY", [], cursor=1, target=1)
    assert out["limitation"] == 42
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run: `uv run --with pytest python -m pytest tests/test_sourcing.py -q`
Expected: FAIL (la signature actuelle est `source(key, filters, seen, target, …)`, pas de `cursor`/`next_cursor`).

- [ ] **Step 3 : Réécrire `source()` dans `scripts/prospect_engine/sourcing.py`**

Remplacer la fonction `source` (lignes 24-53) par (garder `_project` inchangé au-dessus) :

```python
def source(key, filters, cursor, target, *, exclude=()):
    """Une page du pool People DB à la position `cursor` (ordre stable). Renvoie les candidats
    projetés (hors `exclude`), le curseur suivant, le quota restant, et `exhausted` si la page est
    courte (fin de pool). `exclude` (linkedinUrl déjà en campagne) part en filtre `out` natif ET
    re-filtré côté client (filet si la troncature au plafond laisse passer)."""
    exclude = set(exclude)
    search = list(filters)
    if exclude:
        search = search + [{"filterId": "leadLinkedInUrl", "in": [], "out": list(exclude)}]
    st, res = lemlist.search_people(key, search, cursor, target)
    if st != 200 or not isinstance(res, dict):
        return {"candidats": [], "limitation": None, "next_cursor": cursor + 1, "exhausted": True}
    results = res.get("results") or []
    candidats, have = [], set()
    for r in results:
        lead = _project(r)
        url = lead["linkedinUrl"]
        if not url or url in exclude or url in have:
            continue
        candidats.append(lead)
        have.add(url)
    return {"candidats": candidats[:target], "limitation": res.get("limitation"),
            "next_cursor": cursor + 1, "exhausted": len(results) < target}
```

Mettre à jour le docstring de tête du module (lignes 1-6) pour refléter « une page au curseur, exclusion native » au lieu de « pagine … exclut les déjà-vus » :

```python
"""Sourcing People DB — code déterministe (le moteur), appelé par le routeur AVANT le workflow.

Lit UNE page du pool à la position du curseur (ordre People DB stable), exclut les URLs déjà en
campagne (filtre `out` natif), projette chaque résultat vers la forme lead, renvoie le curseur
suivant. Le `limitation` natif (quota/24 h) est remonté — on le respecte, on ne throttle pas.
"""
```

- [ ] **Step 4 : Lancer, vérifier le succès**

Run: `uv run --with pytest python -m pytest tests/test_sourcing.py -q`
Expected: PASS (8 tests).

- [ ] **Step 5 : Mettre à jour `cmd_source` dans `scripts/prospect_engine/cli.py`**

Remplacer `cmd_source` (lignes 80-85) par :

```python
def cmd_source(a):
    cfg = config.load_cfg_only(a.config)
    key = config.read_key(cfg["api_key_file"])
    st = state.load_state(cfg["state_dir"])
    cursor = st.get("page_cursor", 1)
    target = a.target if a.target is not None else cfg.get("sourcing_size", 50)
    out = sourcing.source(key, cfg.get("filters", []), cursor, target)
    st["page_cursor"] = out["next_cursor"]
    state.save_state(cfg["state_dir"], st)
    _emit(out)
```

- [ ] **Step 6 : Ajouter un test unitaire `cmd_source` dans `tests/test_cli.py`**

Ajouter en bas du fichier (et `import json` est déjà présent en tête) :

```python
def test_cmd_source_persists_advanced_cursor(monkeypatch, tmp_path):
    from prospect_engine import cli, lemlist, state
    sd = tmp_path / "state"
    keyfile = tmp_path / "k.md"
    keyfile.write_text("lemlist_api_key: X")
    cfg = tmp_path / "campaign.json"
    cfg.write_text(json.dumps({"state_dir": str(sd), "api_key_file": str(keyfile),
                               "campaign_id": "cam_1", "filters": [], "sourcing_size": 5}))
    monkeypatch.setattr(lemlist, "search_people",
                        lambda key, filters, page, size: (200, {"results": [], "limitation": 1}))

    class A:
        config = str(cfg)
        target = None
    cli.cmd_source(A())
    assert state.load_state(str(sd))["page_cursor"] == 2
```

- [ ] **Step 7 : Lancer la suite complète**

Run: `uv run --with pytest python -m pytest -q`
Expected: PASS (le reste inchangé ; `seen_lead_ids` existe encore dans l'état mais n'est plus lu par le sourcing).

- [ ] **Step 8 : Commit**

```bash
git add scripts/prospect_engine/sourcing.py scripts/prospect_engine/cli.py tests/test_sourcing.py tests/test_cli.py
git commit -m "sourcing — une page au curseur (page_cursor), avance et persiste le curseur

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2 : Exclusion « déjà en campagne » (filtre `out` depuis Lemlist)

**Files:**
- Modify: `scripts/prospect_engine/lemlist.py` (ajout `get_contacts`)
- Modify: `scripts/prospect_engine/sourcing.py` (ajout helper pur `loaded_urls`)
- Modify: `scripts/prospect_engine/cli.py` (`cmd_source` construit `exclude`)
- Test: `tests/test_sourcing.py` (ajout `loaded_urls`), `tests/test_cli.py` (maj test `cmd_source`)

**Interfaces:**
- Produces: `lemlist.get_contacts(key) -> list[dict]` (chaque contact porte `linkedinUrl` + `campaigns: [{campaignId}]`). `sourcing.loaded_urls(contacts, campaign_id, cap=900) -> set[str]`.
- Consumes: `sourcing.source(..., exclude=…)` de la Task 1.

- [ ] **Step 1 : Ajouter les tests `loaded_urls` dans `tests/test_sourcing.py`**

Ajouter en bas du fichier :

```python
def test_loaded_urls_keeps_only_this_campaign_members():
    contacts = [
        {"linkedinUrl": "https://lk/a", "campaigns": [{"campaignId": "cam_1"}]},
        {"linkedinUrl": "https://lk/b", "campaigns": [{"campaignId": "cam_2"}]},
        {"linkedinUrl": "https://lk/c", "campaigns": []},
        {"campaigns": [{"campaignId": "cam_1"}]},  # sans linkedinUrl → ignoré
    ]
    assert sourcing.loaded_urls(contacts, "cam_1") == {"https://lk/a"}


def test_loaded_urls_caps_at_limit():
    contacts = [{"linkedinUrl": f"https://lk/{i}", "campaigns": [{"campaignId": "cam_1"}]}
                for i in range(10)]
    assert len(sourcing.loaded_urls(contacts, "cam_1", cap=3)) == 3
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run: `uv run --with pytest python -m pytest tests/test_sourcing.py -k loaded_urls -q`
Expected: FAIL (`loaded_urls` n'existe pas).

- [ ] **Step 3 : Ajouter `loaded_urls` dans `scripts/prospect_engine/sourcing.py`**

Au-dessus de `def source(`, ajouter :

```python
EXCLUDE_CAP = 900  # sous le plafond du filtre `out` Lemlist (~1000)


def loaded_urls(contacts, campaign_id, cap=EXCLUDE_CAP):
    """linkedinUrl des contacts déjà membres de cette campagne (via `contact.campaigns`), borné au
    plafond `out`. C'est « Lemlist = mémoire » des leads déjà chargés."""
    urls = [c["linkedinUrl"] for c in contacts
            if c.get("linkedinUrl")
            and any(cm.get("campaignId") == campaign_id for cm in (c.get("campaigns") or []))]
    return set(urls[:cap])
```

- [ ] **Step 4 : Lancer, vérifier le succès**

Run: `uv run --with pytest python -m pytest tests/test_sourcing.py -k loaded_urls -q`
Expected: PASS (2 tests).

- [ ] **Step 5 : Ajouter `get_contacts` dans `scripts/prospect_engine/lemlist.py`**

Après `get_campaign_leads` (ligne 96), ajouter :

```python
def get_contacts(key):
    """Tous les contacts du compte (paginé). Chaque contact porte `linkedinUrl` + `campaigns[]`.
    Renvoie [] si l'appel échoue (le sourcing dégrade alors sans filtre d'exclusion)."""
    return paginate(key, "/contacts", {"limit": 100})
```

- [ ] **Step 6 : Brancher `exclude` dans `cmd_source` (`scripts/prospect_engine/cli.py`)**

Remplacer `cmd_source` par :

```python
def cmd_source(a):
    cfg = config.load_cfg_only(a.config)
    key = config.read_key(cfg["api_key_file"])
    st = state.load_state(cfg["state_dir"])
    cursor = st.get("page_cursor", 1)
    target = a.target if a.target is not None else cfg.get("sourcing_size", 50)
    exclude = sourcing.loaded_urls(lemlist.get_contacts(key), cfg["campaign_id"])
    out = sourcing.source(key, cfg.get("filters", []), cursor, target, exclude=exclude)
    st["page_cursor"] = out["next_cursor"]
    state.save_state(cfg["state_dir"], st)
    _emit(out)
```

- [ ] **Step 7 : Mettre à jour le test `cmd_source` dans `tests/test_cli.py`**

`cmd_source` appelle désormais `lemlist.get_contacts` ; le mocker. Remplacer `test_cmd_source_persists_advanced_cursor` par :

```python
def test_cmd_source_persists_advanced_cursor(monkeypatch, tmp_path):
    from prospect_engine import cli, lemlist, state
    sd = tmp_path / "state"
    keyfile = tmp_path / "k.md"
    keyfile.write_text("lemlist_api_key: X")
    cfg = tmp_path / "campaign.json"
    cfg.write_text(json.dumps({"state_dir": str(sd), "api_key_file": str(keyfile),
                               "campaign_id": "cam_1", "filters": [], "sourcing_size": 5}))
    monkeypatch.setattr(lemlist, "get_contacts", lambda key: [])
    monkeypatch.setattr(lemlist, "search_people",
                        lambda key, filters, page, size: (200, {"results": [], "limitation": 1}))

    class A:
        config = str(cfg)
        target = None
    cli.cmd_source(A())
    assert state.load_state(str(sd))["page_cursor"] == 2


def test_cmd_source_excludes_campaign_members(monkeypatch, tmp_path):
    from prospect_engine import cli, lemlist, state
    sd = tmp_path / "state"
    keyfile = tmp_path / "k.md"
    keyfile.write_text("lemlist_api_key: X")
    cfg = tmp_path / "campaign.json"
    cfg.write_text(json.dumps({"state_dir": str(sd), "api_key_file": str(keyfile),
                               "campaign_id": "cam_1", "filters": [], "sourcing_size": 5}))
    monkeypatch.setattr(lemlist, "get_contacts",
                        lambda key: [{"linkedinUrl": "https://lk/a", "campaigns": [{"campaignId": "cam_1"}]}])
    captured = {}
    def fake_search(key, filters, page, size):
        captured["filters"] = filters
        return (200, {"results": [{"lead_linkedin_url": "https://lk/a", "lead_id": "a"},
                                  {"lead_linkedin_url": "https://lk/b", "lead_id": "b"}],
                      "limitation": 1})
    monkeypatch.setattr(lemlist, "search_people", fake_search)

    class A:
        config = str(cfg)
        target = None
    cli.cmd_source(A())
    out_f = [f for f in captured["filters"] if f["filterId"] == "leadLinkedInUrl"]
    assert out_f and out_f[0]["out"] == ["https://lk/a"]
```

- [ ] **Step 8 : Lancer la suite complète**

Run: `uv run --with pytest python -m pytest -q`
Expected: PASS.

- [ ] **Step 9 : Commit**

```bash
git add scripts/prospect_engine/lemlist.py scripts/prospect_engine/sourcing.py scripts/prospect_engine/cli.py tests/test_sourcing.py tests/test_cli.py
git commit -m "sourcing — exclut les leads déjà en campagne via le filtre out (Lemlist)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3 : Suppression de `seen_lead_ids` (état, dedup, cli)

**Files:**
- Modify: `scripts/prospect_engine/state.py` (`STATE_DEFAULT`, suppr. `merge_seen`, `apply_commit`, `load_state`)
- Modify: `scripts/prospect_engine/dedup.py` (`dedup_check` perd `seen`)
- Modify: `scripts/prospect_engine/cli.py` (`cmd_prepare`, `cmd_dedup_check`, `cmd_record_run`)
- Test: `tests/test_state.py` (réécrit), `tests/test_cli.py` (tests record-run / dedup), `tests/test_dedup.py` (signature)

**Interfaces:**
- Produces: `state.apply_commit(state, date, n_sourced, n_true, n_false) -> state` (sans `seen`). `dedup.dedup_check(leads, ledger, campaign_id) -> {"allowed", "skipped"}` (sans `seen`). `STATE_DEFAULT = {"page_cursor": 1, "last_run": None, "history": []}`.

- [ ] **Step 1 : Réécrire `tests/test_state.py`**

```python
"""État machine : curseur de page, historique, status de reprise — écritures atomiques."""
from prospect_engine import state


def test_apply_commit_appends_history_entry():
    st = {"page_cursor": 1, "last_run": None, "history": []}
    state.apply_commit(st, "2026-06-15", 2, 1, 1)
    assert st["last_run"] == "2026-06-15"
    assert st["history"][-1] == {"date": "2026-06-15", "sourced": 2, "true": 1, "false": 1}


def test_apply_commit_does_not_track_seen():
    st = {"page_cursor": 1, "last_run": None, "history": []}
    state.apply_commit(st, "2026-06-15", 3, 0, 0)
    assert "seen_lead_ids" not in st


def test_save_load_state_roundtrip(tmp_path):
    st = {"page_cursor": 2, "last_run": "2026-06-15", "history": []}
    state.save_state(str(tmp_path), st)
    assert state.load_state(str(tmp_path)) == st


def test_load_state_default_when_absent(tmp_path):
    st = state.load_state(str(tmp_path / "nope"))
    assert st == {"page_cursor": 1, "last_run": None, "history": []}


def test_status_set_get_roundtrip(tmp_path):
    state.status_set(str(tmp_path), "phase1_done", True)
    state.status_set(str(tmp_path), "w2_steps", ["campaign", "sequence"])
    assert state.status_get(str(tmp_path), "phase1_done") is True
    assert state.status_get(str(tmp_path), "w2_steps") == ["campaign", "sequence"]


def test_load_status_default_when_absent(tmp_path):
    assert state.load_status(str(tmp_path)) == {
        "phase1_done": False, "w2_steps": [], "edit_in_progress": False, "last_run": None}
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run: `uv run --with pytest python -m pytest tests/test_state.py -q`
Expected: FAIL (`apply_commit` a encore la signature `(state, date, sourced, n_true, n_false, seen_cap)` ; `STATE_DEFAULT` contient `seen_lead_ids`).

- [ ] **Step 3 : Modifier `scripts/prospect_engine/state.py`**

Remplacer `STATE_DEFAULT` (ligne 14) :

```python
STATE_DEFAULT = {"page_cursor": 1, "last_run": None, "history": []}
```

Supprimer entièrement `merge_seen` (lignes 20-22) et remplacer `apply_commit` (lignes 25-34) par :

```python
def apply_commit(state, date, n_sourced, n_true, n_false):
    """Append l'historique du run + horodate. Aucune mémoire de déjà-vus ici : l'exclusion au
    sourcing se fait par le curseur de page + le filtre `out` (leads déjà en campagne)."""
    state["last_run"] = date
    state["history"].append({"date": date, "sourced": n_sourced, "true": n_true, "false": n_false})
    return state
```

Remplacer le corps de `load_state` qui renvoie le défaut (ligne 55) :

```python
        return dict(STATE_DEFAULT, history=[])
```

Mettre à jour le docstring de tête (ligne 4) :

```python
  state.json  : page_cursor (position dans le pool People DB), history, last_run
```

- [ ] **Step 4 : Lancer, vérifier le succès `test_state`**

Run: `uv run --with pytest python -m pytest tests/test_state.py -q`
Expected: PASS (6 tests).

- [ ] **Step 5 : Modifier `dedup.py` (signature sans `seen`)**

Remplacer `dedup_check` (lignes 11-29 de `scripts/prospect_engine/dedup.py`) par :

```python
def dedup_check(leads, ledger, campaign_id):
    """Partitionne `leads` en {allowed, skipped[{lead, reason}]} contre le ledger de reçus
    (déjà chargés dans cette campagne) et l'absence d'identifiant.

    ledger : dict (campaign_id, lead_key) -> reçu (cf. receipts.read_ledger).
    """
    allowed, skipped = [], []
    for lead in leads:
        key = lead_key(lead)
        if key is None:
            skipped.append({"lead": lead, "reason": "no_identifier"})
        elif (campaign_id, key) in ledger:
            skipped.append({"lead": lead, "reason": "already_loaded"})
        else:
            allowed.append(lead)
    return {"allowed": allowed, "skipped": skipped}
```

- [ ] **Step 6 : Mettre à jour `tests/test_dedup.py`**

Ouvrir `tests/test_dedup.py` et retirer le paramètre `seen` de chaque appel `dedup.dedup_check(...)` (passer `(leads, ledger, campaign_id)`), et supprimer tout test dont l'objet unique était l'exclusion par `seen` (la branche `already_seen` n'existe plus). Conserver/écrire au moins :

```python
def test_dedup_check_flags_already_loaded():
    from prospect_engine import dedup
    leads = [{"linkedinUrl": "https://lk/a"}, {"linkedinUrl": "https://lk/b"}]
    ledger = {("cam_1", "https://lk/a"): {"stage": "varset"}}
    out = dedup.dedup_check(leads, ledger, "cam_1")
    assert [l["linkedinUrl"] for l in out["allowed"]] == ["https://lk/b"]
    assert out["skipped"][0]["reason"] == "already_loaded"


def test_dedup_check_flags_no_identifier():
    from prospect_engine import dedup
    out = dedup.dedup_check([{"fullName": "Sans URL"}], {}, "cam_1")
    assert out["allowed"] == [] and out["skipped"][0]["reason"] == "no_identifier"
```

- [ ] **Step 7 : Modifier `cmd_prepare`, `cmd_dedup_check`, `cmd_record_run` dans `cli.py`**

`cmd_prepare` (lignes 30-32) — retirer `seenIds` (et la variable `inline`) :

```python
    _emit({"date": a.date, "config": cfg, "prompts": prompts, "dry_run": cfg.get("dry_run", True)})
```

`cmd_dedup_check` (lignes 47-52) — retirer `seen` :

```python
def cmd_dedup_check(a):
    cfg = config.load_cfg_only(a.config)
    leads = json.loads(Path(a.input).read_text(encoding="utf-8"))
    ledger = receipts.read_ledger(cfg["state_dir"])
    _emit(dedup.dedup_check(leads, ledger, cfg["campaign_id"]))
```

`cmd_record_run` — passer le *nombre* sourcé, plus de clés `seen` :

```python
def cmd_record_run(a):
    cfg = config.load_cfg_only(a.config)
    sourced = json.loads(Path(a.sourced_file).read_text(encoding="utf-8"))
    st = state.apply_commit(state.load_state(cfg["state_dir"]), a.date, len(sourced), a.true, a.false)
    state.save_state(cfg["state_dir"], st)
    _emit({"recorded": a.date, "history_len": len(st["history"])})
```

- [ ] **Step 8 : Mettre à jour `tests/test_cli.py` (record-run + dedup)**

Remplacer `test_cli_record_run_then_dedup_flags_seen` par deux tests (la dédup se fait désormais via les reçus, pas via `record-run`) :

```python
def test_cli_record_run_appends_history(tmp_path):
    cfg = _campaign(tmp_path)
    sourced = tmp_path / "sourced.json"
    sourced.write_text(json.dumps([{"linkedinUrl": "https://lk/a", "fullName": "A B"}]))
    r = run("record-run", "--config", cfg, "--date", "2026-06-15",
            "--sourced-file", str(sourced), "--true", "1", "--false", "0")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["history_len"] == 1


def test_cli_dedup_flags_already_loaded(tmp_path):
    from prospect_engine import receipts
    cfg = _campaign(tmp_path)
    state_dir = json.loads(Path(cfg).read_text())["state_dir"]
    receipts.append_receipt(state_dir, {"campaign_id": "cam_1", "lead_key": "https://lk/a",
                                        "stage": "varset", "ok": True})
    leads = tmp_path / "leads.json"
    leads.write_text(json.dumps([{"linkedinUrl": "https://lk/a", "fullName": "A B"},
                                 {"linkedinUrl": "https://lk/b", "fullName": "C D"}]))
    r = run("dedup-check", "--config", cfg, "--input", str(leads))
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert [l["linkedinUrl"] for l in out["allowed"]] == ["https://lk/b"]
    assert out["skipped"][0]["reason"] == "already_loaded"
```

> Note : `_campaign(tmp_path)` (helper existant de `test_cli.py`) doit produire une config dont `campaign_id` == `"cam_1"` et un `state_dir` sous `tmp_path`. Vérifier ce helper ; s'il fixe un autre `campaign_id`, aligner la valeur utilisée dans le reçu ci-dessus.

- [ ] **Step 9 : Vérifier qu'aucune référence à `seen_lead_ids` / `merge_seen` ne subsiste**

Run: `grep -rn "seen_lead_ids\|merge_seen\|seenIds\|already_seen" scripts/ tests/`
Expected: aucune sortie.

- [ ] **Step 10 : Lancer la suite complète (Python + JS)**

Run: `uv run --with pytest python -m pytest -q && node --test 'tests/js/**/*.test.js'`
Expected: PASS (Python + JS verts).

- [ ] **Step 11 : Commit**

```bash
git add scripts/prospect_engine/state.py scripts/prospect_engine/dedup.py scripts/prospect_engine/cli.py tests/test_state.py tests/test_dedup.py tests/test_cli.py
git commit -m "sourcing-state — supprime seen_lead_ids (curseur + filtre out le remplacent)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Migration (note d'exécution, pas une tâche)

Les `state.json` existants (ex. agence-immo) gardent une clé `seen_lead_ids` désormais **ignorée** (inoffensive). `page_cursor` repart de sa valeur courante (1) : au premier run du nouveau code, un re-sweep depuis la page 1 — les leads déjà en campagne exclus par `out`, quelques rejetés re-scorés une fois. Acceptable. Nettoyage optionnel : retirer la clé `seen_lead_ids` du fichier à la main (non requis).

## Self-review (effectué)

- **Couverture spec** : curseur (Task 1), exclusion `out` déjà-en-campagne (Task 2), suppression `seen_lead_ids` (Task 3), fallback fetch KO (`get_contacts` renvoie `[]` → `loaded_urls([])` = ∅), fin de pool (`exhausted`), borne du cap (`loaded_urls` cap). Migration documentée. ✓
- **Placeholders** : aucun — code complet à chaque étape. ✓
- **Cohérence des types** : `source(..., exclude=())→{candidats, limitation, next_cursor, exhausted}` (Task 1) consommé tel quel par `cmd_source` (Task 1/2) ; `loaded_urls(contacts, campaign_id, cap)→set` (Task 2) ; `apply_commit(state, date, n_sourced, n_true, n_false)` + `dedup_check(leads, ledger, campaign_id)` (Task 3) alignés avec leurs appelants `cmd_record_run` / `cmd_dedup_check`. ✓
- **Correction « jamais 2× »** : inchangée (receipts + dedup natif), hors périmètre — non touchée. ✓
