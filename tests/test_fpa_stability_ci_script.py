import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_fpa_stability_ci.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("run_fpa_stability_ci", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fpa_stability_ci_script_runs_rules_only_standard_suite(tmp_path):
    script = _load_script()
    exit_code = script.main([
        "--preset",
        "",
        "--suite",
        "standard",
        "--profiles",
        "strict_fpa",
        "--strategies",
        "rules_only",
        "--rule-sets",
        "strict_fpa_rs",
        "--max-retries",
        "0",
        "--output-dir",
        str(tmp_path),
    ])

    assert exit_code == 0
    assert (tmp_path / "fpa-stability-sampling-report.md").exists()
    assert (tmp_path / "fpa-stability-sampling-manifest.json").exists()


def test_fpa_stability_ci_script_dry_run_defaults_to_rules_only(capsys, tmp_path):
    script = _load_script()
    exit_code = script.main([
        "--dry-run",
        "--suite",
        "standard",
        "--output-dir",
        str(tmp_path),
    ])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["mode"] == "dry_run"
    assert payload["configs"] == [{
        "profile": "strict_fpa",
        "strategy": "rules_only",
        "rule_set": "strict_fpa_rs",
    }]
    assert payload["will_call_model"] is False


def test_fpa_stability_ci_script_dry_run_shows_real_model_preset(capsys, tmp_path):
    script = _load_script()
    exit_code = script.main([
        "--dry-run",
        "--preset",
        "strict-real-model",
        "--output-dir",
        str(tmp_path),
    ])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["suite"] == "standard"
    assert payload["configs"] == [{
        "profile": "strict_fpa",
        "strategy": "ai_first",
        "rule_set": "strict_fpa_rs",
    }]
    assert payload["thresholds"] == {
        "retryable_quality_issue_count": 0,
        "retry_count": 0,
    }
    assert payload["will_call_model"] is True
