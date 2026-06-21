"""Conformance prompts ↔ variables de séquence — gardien du contrat de variables.

Sens unique : la séquence Lemlist est la vérité (on lit ses variables référencées) ; le local doit
s'y conformer (un prompt par variable de message). On n'écrit JAMAIS vers Lemlist depuis ici.
"""
import re
from pathlib import Path

from prospect_engine import lemlist

# Variables de personnalisation natives Lemlist : référencées dans les messages mais ne nécessitent
# PAS de prompt (elles viennent des champs du lead, pas de notre rédaction).
BUILTINS = {
    "firstName", "lastName", "fullName", "name", "companyName", "company", "jobTitle", "title",
    "email", "phone", "linkedinUrl", "picture", "companyDomain", "city", "country", "location",
    "industry", "signature", "sendUserName", "sendUserFirstName", "sendUserEmail",
}

_TOKEN = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")


def parse_variables(steps):
    """Ensemble des variables `{{…}}` référencées dans les `message`/`subject` des steps."""
    out = set()
    for s in steps or []:
        for field in ("message", "subject"):
            out.update(_TOKEN.findall(s.get(field) or ""))
    return out


def _extract_steps(res):
    """Récupère la liste plate des steps, quelle que soit l'imbrication de la réponse."""
    if isinstance(res, dict):
        if "steps" in res:
            return res["steps"]
        if "sequences" in res:
            return [st for seq in res["sequences"] for st in (seq.get("steps") or [])]
        # Forme réelle de l'API : un dict de séquences keyées par id ({seq_id: {steps: […]}}).
        seqs = [v for v in res.values() if isinstance(v, dict) and "steps" in v]
        if seqs:
            return [st for seq in seqs for st in (seq.get("steps") or [])]
    if isinstance(res, list):
        if res and isinstance(res[0], dict) and "steps" in res[0]:
            return [st for seq in res for st in (seq.get("steps") or [])]
        return res
    return []


def required_variables(key, campaign_id):
    """Variables de message requises par la séquence (custom, hors personnalisation native) — triées.
    Source des clés que chaque lead doit porter avant launch (garde dure)."""
    st, res = lemlist.get_campaign_sequences(key, campaign_id)
    seq = parse_variables(_extract_steps(res) if st == 200 else [])
    return sorted(v for v in seq if v not in BUILTINS)


def verify(key, campaign_id, prompts_dir):
    """Confronte les variables de la séquence Lemlist aux prompts locaux.

    missing_prompts : variable de message sans prompt → BLOQUANT (aligned=False).
    orphan_prompts  : prompt sans variable correspondante → avertissement (n'empêche pas aligned)."""
    st, res = lemlist.get_campaign_sequences(key, campaign_id)
    seq_vars = parse_variables(_extract_steps(res) if st == 200 else [])
    custom = {v for v in seq_vars if v not in BUILTINS}
    prompt_keys = {p.stem for p in Path(prompts_dir).expanduser().glob("*.md") if p.stem != "icpFit"}
    missing = sorted(custom - prompt_keys)
    orphan = sorted(prompt_keys - seq_vars)
    return {"aligned": not missing, "missing_prompts": missing, "orphan_prompts": orphan,
            "sequence_variables": sorted(seq_vars), "prompt_keys": sorted(prompt_keys)}
