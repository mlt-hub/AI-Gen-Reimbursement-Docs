"""生成 项目功能点拆分表.xlsx（COSMIC 功能点度量）。

本模块是 COSMIC 管线的高层入口，内部委托至 cosmic_md / cosmic_ai / cosmic_writer。
"""

import logging
import os
import shutil

from ai_gen_reimbursement_docs.cosmic_ai import load_user_config_from_meta
from ai_gen_reimbursement_docs.excel_source import (
    build_modules_from_tree_md, write_cfp_sum,
)
from ai_gen_reimbursement_docs.cosmic_writer import write_cosmic_xlsx, write_environment_sheet
from ai_gen_reimbursement_docs.cosmic_md import (
    export_empty_md, fill_md_with_ai, parse_md_to_items,
)

logger = logging.getLogger('ai_gen_reimbursement_docs.gen_cosmic')


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


def generate_cosmic_xlsx_from_md(
    md_path: str,
    template_path: str,
    output_path: str,
    meta_md_path: str = "",
    *,
    md_dir: str = "",
    project_name: str = "",
    cfp_formula: str = "",
) -> str:
    """从已填充的 COSMIC MD 生成 项目功能点拆分表.xlsx。

    同时写入 CFP 总和 MD 和更新环境图 sheet。
    cfp_formula 优先从 Excel 元数据 sheet 读取，空则用默认公式。

    Returns:
        output_path
    """
    logger.info("第3.4步：从 COSMIC MD 生成 Excel...")

    items = parse_md_to_items(md_path)
    if not items:
        logger.warning("COSMIC MD 中未解析到任何功能点，跳过 Excel 生成")
        return output_path

    meta = parse_meta_md(meta_md_path) if meta_md_path else {}

    kws = {"meta": meta}
    if cfp_formula:
        kws["cfp_formula"] = cfp_formula
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    saved_path = write_cosmic_xlsx(template_path, output_path, items, **kws)

    target = meta.get("建设目标", "")
    necessity = meta.get("建设必要性", "")
    if target or necessity:
        write_environment_sheet(output_path, output_path, project_name, target, necessity)

    logger.info(f"项目功能点拆分表已生成: {saved_path} ({len(items)} 个功能过程)")

    cfp_total = sum(item.total_cfp() for item in items)

    if md_dir:
        write_cfp_sum(md_dir, cfp_total)

    return saved_path
