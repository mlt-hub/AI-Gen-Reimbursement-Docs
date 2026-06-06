"""Batch runner for FPA stability sampling over fixture cases."""

from dataclasses import dataclass
import json
from pathlib import Path
import re

from ai_gen_reimbursement_docs.fpa_stability_report import (
    build_fpa_stability_comparison,
    render_fpa_stability_comparison_markdown,
)
from ai_gen_reimbursement_docs.gen_fpa import plan_fpa_md_from_tree


@dataclass(frozen=True)
class FpaStabilitySampleConfig:
    profile: str
    strategy: str
    rule_set: str


def run_fpa_stability_sampling(
    *,
    fixture_paths: list[str],
    output_dir: str,
    configs: list[FpaStabilitySampleConfig],
    api_key: str = "",
    model: str = "",
    base_url: str = "",
) -> dict[str, object]:
    """Run FPA planning for fixture/config combinations and render a comparison report."""
    if not fixture_paths:
        raise ValueError("至少需要一个 FPA fixture")
    if not configs:
        raise ValueError("至少需要一个 FPA 采样配置")
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    trace_paths: list[str] = []
    runs: list[dict[str, object]] = []
    for fixture_path in fixture_paths:
        case = _load_fixture(fixture_path)
        case_id = _safe_name(str(case.get("case_id", "") or Path(fixture_path).stem))
        for config in configs:
            run_id = _safe_name(
                f"{case_id}__{config.profile or 'default'}__{config.strategy or 'default'}__{config.rule_set or 'default'}"
            )
            run_dir = output_root / run_id
            run_dir.mkdir(parents=True, exist_ok=True)
            tree_md = run_dir / "module_tree.md"
            meta_md = run_dir / "meta.md"
            fpa_md = run_dir / "fpa.md"
            summary_md = run_dir / "summary.md"
            audit_trace = run_dir / "fpa_audit_trace.json"
            _write_tree_md(tree_md, _case_rows(case))
            _write_meta_md(meta_md, _case_meta(case))
            plan_fpa_md_from_tree(
                str(tree_md),
                str(meta_md),
                str(fpa_md),
                api_key=api_key,
                model=model,
                base_url=base_url,
                summary_md_path=str(summary_md),
                profile_name=config.profile,
                strategy=config.strategy,
                rule_set=config.rule_set,
                audit_trace_path=str(audit_trace),
            )
            trace_paths.append(str(audit_trace))
            runs.append({
                "case_id": case_id,
                "profile": config.profile,
                "strategy": config.strategy,
                "rule_set": config.rule_set,
                "run_dir": str(run_dir),
                "audit_trace": str(audit_trace),
            })

    comparison = build_fpa_stability_comparison(trace_paths)
    report_md = output_root / "fpa-stability-sampling-report.md"
    report_md.write_text(
        render_fpa_stability_comparison_markdown(comparison),
        encoding="utf-8",
    )
    manifest = {
        "fixture_paths": fixture_paths,
        "runs": runs,
        "comparison": comparison,
        "report_path": str(report_md),
    }
    (output_root / "fpa-stability-sampling-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest


def parse_fpa_stability_sample_configs(
    *,
    profiles: str = "",
    strategies: str = "",
    rule_sets: str = "",
) -> list[FpaStabilitySampleConfig]:
    profile_items = _csv_values(profiles) or [""]
    strategy_items = _csv_values(strategies) or ["rules_only"]
    rule_set_items = _csv_values(rule_sets) or [""]
    return [
        FpaStabilitySampleConfig(profile=profile, strategy=strategy, rule_set=rule_set)
        for profile in profile_items
        for strategy in strategy_items
        for rule_set in rule_set_items
    ]


def _load_fixture(path: str) -> dict[str, object]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"FPA fixture must be a JSON object: {path}")
    return data


def _case_rows(case: dict[str, object]) -> list[dict[str, str]]:
    rows = case.get("rows", [])
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _case_meta(case: dict[str, object]) -> dict[str, str]:
    meta = case.get("meta", {})
    if not isinstance(meta, dict):
        return {}
    return {str(key): str(value) for key, value in meta.items()}


def _write_meta_md(path: Path, meta: dict[str, str]) -> None:
    rows = "\n".join(f"| {key} | {value} |" for key, value in meta.items())
    path.write_text(f"# 文档元数据\n\n{rows}\n", encoding="utf-8")


def _write_tree_md(path: Path, rows: list[dict[str, str]]) -> None:
    lines = [
        "| 入口 | 一级模块 | 二级模块 | 三级模块 | 客户端类型 | 三级模块整体功能描述 | 功能过程 | 功能过程类型 | 功能过程描述 |",
        "|------|---------|---------|---------|----------|----------------------|----------|--------------|--------------|",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join([
                "后台",
                str(row.get("一级模块", "")),
                str(row.get("二级模块", "")),
                str(row.get("三级模块", "")),
                str(row.get("客户端类型", "")),
                str(row.get("三级模块整体功能描述", "")),
                str(row.get("功能过程", "")),
                str(row.get("功能过程类型", "")),
                str(row.get("功能过程描述", "")),
            ])
            + " |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _csv_values(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _safe_name(value: str) -> str:
    return re.sub(r'[\\/:*?"<>|\s]+', "_", value).strip("_") or "sample"
