"""CLI du moteur — glue I/O uniquement. Chaque sous-commande lit ses fichiers, appelle les
modules, imprime du JSON sur stdout. Aucune logique métier ici (elle vit dans les modules)."""
import argparse
import json
import time
from pathlib import Path

from prospect_engine import config, delivery, dedup, lemlist, receipts, state


def _emit(obj):
    print(json.dumps(obj, ensure_ascii=False))


# ---------- commandes ----------

def cmd_prepare(a):
    cfg, prompts = config.load_config(a.config)
    st = state.load_state(cfg["state_dir"])
    key = config.read_key(cfg["api_key_file"])
    code, _ = lemlist.get_team(key)
    if code != 200:
        raise SystemExit(f"STOP: GET /team → {code} (auth/API KO)")
    inline = cfg.get("seen_ids_inline_max", 3000)
    _emit({"date": a.date, "config": cfg, "seenIds": st["seen_lead_ids"][-inline:],
           "prompts": prompts, "dry_run": cfg.get("dry_run", True)})


def cmd_resolve(a):
    _emit(config.resolve_campaign(a.registry, slug=a.slug, campaign_id=a.campaign_id))


def cmd_fetch(a):
    cfg = config.load_cfg_only(a.config)
    key = config.read_key(cfg["api_key_file"])
    _, camp = lemlist.get_campaign(key, cfg["campaign_id"])
    leads = lemlist.get_campaign_leads(key, cfg["campaign_id"])
    _emit({"campaign": camp, "leads": leads, "counts": {"leads": len(leads)}})


def cmd_dedup_check(a):
    cfg = config.load_cfg_only(a.config)
    leads = json.loads(Path(a.input).read_text(encoding="utf-8"))
    ledger = receipts.read_ledger(cfg["state_dir"])
    seen = set(state.load_state(cfg["state_dir"])["seen_lead_ids"])
    _emit(dedup.dedup_check(leads, ledger, cfg["campaign_id"], seen))


def cmd_load_lead(a):
    cfg = config.load_cfg_only(a.config)
    key = config.read_key(cfg["api_key_file"])
    items = json.loads(Path(a.input).read_text(encoding="utf-8"))
    if isinstance(items, dict):
        items = [items]
    dry = cfg.get("dry_run", True)
    results = []
    for it in items:
        results.append(delivery.load_lead(
            key, it["lead"], it.get("variables", {}), cfg["campaign_id"], cfg["list_id"],
            cfg["state_dir"], confirm=a.confirm, dry_run=dry))
        if a.confirm and not dry:
            time.sleep(0.5)  # marge sous 20 req/2s (chaque load = ~4 appels)
    _emit({"results": results})


def cmd_launch(a):
    cfg = config.load_cfg_only(a.config)
    key = config.read_key(cfg["api_key_file"])
    items = json.loads(Path(a.input).read_text(encoding="utf-8"))
    _emit(delivery.launch_leads(key, items, cfg["campaign_id"], cfg["state_dir"], confirm=a.confirm))


def cmd_commit_state(a):
    cfg = config.load_cfg_only(a.config)
    sourced = json.loads(Path(a.sourced_file).read_text(encoding="utf-8"))
    st = state.apply_commit(state.load_state(cfg["state_dir"]), a.date, sourced, a.true, a.false,
                            seen_cap=cfg.get("seen_ids_inline_max", 3000))
    state.save_state(cfg["state_dir"], st)
    _emit({"seen_total": len(st["seen_lead_ids"]), "added": len(sourced)})


def cmd_status(a):
    cfg = config.load_cfg_only(a.config)
    if a.set:
        k, _, v = a.set.partition("=")
        try:
            val = json.loads(v)
        except json.JSONDecodeError:
            val = v
        state.status_set(cfg["state_dir"], k, val)
        _emit({k: val})
    elif a.get:
        _emit({a.get: state.status_get(cfg["state_dir"], a.get)})
    else:
        _emit(state.load_status(cfg["state_dir"]))


def cmd_log(a):
    cfg = config.load_cfg_only(a.config)
    d = Path(cfg["state_dir"]).expanduser()
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "log.md", "a", encoding="utf-8") as f:
        f.write(Path(a.entry_file).read_text(encoding="utf-8").rstrip() + "\n\n")
    _emit({"log": "ok"})


# ---------- parser ----------

def build_parser():
    ap = argparse.ArgumentParser(prog="routine.py", description="Moteur prospect-routine (IO déterministe).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("prepare"); p.add_argument("--config", required=True); p.add_argument("--date", required=True); p.set_defaults(fn=cmd_prepare)
    p = sub.add_parser("resolve"); p.add_argument("--registry", required=True); p.add_argument("--slug"); p.add_argument("--campaign-id", dest="campaign_id"); p.set_defaults(fn=cmd_resolve)
    p = sub.add_parser("fetch"); p.add_argument("--config", required=True); p.set_defaults(fn=cmd_fetch)
    p = sub.add_parser("dedup-check"); p.add_argument("--config", required=True); p.add_argument("--input", required=True); p.set_defaults(fn=cmd_dedup_check)
    p = sub.add_parser("load-lead"); p.add_argument("--config", required=True); p.add_argument("--input", required=True); p.add_argument("--confirm", action="store_true"); p.set_defaults(fn=cmd_load_lead)
    p = sub.add_parser("launch"); p.add_argument("--config", required=True); p.add_argument("--input", required=True); p.add_argument("--confirm", action="store_true"); p.set_defaults(fn=cmd_launch)
    p = sub.add_parser("commit-state"); p.add_argument("--config", required=True); p.add_argument("--date", required=True); p.add_argument("--sourced-file", required=True); p.add_argument("--true", type=int, required=True, dest="true"); p.add_argument("--false", type=int, required=True, dest="false"); p.set_defaults(fn=cmd_commit_state)
    p = sub.add_parser("status"); p.add_argument("--config", required=True); p.add_argument("--get"); p.add_argument("--set"); p.set_defaults(fn=cmd_status)
    p = sub.add_parser("log"); p.add_argument("--config", required=True); p.add_argument("--entry-file", required=True); p.set_defaults(fn=cmd_log)
    return ap


def main(argv=None):
    ap = build_parser()
    a = ap.parse_args(argv)
    a.fn(a)
