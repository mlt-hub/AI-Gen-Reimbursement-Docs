"""生成 项目功能点拆分表.xlsx（COSMIC 功能点度量）。

本模块是 COSMIC 管线的高层入口，内部委托至 cosmic_md / cosmic_ai / cosmic_writer。
"""

import logging
import os
from dataclasses import dataclass

from ai_gen_reimbursement_docs.cosmic_ai import load_user_config_from_meta
from ai_gen_reimbursement_docs.excel_source import (
    build_modules_from_tree_md, write_cfp_sum,
)
from ai_gen_reimbursement_docs.cosmic_writer import write_cosmic_xlsx, write_environment_sheet
from ai_gen_reimbursement_docs.cosmic_models import CosmicItem
from ai_gen_reimbursement_docs.cosmic_md import (
    export_empty_md, export_filled_md, fill_md_with_ai,
)
from ai_gen_reimbursement_docs.cosmic_validator import (
    CosmicIssue,
    CosmicValidationReport,
    validate_cosmic_items,
    write_cosmic_validation_json,
    write_cosmic_validation_report_md,
)

logger = logging.getLogger('ai_gen_reimbursement_docs.gen_cosmic')


@dataclass
class CosmicGenerationResult:
    formal_excel_path: str
    formal_excel_written: bool
    draft_excel_path: str
    draft_excel_written: bool
    validation_json_path: str
    validation_report_path: str
    status: str
    cfp_total: float | None
    item_count: int
    blocked_count: int
    warning_count: int


def parse_meta_md(meta_md_path: str) -> dict[str, str]:
    """解析文档元数据.md 为扁平字典。"""
    from ai_gen_reimbursement_docs.gen_spec import parse_meta_md
    return parse_meta_md(meta_md_path)


def init_cosmic_template_md(
    tree_md_path: str,
    project_name: str,
    output_md_path: str,
) -> str:
    """生成 COSMIC 模板 MD（模块树 + 空白数据移动表）。

    Args:
        tree_md_path: 功能清单-模块树.md 路径
        project_name: 项目名称
        output_md_path: 输出 MD 路径
    """
    logger.info("第3.2步：生成 COSMIC 模板 MD...")
    modules = build_modules_from_tree_md(tree_md_path)
    export_empty_md(modules, project_name, output_md_path)
    logger.info(f"COSMIC 模板 MD 已生成: {output_md_path}")
    return output_md_path, modules


def ai_fill_cosmic_md(
    md_path: str,
    tree_md_path: str,
    project_name: str,
    api_key: str,
    model: str = "",
    base_url: str = "",
    meta_md_path: str = "",
    modules: list | None = None,
) -> str:
    """AI 填充 COSMIC MD（调用 LLM 为每个 三级模块生成数据移动链）。

    Args:
        md_path: 待填充的 MD 路径（由 init_cosmic_template_md 生成）
        tree_md_path: 功能清单-模块树.md 路径
        project_name: 项目名称
        api_key: API Key
        model: 模型名
        base_url: API 端点
        meta_md_path: 文档元数据.md 路径（用于读取用户判定配置）
        modules: 预构建的模块列表，为 None 时从 tree_md_path 解析
    """
    logger.info("第3.3步：AI 填充 COSMIC 数据...")
    logger.debug(f"MODEL: {model}  BASE URL: {base_url or '默认'}  API Key: {'已设置' if api_key else '未设置'}")

    if modules is None:
        modules = build_modules_from_tree_md(tree_md_path)

    user_cfg: dict = {}
    if meta_md_path and os.path.exists(meta_md_path):
        user_cfg = load_user_config_from_meta(meta_md_path)

    fill_md_with_ai(
        md_path, modules, project_name,
        api_key, model, base_url,
        **user_cfg,
    )
    logger.info(f"COSMIC MD 已填充: {md_path}")
    return md_path


def _draft_excel_path(formal_output_path: str) -> str:
    root, ext = os.path.splitext(formal_output_path)
    return f"{root}-草稿{ext or '.xlsx'}"


def _excel_reason(
    report: CosmicValidationReport,
    *,
    formal_excel_written: bool,
    draft_excel_written: bool,
    allow_draft_excel_output: bool,
) -> str:
    if formal_excel_written:
        return "校验通过，已写正式 Excel"
    if draft_excel_written:
        return "存在待审问题，已按配置写入草稿 Excel"
    if report.status == "blocked":
        return "存在阻断问题，未写正式 Excel"
    if report.status == "review_required" and not allow_draft_excel_output:
        return "存在待审问题，草稿 Excel 输出未开启"
    return "未写入 Excel"


def generate_cosmic_artifacts(
    items: list[CosmicItem],
    template_path: str,
    formal_output_path: str,
    meta_md_path: str = "",
    *,
    md_dir: str = "",
    project_name: str = "",
    cfp_formula: str = "",
    modules: list | None = None,
    review_md_path: str = "",
    allow_draft_excel_output: bool = False,
    global_issues: list[CosmicIssue] | None = None,
) -> CosmicGenerationResult:
    """Generate structured COSMIC draft, validation report and gated Excel outputs."""
    logger.info("第3.4步：校验 COSMIC 结构化草稿...")
    meta = parse_meta_md(meta_md_path) if meta_md_path else {}
    report = validate_cosmic_items(
        items,
        project_name=project_name,
        cfp_formula=cfp_formula,
        global_issues=global_issues,
    )

    validation_json_path = (
        os.path.join(md_dir, '3.3.gen-cosmic-AI填充-COSMIC.json')
        if md_dir else ""
    )
    validation_report_path = (
        os.path.join(md_dir, '3.4.gen-cosmic-校验报告.md')
        if md_dir else ""
    )
    if validation_json_path:
        write_cosmic_validation_json(report, validation_json_path)

    if review_md_path:
        export_filled_md(modules or [], items, project_name, review_md_path)

    formal_excel_written = False
    draft_excel_written = False
    draft_output_path = _draft_excel_path(formal_output_path)
    cfp_total: float | None = None

    if report.status == "passed":
        os.makedirs(os.path.dirname(formal_output_path) or '.', exist_ok=True)
        saved_path = write_cosmic_xlsx(
            template_path, formal_output_path, report,
            meta=meta, cfp_formula=cfp_formula,
        )
        _write_environment_if_needed(saved_path, project_name, meta)
        formal_output_path = saved_path
        formal_excel_written = True
        cfp_total = _calculate_cfp_total_for_written_excel(items)
        if md_dir:
            write_cfp_sum(md_dir, cfp_total)
        logger.info("项目功能点拆分表已生成: %s (%d 个功能过程)", saved_path, len(items))
    elif report.status == "review_required" and allow_draft_excel_output:
        os.makedirs(os.path.dirname(draft_output_path) or '.', exist_ok=True)
        saved_path = write_cosmic_xlsx(
            template_path, draft_output_path, report,
            meta=meta, cfp_formula=cfp_formula,
        )
        _write_environment_if_needed(saved_path, project_name, meta)
        draft_output_path = saved_path
        draft_excel_written = True
        logger.warning("COSMIC 存在待审问题，仅写入草稿 Excel: %s", saved_path)
    else:
        logger.warning("COSMIC 校验状态为 %s，未写正式 Excel", report.status)

    reason = _excel_reason(
        report,
        formal_excel_written=formal_excel_written,
        draft_excel_written=draft_excel_written,
        allow_draft_excel_output=allow_draft_excel_output,
    )
    if validation_report_path:
        write_cosmic_validation_report_md(
            report,
            validation_report_path,
            formal_excel_written=formal_excel_written,
            draft_excel_written=draft_excel_written,
            excel_reason=reason,
        )

    return CosmicGenerationResult(
        formal_excel_path=formal_output_path,
        formal_excel_written=formal_excel_written,
        draft_excel_path=draft_output_path,
        draft_excel_written=draft_excel_written,
        validation_json_path=validation_json_path,
        validation_report_path=validation_report_path,
        status=report.status,
        cfp_total=cfp_total,
        item_count=len(items),
        blocked_count=report.summary.get("blocked", 0),
        warning_count=report.summary.get("warnings", 0) + report.summary.get("global_warnings", 0),
    )


def _write_environment_if_needed(output_path: str, project_name: str, meta: dict[str, str]) -> None:
    target = meta.get("建设目标", "")
    necessity = meta.get("建设必要性", "")
    if target or necessity:
        write_environment_sheet(output_path, output_path, project_name, target, necessity)


def _calculate_cfp_total_for_written_excel(items: list[CosmicItem]) -> float:
    return float(sum(len(item.movements) for item in items))
