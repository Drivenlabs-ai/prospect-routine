"""Ledger de reçus — idempotence et reprise de la livraison.

Un reçu = une ligne JSON dans `receipts.jsonl` du dossier d'état de la verticale, écrite à
chaque progression d'un lead. Append-only : la lecture replie sur la DERNIÈRE ligne par
(campaign_id, lead_key) → crash-safe, et donne l'état d'avancement le plus récent de chaque lead.

Schéma d'un reçu :
  {ts, campaign_id, lead_key, contact_id, lead_id, stage, ok, error}
  stage ∈ upserted · listed · created · varset · launched
"""
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

LEDGER = "receipts.jsonl"


def lead_key(lead):
    """Identité stable d'un lead pour l'idempotence : linkedinUrl sinon email, sinon None.

    `deduplicate` natif de Lemlist ne matche que l'email ; nos leads LinkedIn-only n'en ont pas,
    d'où la primauté de linkedinUrl ici. Aucun identifiant → lead non dédupliquable (rejeté en amont)."""
    return (lead.get("linkedinUrl") or "").strip() or (lead.get("email") or "").strip() or None


def append_receipt(state_dir, receipt):
    """Ajoute un reçu au ledger (append-only). Horodate si `ts` absent."""
    d = Path(state_dir).expanduser()
    d.mkdir(parents=True, exist_ok=True)
    rec = dict(receipt)
    rec.setdefault("ts", datetime.now(timezone.utc).isoformat())
    with open(d / LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def read_ledger(state_dir):
    """Replie le ledger sur la dernière ligne par (campaign_id, lead_key)."""
    p = Path(state_dir).expanduser() / LEDGER
    out = {}
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        out[(rec.get("campaign_id"), rec.get("lead_key"))] = rec
    return out


def lookup(state_dir, campaign_id, key):
    """Reçu le plus récent pour (campaign_id, lead_key), ou None."""
    return read_ledger(state_dir).get((campaign_id, key))
