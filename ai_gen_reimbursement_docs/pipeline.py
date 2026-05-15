"""from-excel 管道 —— CLI 和 Web UI 共享的执行编排。

抽取自 main.py 的 --gen-* 逻辑，不依赖 CLI 参数解析或环境变量。
"""

import logging
import os
import re
import shutil
from dataclasses import dataclass, field

from ai_gen_reimbursement_docs.config_utils import (
    load_business_config, load_enable_ai_fill_meta, load_spec_remind_update_toc,
    load_out_templates,
)
from ai_gen_reimbursement_docs.excel_source import (
    generate_md_files, verify_module_tree_stats
)
from ai_gen_reimbursement_docs.excel_writer import generate_cosmic_xlsx_from_md, write_environment_sheet
from ai_gen_reimbursement_docs.gen_spec import (
    generate_spec_docx_from_md, ai_fill_spec_md, init_spec_template_md, parse_meta_md
)
from ai_gen_reimbursement_docs.gen_xlsx import (
    generate_fpa_xlsx_from_md, generate_list_xlsx_from_md,
    init_fpa_template_md, ai_fill_fpa_md,
)
from ai_gen_reimbursement_docs.md_handler import (
    export_empty_md, parse_md_to_items, fill_md_with_ai,
)

logger = logging.getLogger('ai_gen_reimbursement_docs.pipeline')

VALID_MODES = {"gen-all", "gen-basedata", "gen-fpa", "gen-cosmic", "gen-list", "gen-spec"}


@dataclass
class PipelineResult:
    """管道执行结果，各字段在对应步骤完成后填充。"""
    tree_md: str = ""
    meta_md: str = ""
    fpa_xlsx: str = ""
    cosmic_xlsx: str = ""
    require_xlsx: str = ""
    spec_docx: str = ""
    cfp_total: float = 0.0
    fpa_reduced: float = 0.0
    errors: list[str] = field(default_factory=list)


def run_pipeline(
    *,
    mode: str,
    file_path: str,
    output_dir: str,
    api_key: str = "",
    model: str = "",
    base_url: str = "",
    project_name: str = "",
    templates: dict[str, str] | None = None,
) -> PipelineResult:
    """from-excel 管道总入口。

    参数全部 keyword-only，调用方（CLI / Web）各自准备好参数后传入。

    Args:
        mode: "gen-all" | "gen-basedata" | "gen-fpa" | "gen-cosmic" | "gen-list" | "gen-spec"
        file_path: 输入 Excel 路径（功能清单）
        output_dir: 产物输出目录（自动创建）
        api_key: Anthropic API Key
        model: 模型名
        base_url: API 端点
        project_name: 项目名，为空时从 Excel 自动读取
        templates: {"fpa": path, "cosmic": path, "list": path, "spec": path}

    Returns:
        PipelineResult：各产物路径和统计值
    """
    # 校验
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"输入文件不存在: {file_path}")
    if mode not in VALID_MODES:
        raise ValueError(f"未知模式: {mode}，支持: {', '.join(sorted(VALID_MODES))}")

    # 准备目录
    os.makedirs(output_dir, exist_ok=True)
    doc_dir = os.path.join(output_dir, 'cosmic文档')
    md_dir = os.path.join(output_dir, 'md')
    os.makedirs(doc_dir, exist_ok=True)
    os.makedirs(md_dir, exist_ok=True)

    # 路径常量（中间文件）
    tree_md = os.path.join(md_dir, 'gen-basedata-功能清单-模块树.md')
    meta_md_tpl = os.path.join(md_dir, 'gen-basedata-录入文档元数据-模板.md')
    meta_filled_md = os.path.join(md_dir, 'gen-basedata-AI填充-录入文档元数据.md')
    fpa_sum_md = os.path.join(md_dir, 'gen-fpa-FPA工作量-总和.md')

    # 项目名称
    if not project_name:
        project_name = read_project_name_from_excel(file_path)
    if not project_name:
        from ai_gen_reimbursement_docs.main import read_project_name
        project_name = read_project_name(meta_md_tpl) if os.path.exists(meta_md_tpl) else ""
    if not project_name:
        project_name = "products"

    # 模板解析（优先级：传入 > Sheet 8 > 默认 data/templates/）
    templates_dict = _resolve_templates(file_path, templates)

    result = PipelineResult()

    # 产物文件路径（初始默认值，后续由 _resolve_output_filename 覆盖）
    _default_fpa = os.path.join(output_dir, 'FPA工作量评估.xlsx')
    _default_cosmic = os.path.join(doc_dir, '项目功能点拆分表.xlsx')
    _default_require = os.path.join(doc_dir, '项目需求清单.xlsx')
    _default_spec = os.path.join(doc_dir, '项目需求说明书.docx')

    # 确保基础数据存在，以便读取元数据中的自定义文件名
    _ensure_basedata_impl(file_path, md_dir, tree_md, meta_md_tpl)
    _fill_meta_if_needed(meta_md_tpl, meta_filled_md, tree_md, api_key, model, base_url)
    _current_meta = meta_filled_md if os.path.exists(meta_filled_md) else meta_md_tpl

    # 从元数据解析输出文件名（Excel Sheet 中配置的「文件名」字段）
    fpa_xlsx = _resolve_output_filename(_current_meta, '3、FPA工作量评估-元数据录入',
                                         _default_fpa, output_dir)
    cosmic_xlsx = _resolve_output_filename(_current_meta, '6、项目功能点拆分表-元数据录入',
                                            _default_cosmic, doc_dir)
    require_xlsx = _resolve_output_filename(_current_meta, '7、项目需求清单-元数据录入',
                                             _default_require, doc_dir)
    spec_docx = _resolve_output_filename(_current_meta, '4、项目需求说明书-元数据录入',
                                          _default_spec, doc_dir)

    # ── 模式分发 ──
    if mode == "gen-all":
        return _generate_all(
            file_path, output_dir, doc_dir, md_dir,
            tree_md, meta_md_tpl, meta_filled_md, fpa_sum_md,
            fpa_xlsx, cosmic_xlsx, require_xlsx, spec_docx,
            templates_dict, api_key, model, base_url, project_name, result
        )

    if mode == "gen-basedata":
        result.tree_md = tree_md
        result.meta_md = _current_meta
        return result

    # 其余模式：基础数据已就绪，直接用 _current_meta
    meta_md = _current_meta

    if mode == "gen-fpa":
        return _generate_fpa(
            file_path, output_dir, md_dir, tree_md, meta_md, fpa_sum_md, fpa_xlsx,
            templates_dict, api_key, model, base_url, result
        )

    if mode == "gen-cosmic":
        return _generate_cosmic(
            file_path, md_dir, tree_md, meta_md, fpa_sum_md, doc_dir, cosmic_xlsx,
            templates_dict, api_key, model, base_url, project_name, result
        )

    if mode == "gen-list":
        return _generate_list(
            md_dir, tree_md, meta_md, fpa_sum_md, doc_dir, require_xlsx,
            templates_dict, result
        )

    if mode == "gen-spec":
        return _generate_spec(
            file_path, md_dir, tree_md, meta_md, meta_md_tpl, meta_filled_md,
            doc_dir, spec_docx, templates_dict, api_key, model, base_url, result
        )

    return result


# ═══════════════════════════════════════════════════════════════
#  内部辅助
# ═══════════════════════════════════════════════════════════════

def _resolve_templates(file_path: str, cli_templates: dict | None) -> dict:
    """解析模板路径，优先级：CLI 参数 > 配置文件 > data/templates/ 默认。"""
    from ai_gen_reimbursement_docs.main import project_root

    cfg_templates = load_out_templates()
    templates = {}

    for key, config_name, default_filename in [
        ('fpa',    'FPA工作量评估-模板',     'FPA工作量评估-输出模板.xlsx'),
        ('cosmic', '项目功能点拆分表-模板',   '项目功能点拆分表-输出模板.xlsx'),
        ('list',   '项目需求清单-模板',       '项目需求清单-输出模板.xlsx'),
        ('spec',   '项目需求说明书-模板',     '项目需求说明书-输出模板.docx'),
    ]:
        # 1. CLI 参数（最高优先级）
        if cli_templates and key in cli_templates and cli_templates[key]:
            path = cli_templates[key]
            if os.path.exists(path):
                templates[key] = path
                continue

        # 2. 配置文件（system_config.yaml → out_templates）
        cfg_path = cfg_templates.get(config_name, '')
        if cfg_path:
            if not os.path.isabs(cfg_path):
                cfg_path = os.path.join(project_root(), cfg_path)
            if os.path.exists(cfg_path):
                templates[key] = cfg_path
                continue

        # 3. 默认 data/out_templates/
        default = os.path.join(project_root(), 'data', 'out_templates',
                               default_filename)
        if os.path.exists(default):
            templates[key] = default

    # 检查缺失的模板，给出明确提示
    missing = [k for k in ['fpa', 'cosmic', 'list', 'spec'] if not templates.get(k)]
    if missing:
        _names = {'fpa': 'FPA工作量评估', 'cosmic': '项目功能点拆分表',
                   'list': '项目需求清单', 'spec': '项目需求说明书'}
        logger.error(
            f"未找到 {len(missing)} 个输出模板: {', '.join(_names[k] for k in missing)}。"
            f"请在 ~/.ai-gen-reimbursement-docs/system_config.yaml 中配置 out_templates，"
            f"或通过 CLI --{missing[0]}-out-template 参数指定路径。"
        )
    return templates


def _ensure_basedata_impl(file_path: str, md_dir: str,
                          tree_md: str, meta_md_tpl: str) -> None:
    """确保 gen-basedata-*.md 数据源文件存在。"""
    needs_md = not (os.path.exists(meta_md_tpl) and os.path.exists(tree_md))
    if needs_md:
        logger.info("第1步: 生成数据源中间文件...")
        generate_md_files(file_path, md_dir)
    verify_module_tree_stats(tree_md, meta_md_tpl)


def _fill_meta_if_needed(meta_md_tpl: str, meta_filled_md: str, tree_md: str,
                         api_key: str, model: str, base_url: str) -> None:
    """AI 填充元数据（如果尚未填充）。"""
    if not api_key or os.path.exists(meta_filled_md):
        return
    from ai_gen_reimbursement_docs.main import ai_fill_meta_md
    if load_enable_ai_fill_meta():
        logger.info("AI 填充文档元数据...")
        ai_fill_meta_md(meta_md_tpl, meta_filled_md, api_key, model, base_url, tree_md=tree_md)
    else:
        logger.info("enable_ai_fill_meta=false，跳过 AI 填充，直接复制模板")
        shutil.copy2(meta_md_tpl, meta_filled_md)


def _resolve_output_filename(meta_md_path: str, sheet_name: str,
                             default_path: str, target_dir: str) -> str:
    """从元数据 MD 中读取自定义输出文件名。

    Excel Sheet 各段含「文件名」字段，支持 ${工单编号}、${工单标题} 等占位符。
    若 meta_md 未配置或解析失败，回退到 default_path。
    """
    if not os.path.exists(meta_md_path):
        return default_path
    with open(meta_md_path, encoding='utf-8') as f:
        content = f.read()

    # 定位 sheet 段
    section = re.search(
        rf'##\s*{re.escape(sheet_name)}.*?(?=##|\Z)', content, re.DOTALL
    )
    if not section:
        return default_path

    # 提取「文件名」字段
    m = re.search(r'\|\s*文件名\s*\|\s*(.+?)\s*(?:\||$)', section.group())
    if not m:
        return default_path

    name = m.group(1).strip()

    # 占位符替换
    for placeholder, key in [
        ('${工单编号}', '工单编号'),
        ('${工单名称}', '工单标题'),
        ('${工单标题}', '工单标题'),
        ('${子系统（模块）}', '子系统（模块）'),
    ]:
        pm = re.search(rf'{key}\s*\|\s*(.+?)(?:\s*\||$)', content)
        if pm:
            name = name.replace(placeholder, pm.group(1).strip())

    return os.path.join(target_dir, name)


def read_project_name_from_excel(file_path: str) -> str:
    """从 Excel 的「1、工单需求-元数据录入」sheet 读取工单标题。"""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(file_path, data_only=True)
        ws = wb['1、工单需求-元数据录入']
        for row in ws.iter_rows(min_row=2, values_only=True):
            if str(row[0]).strip() == '工单标题':
                name = str(row[1]).strip() if row[1] else ''
                wb.close()
                return name
        wb.close()
    except Exception:
        pass
    return ""


# ═══════════════════════════════════════════════════════════════
#  各子模式实现
# ═══════════════════════════════════════════════════════════════

def _check_template(templates_dict: dict, key: str, name: str):
    """检查模板路径，为空时抛出可读的错误。"""
    path = templates_dict.get(key, '')
    if not path:
        raise FileNotFoundError(
            f"未找到「{name}」模板。"
            f"请在 ~/.ai-gen-reimbursement-docs/system_config.yaml 的 out_templates 中配置，"
            f"或通过 CLI 参数指定。"
        )
    if not os.path.exists(path):
        raise FileNotFoundError(f"「{name}」模板文件不存在: {path}")
    return path


def _generate_fpa(file_path, output_dir, md_dir, tree_md, meta_md,
             fpa_sum_md, fpa_xlsx, templates_dict, api_key, model, base_url, result):
    """第1步：FPA 工作量评估。"""
    logger.info("第1步: 生成 FPA 工作量评估...")
    fpa_src = _check_template(templates_dict, 'fpa', 'FPA工作量评估')

    fpa_md = os.path.join(md_dir, 'gen-fpa-FPA-模板.md')
    fpa_filled_md = os.path.join(md_dir, 'gen-fpa-AI填充-FPA.md')
    init_fpa_template_md(tree_md, meta_md, fpa_md, summary_md_path=fpa_sum_md)

    if api_key:
        logger.info("AI 填充 FPA 数据...")
        shutil.copy2(fpa_md, fpa_filled_md)
        ai_fill_fpa_md(fpa_filled_md, meta_md,
                       template_path=fpa_src,
                       api_key=api_key, model=model, base_url=base_url)
    else:
        fpa_filled_md = fpa_md

    generate_fpa_xlsx_from_md(fpa_filled_md, meta_md, fpa_src, fpa_xlsx)

    from ai_gen_reimbursement_docs.main import read_md_value
    result.fpa_reduced = read_md_value(fpa_sum_md, r'FPA工作量（人/天）[：:]\s*([\d.]+)') or 0.0
    result.fpa_xlsx = fpa_xlsx
    logger.info(f"FPA工作量评估已生成: {fpa_xlsx}")
    return result


def _generate_cosmic(file_path, md_dir, tree_md, meta_md, fpa_sum_md,
                doc_dir, cosmic_xlsx, templates_dict, api_key, model, base_url,
                project_name, result):
    """第2步：COSMIC 功能点拆分表。"""
    logger.info("生成 项目功能点拆分表...")

    from ai_gen_reimbursement_docs.main import (
        build_modules_from_tree_md, resolve_fpa_sum, read_project_name,
        write_cfp_sum,
    )
    from ai_gen_reimbursement_docs.cosmic_llm import load_user_config_from_meta

    cosmic_src = _check_template(templates_dict, 'cosmic', '项目功能点拆分表')

    modules = build_modules_from_tree_md(tree_md)
    project = read_project_name(meta_md) or (modules[0].name if modules else "项目")

    resolve_fpa_sum(fpa_sum_md)

    init_md_path = os.path.join(md_dir, 'gen-cosmic-cosmic模板.md')
    filled_md_path = os.path.join(md_dir, 'gen-cosmic-AI填充cosmic.md')
    export_empty_md(modules, project, init_md_path)

    if api_key:
        shutil.copy2(init_md_path, filled_md_path)
        _user_cfg = load_user_config_from_meta(meta_md)
        fill_md_with_ai(filled_md_path, modules, project, api_key, model, base_url, **_user_cfg)
        items = parse_md_to_items(filled_md_path)
        if items:
            _meta = parse_meta_md(meta_md)
            generate_cosmic_xlsx_from_md(cosmic_src, cosmic_xlsx, items, meta=_meta)
            result.cfp_total = sum(item.total_cfp() for item in items)
            write_cfp_sum(md_dir, result.cfp_total)
            _target = _meta.get("建设目标", "")
            _necessity = _meta.get("建设必要性", "")
            if _target or _necessity:
                write_environment_sheet(cosmic_xlsx, cosmic_xlsx, project_name, _target, _necessity)
                logger.info("环境图 sheet 已更新")
            logger.info(f"CFP 总和: {result.cfp_total}")
    else:
        logger.warning("未设置 API Key，无法生成 COSMIC 拆分数据")

    result.cosmic_xlsx = cosmic_xlsx
    return result


def _generate_list(md_dir, tree_md, meta_md, fpa_sum_md,
              doc_dir, require_xlsx, templates_dict, result):
    """第3步：需求清单。"""
    logger.info("生成 项目需求清单...")
    from ai_gen_reimbursement_docs.main import prompt_list_values
    require_src = _check_template(templates_dict, 'list', '项目需求清单')

    cfp_val, fpa_val = prompt_list_values(fpa_sum_md)
    generate_list_xlsx_from_md(meta_md, tree_md, require_src, require_xlsx,
                               cfp_total=cfp_val, fpa_reduced=fpa_val)
    result.require_xlsx = require_xlsx
    logger.info(f"项目需求清单已生成: {require_xlsx}")
    return result


def _generate_spec(file_path, md_dir, tree_md, meta_md, meta_md_tpl, meta_filled_md,
              doc_dir, spec_docx, templates_dict, api_key, model, base_url, result):
    """需求说明书（无固定顺序依赖）。"""
    logger.info("生成 项目需求说明书...")
    spec_src = _check_template(templates_dict, 'spec', '项目需求说明书')

    # 确保元数据已填充
    if api_key and not os.path.exists(meta_filled_md):
        if load_enable_ai_fill_meta():
            from ai_gen_reimbursement_docs.main import ai_fill_meta_md
            ai_fill_meta_md(meta_md_tpl, meta_filled_md, api_key, model, base_url, tree_md=tree_md)
    if os.path.exists(meta_filled_md):
        meta_md = meta_filled_md

    spec_md = os.path.join(md_dir, 'gen-spec-spec-功能需求章节-模板.md')
    spec_filled_md = os.path.join(md_dir, 'gen-spec-AI填充-spec-功能需求章节.md')
    if not os.path.exists(spec_filled_md):
        init_spec_template_md(tree_md, meta_md, spec_md)
        if api_key:
            ai_fill_spec_md(spec_md, spec_filled_md, api_key, model, base_url)
        else:
            shutil.copy2(spec_md, spec_filled_md)

    filled = spec_filled_md if os.path.exists(spec_filled_md) else ""

    # 需求说明书文件名提醒
    from ai_gen_reimbursement_docs.main import project_root
    if load_spec_remind_update_toc():
        _doc_dir, _doc_name = os.path.split(spec_docx)
        if not _doc_name.startswith("【提醒】请手动更新整个目录"):
            spec_docx = os.path.join(_doc_dir, f"【提醒】请手动更新整个目录 {_doc_name}")

    generate_spec_docx_from_md(spec_src, spec_docx, meta_md, tree_md, filled_md_path=filled)
    result.spec_docx = spec_docx
    logger.info(f"项目需求说明书已生成: {spec_docx}")
    return result


def _generate_all(file_path, output_dir, doc_dir, md_dir,
             tree_md, meta_md_tpl, meta_filled_md, fpa_sum_md,
             fpa_xlsx, cosmic_xlsx, require_xlsx, spec_docx,
             templates_dict, api_key, model, base_url, project_name, result):
    """全流程：base → fpa → spec → cosmic → list（按现有依赖顺序）。"""
    logger.info("全流程模式：按依赖顺序执行...")

    from ai_gen_reimbursement_docs.main import (
        build_modules_from_tree_md, read_project_name, resolve_fpa_sum,
        read_md_value, write_cfp_sum, ai_fill_meta_md,
    )
    from ai_gen_reimbursement_docs.cosmic_llm import load_user_config_from_meta

    # 入口检查所有模板
    fpa_src = _check_template(templates_dict, 'fpa', 'FPA工作量评估')
    cosmic_src = _check_template(templates_dict, 'cosmic', '项目功能点拆分表')
    require_src = _check_template(templates_dict, 'list', '项目需求清单')
    spec_src = _check_template(templates_dict, 'spec', '项目需求说明书')

    # Step 0: 基础数据 + 元数据填充
    _ensure_basedata_impl(file_path, md_dir, tree_md, meta_md_tpl)
    if api_key and not os.path.exists(meta_filled_md):
        if load_enable_ai_fill_meta():
            logger.info("第0步: AI 填充文档元数据...")
            ai_fill_meta_md(meta_md_tpl, meta_filled_md, api_key, model, base_url, tree_md=tree_md)
        else:
            shutil.copy2(meta_md_tpl, meta_filled_md)
    meta_md = meta_filled_md if os.path.exists(meta_filled_md) else meta_md_tpl

    # Step 1: FPA
    fpa_md = os.path.join(md_dir, 'gen-fpa-FPA-模板.md')
    fpa_filled_md = os.path.join(md_dir, 'gen-fpa-AI填充-FPA.md')
    logger.info("第1步：FPA...")
    init_fpa_template_md(tree_md, meta_md, fpa_md, summary_md_path=fpa_sum_md)
    if api_key:
        shutil.copy2(fpa_md, fpa_filled_md)
        ai_fill_fpa_md(fpa_filled_md, meta_md, template_path=fpa_src,
                       api_key=api_key, model=model, base_url=base_url)
    fpa_src_md = fpa_filled_md if api_key else fpa_md
    generate_fpa_xlsx_from_md(fpa_src_md, meta_md, fpa_src, fpa_xlsx)
    result.fpa_xlsx = fpa_xlsx
    result.fpa_reduced = read_md_value(fpa_sum_md, r'FPA工作量（人/天）[：:]\s*([\d.]+)') or 0.0

    # Step 2: 需求说明书
    logger.info("第2步：生成 项目需求说明书...")
    spec_md = os.path.join(md_dir, 'gen-spec-spec-功能需求章节-模板.md')
    spec_filled_md = os.path.join(md_dir, 'gen-spec-AI填充-spec-功能需求章节.md')
    if not os.path.exists(spec_filled_md):
        init_spec_template_md(tree_md, meta_md, spec_md)
        if api_key:
            ai_fill_spec_md(spec_md, spec_filled_md, api_key, model, base_url)
        else:
            shutil.copy2(spec_md, spec_filled_md)
    filled = spec_filled_md if os.path.exists(spec_filled_md) else ""

    # 需求说明书文件名提醒
    if load_spec_remind_update_toc():
        _doc_dir, _doc_name = os.path.split(spec_docx)
        if not _doc_name.startswith("【提醒】请手动更新整个目录"):
            spec_docx = os.path.join(_doc_dir, f"【提醒】请手动更新整个目录 {_doc_name}")

    generate_spec_docx_from_md(spec_src, spec_docx, meta_md, tree_md, filled_md_path=filled)
    result.spec_docx = spec_docx

    # Step 3: COSMIC
    logger.info("第3步：生成 项目功能点拆分表...")
    modules = build_modules_from_tree_md(tree_md)
    project = read_project_name(meta_md) or (modules[0].name if modules else "项目")
    init_md_path = os.path.join(md_dir, 'gen-cosmic-cosmic模板.md')
    filled_md_path = os.path.join(md_dir, 'gen-cosmic-AI填充cosmic.md')
    export_empty_md(modules, project, init_md_path)
    if api_key:
        shutil.copy2(init_md_path, filled_md_path)
        _user_cfg = load_user_config_from_meta(meta_md)
        fill_md_with_ai(filled_md_path, modules, project, api_key, model, base_url, **_user_cfg)
        items = parse_md_to_items(filled_md_path)
        if items:
            _meta = parse_meta_md(meta_md)
            generate_cosmic_xlsx_from_md(cosmic_src, cosmic_xlsx, items, meta=_meta)
            result.cfp_total = sum(item.total_cfp() for item in items)
            write_cfp_sum(md_dir, result.cfp_total)
            _target = _meta.get("建设目标", "")
            _necessity = _meta.get("建设必要性", "")
            if _target or _necessity:
                write_environment_sheet(cosmic_xlsx, cosmic_xlsx, project_name or project, _target, _necessity)
    result.cosmic_xlsx = cosmic_xlsx

    # Step 4: 需求清单
    logger.info("第4步：生成 项目需求清单...")
    cfp_total = read_md_value(os.path.join(md_dir, 'gen-cosmic-CFP-总和.md'), r'CFP 总和[：:]\s*([\d.]+)') or 0
    generate_list_xlsx_from_md(meta_md, tree_md, require_src, require_xlsx,
                               cfp_total=cfp_total, fpa_reduced=result.fpa_reduced)
    result.require_xlsx = require_xlsx

    logger.info("全流程完成")
    return result
