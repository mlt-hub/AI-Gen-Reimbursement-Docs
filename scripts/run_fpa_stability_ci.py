"""Run FPA stability sampling as a CI-friendly quality gate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai_gen_reimbursement_docs.config_utils import load_api_key, load_base_url, load_model_name
from ai_gen_reimbursement_docs.fpa_stability_sampler import (
    parse_fpa_stability_sample_configs,
    resolve_fpa_stability_sample_preset,
    resolve_fpa_stability_suite_fixtures,
    run_fpa_stability_sampling,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run FPA stability sampling and fail on quality gate regressions.")
    parser.add_argument("--output-dir", default=str(ROOT / "tmp_fpa_stability_ci"))
    parser.add_argument("--preset", default="strict-real-model")
    parser.add_argument("--suite", default="")
    parser.add_argument("--fixture", action="append", default=[])
    parser.add_argument("--profiles", default="")
    parser.add_argument("--strategies", default="")
    parser.add_argument("--rule-sets", default="")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--model", default="")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--max-warnings", type=int, default=None)
    parser.add_argument("--max-quality-issues", type=int, default=None)
    parser.add_argument("--max-retryable-issues", type=int, default=None)
    parser.add_argument("--max-retries", type=int, default=None)
    return parser


def _thresholds_from_args(args: argparse.Namespace, preset: dict[str, object]) -> dict[str, int]:
    raw = preset.get("thresholds", {}) if isinstance(preset.get("thresholds", {}), dict) else {}
    thresholds = {str(key): int(value) for key, value in raw.items()}
    explicit = {
        "warning_count": args.max_warnings,
        "quality_issue_count": args.max_quality_issues,
        "retryable_quality_issue_count": args.max_retryable_issues,
        "retry_count": args.max_retries,
    }
    for key, value in explicit.items():
        if value is not None and value >= 0:
            thresholds[key] = value
    return thresholds


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    preset = resolve_fpa_stability_sample_preset(args.preset)
    suite = args.suite or str(preset.get("suite", "") or "")
    profiles = args.profiles or str(preset.get("profiles", "") or "")
    strategies = args.strategies or str(preset.get("strategies", "") or "")
    rule_sets = args.rule_sets or str(preset.get("rule_sets", "") or "")
    fixture_paths = list(args.fixture)
    if suite:
        fixture_paths.extend(resolve_fpa_stability_suite_fixtures(suite))
    fixture_paths = list(dict.fromkeys(fixture_paths))
    manifest = run_fpa_stability_sampling(
        fixture_paths=fixture_paths,
        output_dir=args.output_dir,
        configs=parse_fpa_stability_sample_configs(
            profiles=profiles,
            strategies=strategies,
            rule_sets=rule_sets,
        ),
        api_key=args.api_key or load_api_key(),
        model=args.model or load_model_name(),
        base_url=args.base_url or load_base_url(),
        thresholds=_thresholds_from_args(args, preset),
    )
    evaluation = manifest["comparison"].get("evaluation", {})
    status = evaluation.get("status", "none") if isinstance(evaluation, dict) else "none"
    print(json.dumps({
        "status": status,
        "report_path": manifest["report_path"],
        "run_count": len(manifest["runs"]),
    }, ensure_ascii=False, indent=2))
    return 2 if status == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
