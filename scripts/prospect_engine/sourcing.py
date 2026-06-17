"""Sourcing People DB — code déterministe (le moteur), appelé par le routeur AVANT le workflow.

Pagine la recherche, exclut les déjà-vus (par linkedinUrl), projette chaque résultat brut vers la
forme lead consommée en aval, et s'arrête à `target` candidats, quota épuisé, ou pages épuisées.
Le `limitation` natif (quota/24 h) est remonté — on le respecte, on ne throttle pas nous-mêmes.
"""
from prospect_engine import lemlist


def _project(r):
    """Résultat brut People DB → forme lead (linkedinUrl, fullName, jobTitle, companyName, …)."""
    return {
        "linkedinUrl": r.get("lead_linkedin_url") or "",
        "fullName": r.get("full_name") or "",
        "jobTitle": r.get("title") or r.get("title_normalized") or "",
        "companyName": r.get("current_exp_company_name") or r.get("company_name") or "",
        "location": r.get("location") or "",
        "summary": r.get("summary") or "",
        "headline": r.get("headline") or "",
        "people_db_id": str(r.get("lead_id") or ""),
    }


def source(key, filters, seen, target, *, max_pages=10, size=100):
    """Source jusqu'à `target` candidats inédits. Retourne {candidats, limitation, pages_used, exhausted}."""
    seen = set(seen)
    candidats, have = [], set()
    limitation, pages_used, exhausted, page = None, 0, False, 1
    while len(candidats) < target and page <= max_pages:
        st, res = lemlist.search_people(key, filters, page, size)
        pages_used += 1
        if st != 200 or not isinstance(res, dict):
            break
        limitation = res.get("limitation", limitation)
        results = res.get("results") or []
        if not results:
            exhausted = True
            break
        for r in results:
            lead = _project(r)
            url = lead["linkedinUrl"]
            if not url or url in seen or url in have:
                continue
            candidats.append(lead)
            have.add(url)
            if len(candidats) >= target:
                break
        if len(results) < size:
            exhausted = True
            break
        page += 1
    return {"candidats": candidats[:target], "limitation": limitation,
            "pages_used": pages_used, "exhausted": exhausted}
