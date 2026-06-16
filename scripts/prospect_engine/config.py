"""Config & registre — le moteur LIT ces fichiers (Drive), il ne les possède pas (SSoT métier).

- read_key       : extrait la clé API d'un fichier `.local.md` (hors repo).
- load_config    : charge `campaign.json` + les prompts (1 .md par étape) ; STOP si un prompt manque.
- resolve_campaign : pont slug ↔ campaign_id via `campaigns-registry.json`.
"""
import json
import os
import re
import tempfile
from pathlib import Path


def read_key(path):
    txt = Path(path).expanduser().read_text(encoding="utf-8")
    m = re.search(r"lemlist_api_key:\s*(\S+)", txt)
    if not m:
        raise SystemExit(f"STOP: clé lemlist_api_key introuvable dans {path}")
    return m.group(1)


def load_cfg_only(config_path):
    """Charge uniquement `campaign.json` (sans les prompts). Pour les commandes qui n'en ont pas
    besoin (resolve, status, dedup-check, commit-state, log, fetch, load-lead, launch)."""
    p = Path(config_path).expanduser()
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise SystemExit(f"STOP: config illisible ({p}) — {e}")


def load_config(config_path):
    """Charge `campaign.json` + les prompts (icpFit puis chaque étape de `sequence`, dans l'ordre).
    La voix optionnelle (`cfg['voice']`) préfixe les messages, jamais le scoring icpFit.
    SystemExit si la config est illisible ou si un prompt est introuvable/vide."""
    config_path = Path(config_path).expanduser()
    try:
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise SystemExit(f"STOP: config illisible ({config_path}) — {e}")
    base = config_path.parent
    pdir = Path(cfg.get("prompts_dir", "prompts"))
    pdir = pdir if pdir.is_absolute() else base / pdir
    voice = ""
    if cfg.get("voice"):
        vf = Path(cfg["voice"]).expanduser()
        vf = vf if vf.is_absolute() else base / vf
        voice = vf.read_text(encoding="utf-8").strip() if vf.exists() else ""
        if not voice:
            raise SystemExit(f"STOP: voice introuvable ou vide ({vf})")
    # icpFit est requis. Les prompts de message se découvrent par fichier (PAS via un `sequence`
    # local — la structure vit dans Lemlist) ; `verify` confronte ces clés aux variables réelles.
    prompts = {}
    icp = pdir / "icpFit.md"
    icp_body = icp.read_text(encoding="utf-8").strip() if icp.exists() else ""
    if not icp_body:
        raise SystemExit(f"STOP: prompt 'icpFit' introuvable ou vide ({icp})")
    prompts["icpFit"] = icp_body
    for f in sorted(pdir.glob("*.md")):
        if f.stem == "icpFit":
            continue
        body = f.read_text(encoding="utf-8").strip()
        if not body:
            continue
        prompts[f.stem] = (voice + "\n\n---\n\n" + body) if voice else body
    return cfg, prompts


def _atomic_json(path, payload):
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    except Exception:
        os.unlink(tmp)
        raise


def register_campaign(registry_path, campaign_json_path, campaign_data, registry_entry):
    """Écrit `campaign.json` (linkage) + upsert l'entrée du registre par slug (idempotent). Atomique.
    Ne stocke QUE des pointeurs (ids + chemins), jamais la structure de campagne (SSoT Lemlist)."""
    _atomic_json(campaign_json_path, campaign_data)
    reg = Path(registry_path).expanduser()
    entries = json.loads(reg.read_text(encoding="utf-8")) if reg.exists() else []
    slug = registry_entry.get("slug")
    entries = [e for e in entries if e.get("slug") != slug] + [registry_entry]
    _atomic_json(reg, entries)


def resolve_campaign(registry_path, *, slug=None, campaign_id=None):
    """Retourne l'entrée du registre correspondant au slug OU au campaign_id. STOP si introuvable."""
    p = Path(registry_path).expanduser()
    try:
        entries = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise SystemExit(f"STOP: registre illisible ({p}) — {e}")
    for e in entries:
        if (slug and e.get("slug") == slug) or (campaign_id and e.get("campaign_id") == campaign_id):
            return e
    raise SystemExit(f"STOP: campagne introuvable dans le registre (slug={slug}, campaign_id={campaign_id})")
