"""Conformance prompts ↔ variables de séquence (sens unique : Lemlist = vérité, local conforme)."""
from prospect_engine import lemlist, verify


def _steps(*msgs):
    return [{"message": m, "type": "linkedinSend", "delay": 1} for m in msgs]


def _prompts(tmp_path, names):
    d = tmp_path / "prompts"
    d.mkdir()
    (d / "icpFit.md").write_text("scoring")
    for n in names:
        (d / f"{n}.md").write_text("msg")
    return str(d)


def test_parse_variables_extracts_all_tokens():
    assert verify.parse_variables(_steps("Salut {{firstName}}, {{icebreaker}}", "{{followup}}")) == \
        {"firstName", "icebreaker", "followup"}


def test_parse_variables_includes_subject():
    out = verify.parse_variables([{"message": "hi {{icebreaker}}", "subject": "{{closing}}"}])
    assert {"icebreaker", "closing"} <= out


def test_verify_aligned(monkeypatch, tmp_path):
    monkeypatch.setattr(lemlist, "get_campaign_sequences",
                        lambda k, c: (200, {"steps": _steps("{{firstName}} {{icebreaker}}", "{{followup}}", "{{closing}}")}))
    out = verify.verify("KEY", "cam_1", _prompts(tmp_path, ["icebreaker", "followup", "closing"]))
    assert out["aligned"] is True
    assert out["missing_prompts"] == [] and out["orphan_prompts"] == []


def test_verify_missing_prompt_blocks(monkeypatch, tmp_path):
    monkeypatch.setattr(lemlist, "get_campaign_sequences",
                        lambda k, c: (200, {"steps": _steps("{{icebreaker}}", "{{closing}}")}))
    out = verify.verify("KEY", "cam_1", _prompts(tmp_path, ["icebreaker"]))
    assert out["aligned"] is False
    assert out["missing_prompts"] == ["closing"]


def test_verify_orphan_prompt_warns_but_aligned(monkeypatch, tmp_path):
    monkeypatch.setattr(lemlist, "get_campaign_sequences",
                        lambda k, c: (200, {"steps": _steps("{{icebreaker}}")}))
    out = verify.verify("KEY", "cam_1", _prompts(tmp_path, ["icebreaker", "extra"]))
    assert out["aligned"] is True
    assert out["orphan_prompts"] == ["extra"]


def test_verify_ignores_builtin_personalization(monkeypatch, tmp_path):
    monkeypatch.setattr(lemlist, "get_campaign_sequences",
                        lambda k, c: (200, {"steps": _steps("{{firstName}} {{companyName}} {{icebreaker}}")}))
    out = verify.verify("KEY", "cam_1", _prompts(tmp_path, ["icebreaker"]))
    assert out["aligned"] is True and out["missing_prompts"] == []


def test_required_variables_returns_custom_only_sorted(monkeypatch):
    monkeypatch.setattr(lemlist, "get_campaign_sequences",
                        lambda k, c: (200, {"steps": _steps("{{firstName}} {{icebreaker}}", "{{followup}}")}))
    assert verify.required_variables("KEY", "cam_1") == ["followup", "icebreaker"]


def test_verify_extracts_steps_from_sequences_nesting(monkeypatch, tmp_path):
    monkeypatch.setattr(lemlist, "get_campaign_sequences",
                        lambda k, c: (200, {"sequences": [{"steps": _steps("{{icebreaker}}")}]}))
    out = verify.verify("KEY", "cam_1", _prompts(tmp_path, ["icebreaker"]))
    assert out["aligned"] is True


def test_verify_extracts_steps_from_dict_of_sequences(monkeypatch, tmp_path):
    # Forme réelle de l'API : un dict de séquences keyées par id ({seq_id: {_id, steps:[...]}}),
    # plusieurs séquences (invite sans message + séquence de messages).
    monkeypatch.setattr(lemlist, "get_campaign_sequences", lambda k, c: (200, {
        "seq_a": {"_id": "seq_a", "steps": [{"type": "linkedinInvite", "message": ""}]},
        "seq_b": {"_id": "seq_b", "steps": _steps("{{icebreaker}}", "{{followup}}", "{{closing}}")},
    }))
    out = verify.verify("KEY", "cam_1", _prompts(tmp_path, ["icebreaker", "followup", "closing"]))
    assert out["sequence_variables"] == ["closing", "followup", "icebreaker"]
    assert out["aligned"] is True and out["orphan_prompts"] == []
