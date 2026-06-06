import importlib.util
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
