"""État machine local — jamais dans le Drive.

Deux fichiers dans `~/.claude/prospect-routine/<slug>/` :
  state.json  : seen_lead_ids (fenêtre glissante bornée), history, last_run, page_cursor
  status.json : phases de reprise des workflows (phase1_done, w2_steps, edit_in_progress, last_run)

Toutes les écritures sont atomiques (tmp + os.replace) — jamais d'état corrompu sur crash.
"""
import json
import os
import tempfile
from pathlib import Path

STATE_DEFAULT = {"seen_lead_ids": [], "page_cursor": 1, "last_run": None, "history": []}
STATUS_DEFAULT = {"phase1_done": False, "w2_steps": [], "edit_in_progress": False, "last_run": None}


# ---------- helpers purs ----------

def merge_seen(seen, new):
    """Union ordonnée, tout en string, sans doublon (premier vu conservé)."""
    return list(dict.fromkeys([str(x) for x in list(seen) + list(new)]))


def apply_commit(state, date, sourced, n_true, n_false, seen_cap=None):
    """Enregistre un run : ajoute les sourcés aux déjà-vus (fenêtre glissante), append l'historique.

    `seen_lead_ids` ne sert qu'à l'exclusion au sourcing ; la garantie « jamais deux fois » est
    tenue par le ledger de reçus + le `deduplicate` natif Lemlist. On borne donc à une fenêtre."""
    seen = merge_seen(state["seen_lead_ids"], sourced)
    state["seen_lead_ids"] = seen[-seen_cap:] if seen_cap and len(seen) > seen_cap else seen
    state["last_run"] = date
    state["history"].append({"date": date, "sourced": len(sourced), "true": n_true, "false": n_false})
    return state


# ---------- IO atomique ----------

def _atomic_write(path, payload):
    d = path.parent
    d.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    except Exception:
        os.unlink(tmp)
        raise


def load_state(state_dir):
    p = Path(state_dir).expanduser() / "state.json"
    if not p.exists():
        return dict(STATE_DEFAULT, seen_lead_ids=[], history=[])
    return json.loads(p.read_text(encoding="utf-8"))


def save_state(state_dir, state):
    _atomic_write(Path(state_dir).expanduser() / "state.json", state)


# ---------- status (reprise des workflows) ----------

def load_status(state_dir):
    p = Path(state_dir).expanduser() / "status.json"
    if not p.exists():
        return dict(STATUS_DEFAULT, w2_steps=[])
    return json.loads(p.read_text(encoding="utf-8"))


def save_status(state_dir, status):
    _atomic_write(Path(state_dir).expanduser() / "status.json", status)


def status_set(state_dir, key, value):
    status = load_status(state_dir)
    status[key] = value
    save_status(state_dir, status)
    return status


def status_get(state_dir, key=None):
    status = load_status(state_dir)
    return status if key is None else status.get(key)
