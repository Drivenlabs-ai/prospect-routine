"""Pré-filtre local de déduplication — pur, zéro appel réseau.

Optimisation, PAS garantie de correction : la correction cross-campagne est tenue nativement par
`create-lead?deduplicate=true` (email) et nos reçus (linkedinUrl) ; l'opt-out par la suppression
native Lemlist. Ce filtre évite seulement de gaspiller des appels create-lead sur des leads qu'on
a déjà chargés dans cette campagne, déjà vus récemment, ou sans identifiant exploitable.
"""
from prospect_engine.receipts import lead_key


def dedup_check(leads, ledger, campaign_id, seen):
    """Partitionne `leads` en {allowed, skipped[{lead, reason}]}.

    ledger : dict (campaign_id, lead_key) -> reçu (cf. receipts.read_ledger).
    seen   : itérable de lead_keys déjà vus au sourcing (state.seen_lead_ids).
    """
    seen = set(seen)
    allowed, skipped = [], []
    for lead in leads:
        key = lead_key(lead)
        if key is None:
            skipped.append({"lead": lead, "reason": "no_identifier"})
        elif (campaign_id, key) in ledger:
            skipped.append({"lead": lead, "reason": "already_loaded"})
        elif key in seen:
            skipped.append({"lead": lead, "reason": "already_seen"})
        else:
            allowed.append(lead)
    return {"allowed": allowed, "skipped": skipped}
