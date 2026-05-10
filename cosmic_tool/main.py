"""COSMIC 功能点拆分工具 - CLI入口

推荐工作流（MD中间件模式）:
  0. python -m cosmic_tool.main --docx 需求书.docx --init-md 需求书_拆分表.md   (含原文转MD)
  1. python -m cosmic_tool.main --fill-md 需求书_拆分表.md
     (编辑拆分表.md 人工审核修正)
  2. python -m cosmic_tool.main --md 需求书_拆分表.md --template 模板.xlsx --output 结果.xlsx

快捷模式（一键全流程）:
  python -m cosmic_tool.main --docx "需求书.docx" --template "模板.xlsx" --output "结果.xlsx" --all

一键直出（跳过MD中间文件）:
  python -m cosmic_tool.main --docx 需求书.docx --template 模板.xlsx --output 结果.xlsx

批量处理Word文件:
  python -m cosmic_tool.main --docx-all
"""

import argparse
import logging
import os
import shutil
import sys
from datetime import datetime

from cosmic_tool.docx_to_md import convert_to_md, build_modules_from_md, get_project_name_from_md
from cosmic_tool.docx_parser import build_module_tree, ai_build_module_tree, print_tree, get_project_name
from cosmic_tool.models import FunctionModule
from cosmic_tool.cosmic_llm import generate_cosmic_items
from cosmic_tool.excel_writer import write_to_template
from cosmic_tool.config_utils import load_api_key, load_base_url, load_model_name, load_business_config
from cosmic_tool.md_handler import (
    export_empty_md,
    export_filled_md,
    parse_md_to_items,
    fill_md_with_ai,
)
from cosmic_tool.excel_source import generate_md_files, read_fpa_xlsx_sum, read_template_config, verify_module_tree_stats
from cosmic_tool.gen_spec import generate_spec, export_spec_template_md, fill_spec_md
from cosmic_tool.gen_xlsx import generate_fpa_xlsx_from_md, generate_require_xlsx
from cosmic_tool.gen_xlsx import init_fpa_template_md, ai_fill_fpa_md

# 启动时自动清理 cosmic_tool 自身的字节码缓存，避免代码修改后缓存过期问题
_pycache = os.path.join(os.path.dirname(__file__), '__pycache__')
if os.path.isdir(_pycache):
    shutil.rmtree(_pycache, ignore_errors=True)


def _init_global_logging():
    """初始化全局日志：项目根目录 log/（控制台 + 总日志 + 运行日志）"""
    if getattr(sys, 'frozen', False):
        log_dir = os.path.join(os.path.expanduser('~'), '.cosmic-tool', 'log')
    else:
        log_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 'log'
        )
    os.makedirs(log_dir, exist_ok=True)

    main_log = os.path.join(log_dir, 'cosmic_tool.log')
    run_stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    run_log = os.path.join(log_dir, f'global_run_{run_stamp}.log')

    logger = logging.getLogger('cosmic_tool')
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 全局总日志（持续追加，永不删除）
    main_log = os.path.join(log_dir, 'global_cosmic_tool.log')
    fh = logging.FileHandler(main_log, encoding='utf-8', mode='a')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    fh._is_global = True
    logger.addHandler(fh)

    # 本次运行日志
    rh = logging.FileHandler(run_log, encoding='utf-8', mode='w')
    rh.setLevel(logging.DEBUG)
    rh.setFormatter(fmt)
    rh._is_global = True
    logger.addHandler(rh)

    # 控制台
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter('%(message)s'))
    ch._is_global = True
    logger.addHandler(ch)

    return logger, run_log


def setup_logging(log_dir: str, docx_name: str = ""):
    """添加 per-docx 日志处理器（保留全局日志）。"""
    os.makedirs(log_dir, exist_ok=True)

    prefix = f"{docx_name}_" if docx_name else ""
    main_log = os.path.join(log_dir, f'{prefix}cosmic_tool.log')
    run_stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    run_log = os.path.join(log_dir, f'{prefix}run_{run_stamp}.log')

    logger = logging.getLogger('cosmic_tool')

    fmt = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 添加 per-docx 日志（不删除全局处理器）
    fh = logging.FileHandler(main_log, encoding='utf-8', mode='a')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    rh = logging.FileHandler(run_log, encoding='utf-8', mode='w')
    rh.setLevel(logging.DEBUG)
    rh.setFormatter(fmt)
    logger.addHandler(rh)

    return logger, run_log


logger, _run_log_path = _init_global_logging()


def _get_version() -> str:
    """Read version from pyproject.toml (single source of truth)."""
    import tomllib
    import re
    try:
        toml_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'pyproject.toml')
        with open(toml_path, 'rb') as f:
            return tomllib.load(f)['project']['version']
    except Exception:
        return "unknown"


def _setup_docx_logging(docx_path: str) -> str:
    """Set up per-docx log directory: {docx_name}/log/. Returns log_dir."""
    base_name = os.path.splitext(os.path.basename(docx_path))[0]
    log_dir = os.path.join(os.path.abspath(base_name), 'log')
    os.makedirs(log_dir, exist_ok=True)
    setup_logging(log_dir, base_name)
    os.environ['COSMIC_LOG_DIR'] = log_dir
    return log_dir


def _section(title: str):
    """Print a section header to both console and log."""
    sep = "=" * 60
    logger.info(sep)
    logger.info(title)
    logger.info(sep)
    logger.debug("--- section start ---")


def _build_modules(docx_path: str, use_ai: bool,
                   api_key: str = "", model: str = "",
                   base_url: str = "",
                   mapping_name: str = "",
                   chapter_detection: str = "") -> list[FunctionModule]:
    """Build module tree from docx; fall back to AI if configured."""
    modules = build_module_tree(docx_path, mapping_name=mapping_name,
                                 chapter_detection=chapter_detection)
    _verify_against_json(modules, docx_path)

    l1 = [m for m in modules if m.level == 1]
    l2 = [m for m in modules if m.level == 2]
    l3 = [m for m in modules if m.level == 3]
    l3_parents_valid = all(
        not m.parent or any(p.name == m.parent for p in l2) or any(gp.name == m.parent for gp in l1)
        for m in l3
    )
    tree_ok = len(l1) > 0 and len(l3) > 0 and l3_parents_valid

    if not tree_ok and (use_ai or load_business_config().get('parse_docx_by_ai', False)):
        logger.warning(f"硬编码解析层级不完整（L1:{len(l1)} L2:{len(l2)} L3:{len(l3)}），尝试AI解析...")
        modules = ai_build_module_tree(
            docx_path=docx_path,
            api_key=api_key or None,
            model=model or "deepseek-v4-flash",
            base_url=base_url or None,
        )
    elif tree_ok and (use_ai or load_business_config().get('parse_docx_by_ai', False)):
        logger.info(f"硬编码解析层级完整（L1:{len(l1)} L2:{len(l2)} L3:{len(l3)}），跳过AI解析")
    return modules


def _build_modules_from_md(md_path: str, docx_path: str = "",
                            mapping_name: str = "",
                            chapter_detection: str = "") -> list[FunctionModule]:
    """Build module tree from docx. Falls back to Markdown if no docx."""
    if docx_path:
        from cosmic_tool.docx_parser import build_module_tree
        modules = build_module_tree(docx_path, mapping_name=mapping_name,
                                    chapter_detection=chapter_detection)
        _verify_against_json(modules, docx_path)
        return modules
    modules = build_modules_from_md(md_path)
    # 标题解析结果可能为空或错误（如把文档标题当作 L1），
    # 检测是否有 L2/L3 层级，无则尝试表格格式解析
    has_hierarchy = any(m.level >= 2 for m in modules)
    if not has_hierarchy:
        table_modules = _build_modules_from_tree_md(md_path)
        if table_modules:
            modules = table_modules
    if not modules:
        logger.warning("Markdown中未解析到模块层次，结果可能为空")
    return modules


def _build_modules_from_tree_md(md_path: str) -> list[FunctionModule]:
    """从功能清单模块树.md 的表格格式构建 FunctionModule 列表。

    表格列：入口 | 一级模块 | 二级模块 | 三级模块 | ... | 功能过程 | ...
    自动去重并构建 L1→L2→L3 层级，功能过程作为 L3 的 children。
    """
    from cosmic_tool.md_table import parse_md_table_row

    rows: list[dict] = []
    with open(md_path, encoding='utf-8') as f:
        in_table = False
        for line in f:
            if "| 入口 | 一级模块" in line:
                in_table = True
                continue
            if "|------" in line and in_table:
                continue
            if in_table:
                cells = parse_md_table_row(line, min_cols=9)
                if cells is not None:
                    rows.append({
                        "入口": cells[0],
                        "一级模块": cells[1],
                        "二级模块": cells[2],
                        "三级模块": cells[3],
                        "客户端类型": cells[4],
                        "三级模块整体功能描述": cells[5],
                        "功能过程": cells[6],
                        "功能过程类型": cells[7],
                        "功能过程描述": cells[8],
                    })

    if not rows:
        return []

    modules: list[FunctionModule] = []
    seen_l1: set[str] = set()
    seen_l2: dict[str, set[str]] = {}  # l1 → set of l2 names
    seen_l3: dict[str, set[str]] = {}  # l2 → set of l3 names
    l3_desc: dict[str, str] = {}       # l3 name → description
    l3_procs: dict[str, set[str]] = {} # l3 name → set of process names

    for r in rows:
        l1 = r["一级模块"]
        l2 = r["二级模块"]
        l3 = r["三级模块"]
        proc = r["功能过程"]
        desc = r["三级模块整体功能描述"]

        if l1 not in seen_l1:
            seen_l1.add(l1)
            modules.append(FunctionModule(name=l1, level=1))
        if l1 not in seen_l2:
            seen_l2[l1] = set()
        if l2 and l2 not in seen_l2[l1]:
            seen_l2[l1].add(l2)
            modules.append(FunctionModule(name=l2, level=2, parent=l1))
        if l2 not in seen_l3:
            seen_l3[l2] = set()
        if l3 not in seen_l3[l2]:
            seen_l3[l2].add(l3)
            modules.append(FunctionModule(name=l3, level=3, parent=l2,
                                          description=desc))
            l3_desc[l3] = desc
        if l3 not in l3_procs:
            l3_procs[l3] = set()
        if proc:
            l3_procs[l3].add(proc)

    # 将功能过程挂到 L3 的 children，同时去重
    for m in modules:
        if m.level == 3 and m.name in l3_procs:
            m.children = sorted(l3_procs[m.name])

    l3_count = len([m for m in modules if m.level == 3])
    logger.info(f"从表格解析到模块层级: {len(seen_l1)}个L1, "
                f"{sum(len(v) for v in seen_l2.values())}个L2, "
                f"{l3_count}个L3")
    return modules


def _read_project_name(meta_md_path: str) -> str:
    """从文档元数据.md 读取项目名称（工单标题）。"""
    try:
        with open(meta_md_path, encoding='utf-8') as f:
            for line in f:
                if '| 工单标题' in line and '|' in line:
                    parts = [c.strip() for c in line.split('|')]
                    if len(parts) >= 3 and parts[2]:
                        return parts[2]
    except Exception:
        pass
    return ""


def _ensure_basedata(excel_path: str, md_dir: str, meta_md: str, tree_md: str,
                     meta_md_tpl: str = "") -> None:
    """确保数据源中间文件存在（功能清单模块树.md + 文档元数据模板.md）。"""
    tpl = meta_md_tpl or meta_md
    needs_md = not (os.path.exists(tpl) and os.path.exists(tree_md))
    if needs_md:
        logger.info("第1步: 生成功能清单模块树.md 和 文档元数据模板.md...")
        generate_md_files(excel_path, md_dir)
    verify_module_tree_stats(tree_md, tpl)


def _write_fpa_summary(fpa_xlsx_path: str, output_md_path: str) -> None:
    """读取 FPA Excel 核减后工作量列的求和，写入 MD 文件。"""
    total = read_fpa_xlsx_sum(fpa_xlsx_path)
    os.makedirs(os.path.dirname(output_md_path), exist_ok=True)
    with open(output_md_path, 'w', encoding='utf-8') as f:
        f.write("# FPA 核减后工作量\n\n")
        f.write(f"FPA工作量（人/天）: {total}\n")


def _resolve_fpa_sum(fpa_sum_md_path: str) -> float:
    """从 FPA工作量.md 读取值作为默认，提示用户输入FPA核减后工作量。"""
    import re
    md_val = 0.0
    if os.path.exists(fpa_sum_md_path):
        with open(fpa_sum_md_path, encoding='utf-8') as f:
            for line in f:
                m = re.search(r'FPA工作量（人/天）[：:]\s*([\d.]+)', line)
                if m:
                    md_val = float(m.group(1))
                    break

    if md_val > 0:
        print(f"\nFPA工作量: {md_val}。请输入 FPA 核减后的工作量（直接回车使用FPA工作量）: ", end="")
    else:
        print("\n请输入 FPA 核减后的工作量（人/天）: ", end="")

    try:
        inp = input().strip()
        if inp:
            val = float(inp)
            logger.info(f"FPA核减后工作量: {val}（用户输入）")
            return val
    except (EOFError, OSError, ValueError):
        pass

    if md_val > 0:
        logger.info(f"FPA核减后工作量: {md_val}（来自 FPA工作量.md）")
        return md_val

    msg = "未输入 FPA 核减后的工作量，CFP 数量将不受限制"
    logger.warning(msg)
    print(f"\n⚠ {msg}")
    return 0


def _ai_fill_meta_md(src_md: str, dst_md: str, api_key: str, model: str, base_url: str) -> str:
    """读取文档元数据模板.md，AI 填充 #AI生成# 标记，写入 AI填充文档元数据.md。

    处理 #AI生成#（包含 #AI生成-XXX# 格式），跳过 #AI补充#。
    """
    from cosmic_tool.excel_source import strip_ai_marker, replace_placeholders
    from cosmic_tool.md_table import parse_md_table_row

    # 读取元数据模板，收集 project_info / fpa_meta 用于 ${} 替换
    meta_data = {}
    with open(src_md, encoding='utf-8') as f:
        for line in f:
            cells = parse_md_table_row(line, min_cols=2)
            if cells is not None and cells[0]:
                meta_data[cells[0]] = cells[1]

    project_info = {}
    for k, v in meta_data.items():
        key = k.replace("1、工单需求-元数据录入.", "")
        if key in ("工单编号", "工单标题", "工单内容", "总体描述",
                    "建设目标", "建设必要性", "系统概况"):
            project_info[key] = v
    fpa_meta = {}
    for k, v in meta_data.items():
        key = k.replace("3、FPA工作量评估-元数据录入.", "")
        if key in ("子系统（模块）",):
            fpa_meta[key] = v

    # 逐行处理
    with open(src_md, encoding='utf-8') as f:
        lines = f.readlines()

    new_lines = []
    for line in lines:
        cells = parse_md_table_row(line, min_cols=2)
        if cells is not None:
            key, val = cells[0], cells[1]
            if val and ('#AI生成#' in val or '#AI生成-' in val):
                prompt_raw, needs_ai = strip_ai_marker(val)
                if needs_ai:
                    if not prompt_raw:
                        prompt_raw = f"基于{key}"
                    elif '${' in prompt_raw:
                        prompt_raw = replace_placeholders(prompt_raw, project_info, fpa_meta)
                    resp = _call_llm_once(prompt_raw, api_key, model, base_url,
                                          tag=f"meta_{key[:16]}")
                    if resp:
                        new_lines.append(f"| {key} | {resp} |\n")
                        continue
            # #AI补充# 不做处理，原样保留
        new_lines.append(line)

    with open(dst_md, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    return dst_md


def _call_llm_once(prompt: str, api_key: str, model: str, base_url: str,
                   tag: str = "") -> str:
    """单次 LLM 调用，返回文本。保存 prompt 和 response 到日志文件。"""
    if not api_key:
        return ""

    logger.info(f"AI 生成请求 [{tag}] 模型: {model}")

    # 保存提示词
    ts = ""
    try:
        base_log = os.environ.get('COSMIC_LOG_DIR', '') or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), '..', 'log'
        )
        prompt_dir = os.path.join(base_log, 'ai_prompts')
        os.makedirs(prompt_dir, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        with open(os.path.join(prompt_dir, f'{ts}_{tag}_prompt.txt'), 'w', encoding='utf-8') as f:
            f.write(f"# AI Prompt: {tag}\n")
            f.write(f"# Model: {model}\n")
            f.write(f"# Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(prompt)
    except Exception as e:
        logger.debug(f"保存提示词失败: {e}")

    from cosmic_tool.config_utils import load_max_tokens, load_ai_system_prompt
    max_tokens = load_max_tokens()
    system_prompt = load_ai_system_prompt("metadata_gen")

    try:
        import anthropic
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        client = anthropic.Anthropic(**client_kwargs)
        msg = client.messages.create(
            model=model or "deepseek-v4-flash",
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )
        resp = ""
        for block in msg.content:
            if hasattr(block, 'text'):
                resp = block.text.strip()
                break

        # 保存响应
        try:
            resp_dir = os.path.join(base_log, 'ai_responses')
            os.makedirs(resp_dir, exist_ok=True)
            with open(os.path.join(resp_dir, f'{ts}_{tag}_response.txt'), 'w', encoding='utf-8') as f:
                f.write(f"# AI Response: {tag}\n")
                f.write(f"# Model: {model}\n")
                f.write(f"# Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write(resp)
        except Exception as e:
            logger.debug(f"保存响应失败: {e}")

        logger.info(f"AI 生成完成 [{tag}] 长度: {len(resp)} 字")
        return resp
    except Exception as e:
        logger.warning(f"AI 调用失败 [{tag}]: {e}")
        return ""


def _verify_against_json(modules: list, docx_path: str) -> None:
    """Compare parsing result with expected counts from a JSON file."""
    json_path = os.path.splitext(docx_path)[0] + '.json'
    if not os.path.exists(json_path):
        logger.info(f"未找到预期结果文件: [{os.path.basename(json_path)}]，跳过比较")
        return
    try:
        import json
        with open(json_path, 'r', encoding='utf-8') as f:
            expected = json.load(f)
        actual = {
            'L1': len([m for m in modules if m.level == 1]),
            'L2': len([m for m in modules if m.level == 2]),
            'L3': len([m for m in modules if m.level == 3]),
            'proc': sum(len(m.children) for m in modules if m.level == 3),
        }
        diffs = []
        for key in ('L1', 'L2', 'L3', 'proc'):
            exp = expected.get(key)
            if exp is None:
                continue
            act = actual[key]
            if act != exp:
                diffs.append(f"{key}: 预期={exp} 实际={act}")
        if diffs:
            logger.warning(f"解析结果与JSON不一致: {'; '.join(diffs)}")
        else:
            logger.info(f"解析结果同JSON文件一致")
    except Exception as e:
        logger.warning(f"读取JSON比较文件失败: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="COSMIC 功能点拆分工具 - 从需求说明书自动生成功能点拆分表（需指定参数，--docx-all可批量处理Word）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
工作流示例:

  # (推荐) MD中间件模式：docx → MD → 编辑MD → Excel
  python -m cosmic_tool.main --docx 需求书.docx --init-md 需求书_拆分表.md
  python -m cosmic_tool.main --fill-md 需求书_拆分表.md
  python -m cosmic_tool.main --md 需求书_拆分表.md --template 模板.xlsx --output 结果.xlsx

  # (快捷) 一键直出：docx → LLM → Excel
  python -m cosmic_tool.main --docx 需求书.docx --template 模板.xlsx --output 结果.xlsx

  # (快捷) 一键全流程：docx → MD → AI填充 → Excel（含功能清单模块树.md和文档元数据.md）
  python -m cosmic_tool.main --docx "需求书.docx" --template "模板.xlsx" --output "结果.xlsx" --all

  # 仅查看模块树
  python -m cosmic_tool.main --docx 需求书.docx --show-tree

  # 初始化API Key配置
  python -m cosmic_tool.main --init-config

  # 批量处理当前目录下所有Word文件
  python -m cosmic_tool.main --docx-all

  # Excel 功能清单 → 全套交付物
  python -m cosmic_tool.main --from-excel 功能清单.xlsx --gen-all
        """
    )

    # === CLI Arguments ===
    parser.add_argument('--docx', '-d', default='',
                        help='需求说明书 .docx 文件路径')

    parser.add_argument('--init-md', nargs='?', const='', default=None,
                        help='生成拆分表模板MD（含模块结构，数据表为空）；省略路径时从docx自动命名')

    parser.add_argument('--fill-md', nargs='?', const='', default=None,
                        help='AI填充COSMIC数据到模板MD；省略路径时从docx自动命名')

    parser.add_argument('--md', nargs='?', const='', default=None,
                        help='从MD文件生成Excel；省略路径时从docx自动查找')

    parser.add_argument('--template', '-t', default='',
                        help='功能点拆分表 .xlsx 模板文件路径（默认 data/templates/）')

    parser.add_argument('--output', '-o', default='',
                        help='输出 .xlsx 文件路径')

    parser.add_argument('--api-key', '-k', default='',
                        help='API Key（默认从 .env 读取）')

    parser.add_argument('--model', '-m', default='',
                        help='模型名称（默认从 .env 读取，否则 deepseek-v4-flash）')

    parser.add_argument('--show-tree', '-s', action='store_true',
                        help='仅显示模块树结构')

    parser.add_argument('--no-llm', action='store_true',
                        help='跳过AI阶段')

    parser.add_argument('--parse-by-ai', action='store_true',
                        help='使用AI解析模块层级（默认用硬编码解析器）')

    parser.add_argument('--mapping', default='',
                        help='指定层级映射名（来自 ~/.cosmic-tool/docx_parse_mapping_rules.yaml 中的 mapping 名称）')

    parser.add_argument('--chapter-detection', default='',
                        help='指定章节检测配置名（来自 ~/.cosmic-tool/docx_parse_mapping_rules.yaml 中的 章节检测 分组）')

    parser.add_argument('--all', action='store_true',
                        help='一键全流程: docx → MD → AI填充 → Excel')

    parser.add_argument('--docx-all', action='store_true',
                        help='批量处理当前目录下所有Word文件')

    # === Excel 功能清单 → 全套交付物 ===
    parser.add_argument('--from-excel', default='',
                        help='功能清单.xlsx 路径（配合 --gen-* 使用）')

    parser.add_argument('--gen-fpa', action='store_true',
                        help='第1步：从功能清单生成 FPA工作量评估.xlsx')

    parser.add_argument('--gen-cosmic', action='store_true',
                        help='第2步：从功能清单生成 项目功能点拆分表.xlsx（需第1步完成）')

    parser.add_argument('--gen-list', action='store_true',
                        help='第3步：从功能清单生成 项目需求清单.xlsx（需第2步完成）')

    parser.add_argument('--gen-spec', action='store_true',
                        help='从功能清单生成 项目需求说明书.docx（无依赖，可随时执行）')

    parser.add_argument('--gen-basedata', action='store_true',
                        help='第0步：生成功能清单模块树.md 和 文档元数据.md')

    parser.add_argument('--gen-all', action='store_true',
                        help='全流程：按依赖顺序自动执行 --gen-basedata → --gen-fpa → --gen-cosmic → --gen-list')

    parser.add_argument('--output-dir', default='',
                        help='--from-excel 系列命令的输出目录（默认输入文件所在目录）')

    # 模板路径覆盖（优先级: CLI > Excel sheet 8 > data/templates/）
    parser.add_argument('--fpa-template', default='',
                        help='FPA工作量评估 模板路径')
    parser.add_argument('--cosmic-template', default='',
                        help='项目功能点拆分表 模板路径')
    parser.add_argument('--list-template', default='',
                        help='项目需求清单(Requirements List) 模板路径')
    parser.add_argument('--spec-template', default='',
                        help='项目需求说明书(Specification) 模板路径')

    parser.add_argument('--init-config', action='store_true',
                        help='初始化 .env 配置文件')

    parser.add_argument('--log', nargs='?', const='tail', default=None,
                        help='查看日志：--log（末30行），--log full，--log watch，--log open')

    parser.add_argument('--version', '-v', action='store_true',
                        help='显示版本号')

    args = parser.parse_args()
    logger.debug(f"CLI args: {args}")

    # 版本信息
    ver = _get_version()
    logger.info(f"COSMIC 工具 v{ver} — 从需求说明书自动生成功能点拆分表")
    logger.debug(f"版本: v{ver}")

    # 当前配置目录
    from cosmic_tool.config_utils import _config_dir
    logger.info(f"配置文件目录: {_config_dir()}")

    # 配置迁移（新模板键自动追加到用户配置文件）
    from cosmic_tool.config_utils import _migrate_config
    _migrate_config()

    # === Log viewer ===
    if getattr(sys, 'frozen', False):
        log_dir = os.path.join(os.path.expanduser('~'), '.cosmic-tool', 'log')
    else:
        log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'log')
    if args.log:
        if args.log == 'open':
            os.startfile(log_dir)
            return
        # Find latest log file
        log_files = sorted(
            [f for f in os.listdir(log_dir) if f.endswith('.log')],
            reverse=True
        )
        if not log_files:
            logger.error("没有找到日志文件")
            return
        latest = os.path.join(log_dir, log_files[0])
        if args.log == 'watch':
            try:
                os.system(f'tail -f "{latest}"')
            except:
                os.system(f'powershell -command "Get-Content \\"{latest}\\" -Wait"')
            return
        with open(latest, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        if args.log == 'tail':
            lines = lines[-30:]
        print(''.join(lines))
        return

    # === Version ===
    if args.version:
        print(f"cosmic-tool v{_get_version()}")
        return

    # === Init config ===
    if args.init_config:
        config_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config')
        home_cfg = os.path.join(os.path.expanduser('~'), '.cosmic-tool')
        os.makedirs(home_cfg, exist_ok=True)

        # 直接从 .example 复制，保留注释
        pairs = [
            (os.path.join(config_dir, '.env.example'), os.path.join(home_cfg, '.env')),
            (os.path.join(config_dir, 'system_config.yaml.example'), os.path.join(home_cfg, 'system_config.yaml')),
            (os.path.join(config_dir, 'business_rules.yaml.example'), os.path.join(home_cfg, 'business_rules.yaml')),
        ]
        for src, dst in pairs:
            if os.path.exists(dst):
                logger.info(f"已存在，跳过: {dst}")
                continue
            shutil.copy2(src, dst)
            logger.info(f"已创建: {dst}")

        logger.info("请编辑 ~/.cosmic-tool/.env 填入你的 API Key 后使用")
        return
    # === Load config ===
    api_key = args.api_key or load_api_key()
    base_url = load_base_url()
    model = args.model or load_model_name("deepseek-v4-flash")

    if api_key:
        os.environ["ANTHROPIC_API_KEY"] = api_key
    if base_url:
        os.environ["ANTHROPIC_BASE_URL"] = base_url
    logger.debug(f"API Key: {'已设置' if api_key else '未设置'}, 端点: {base_url or '默认'}, 模型: {model}")

    # 记录实际使用的配置值
    from cosmic_tool.config_utils import load_max_tokens, load_business_config, load_cfp_formula
    logger.info(f"配置: MAX_TOKENS={load_max_tokens()}, CFP公式={load_cfp_formula()}")
    biz_cfg = load_business_config()
    logger.info(f"配置: REGENERATE_MD={biz_cfg['regenerate_md']}, ENABLE_AI_GENERATE_COSMIC={biz_cfg['enable_ai_generate_cosmic']}")

    # === Show tree ===
    if args.docx and args.show_tree:
        modules = _build_modules(args.docx, args.parse_by_ai, api_key, model, base_url,
                                  mapping_name=args.mapping, chapter_detection=args.chapter_detection)
        project = get_project_name(args.docx)
        logger.info(f"项目名称: {project}")
        print_tree(modules)
        logger.debug("show-tree completed")
        return

    # === 批量处理模式: 处理当前目录下所有 Word 文件 ===
    if args.docx_all:
        _section("批量处理模式（Word → AI → Excel）")
        import glob
        docx_files = [f for f in glob.glob("*.docx") + glob.glob("*.docm")
                      if not f.startswith("~$")]
        if not docx_files:
            logger.warning("当前目录没有找到 docx 文件")
            return

        total = len(docx_files)
        excel_ok: list[str] = []       # 成功生成 Excel 的 docx
        processed_no_excel: list[str] = []  # 处理了但没生成 Excel
        failed: list[str] = []         # 处理失败的 docx

        # 加载业务配置（是否重新生成各阶段文件等）
        from cosmic_tool.config_utils import load_business_config
        biz_config = load_business_config()
        logger.info(f"  配置: ENABLE_AI_GENERATE_COSMIC={biz_config['enable_ai_generate_cosmic']}, "
                    f"REGENERATE_ALL={biz_config['regenerate_all']}")

        for idx, docx_path in enumerate(docx_files, 1):
            base_name = os.path.splitext(docx_path)[0]
            out_dir = os.path.abspath(base_name)
            md_dir = os.path.join(out_dir, 'md')
            log_dir = os.path.join(out_dir, 'log')

            xlsx_path = _auto_output_path(docx_path)
            out_xlsx = os.path.join(out_dir, os.path.basename(xlsx_path))
            docx_name = os.path.splitext(os.path.basename(docx_path))[0]
            md_raw = os.path.join(md_dir, f'{docx_name}_原文.md')
            md_base = os.path.join(md_dir, f'{docx_name}_拆分表.md')
            md_filled = os.path.join(md_dir, f'{docx_name}_AI填充cosmic.md')

            os.makedirs(md_dir, exist_ok=True)
            os.makedirs(log_dir, exist_ok=True)

            logger.info(f"  [{idx}/{total}] {docx_path}")

            # Reconfigure logging and AI response paths for this docx
            docx_name = os.path.splitext(os.path.basename(docx_path))[0]
            setup_logging(log_dir, docx_name)
            os.environ['COSMIC_LOG_DIR'] = log_dir

            try:
                # --- Stage 0: docx → 原文 Markdown ---
                if os.path.exists(md_raw) and not biz_config['regenerate_md']:
                    logger.info(f"  原文MD已存在，跳过（REGENERATE_MD=false）")
                else:
                    convert_to_md(docx_path, md_raw, args.chapter_detection)
                    logger.info(f"  原文MD已生成: {md_raw}")

                # --- Stage 1: 原文 MD → 生成 COSMIC 模板 ---
                if os.path.exists(md_base) and not biz_config['regenerate_md']:
                    logger.info(f"  模板MD已存在，跳过（REGENERATE_MD=false）")
                    modules = _build_modules_from_md(md_raw, docx_path, args.mapping, args.chapter_detection)
                    project = get_project_name_from_md(md_raw)
                else:
                    modules = _build_modules_from_md(md_raw, docx_path, args.mapping, args.chapter_detection)
                    project = get_project_name_from_md(md_raw)
                    export_empty_md(modules, project, md_base)
                    logger.info(f"  模板MD已生成: {md_base}")

                # --- Stage 2: AI 填充 ---
                if not biz_config['enable_ai_generate_cosmic']:
                    logger.info(f"  AI已禁用（ENABLE_AI_GENERATE_COSMIC=false），跳过填充")
                elif os.path.exists(md_filled) and not biz_config['regenerate_filled']:
                    logger.info(f"  已填充MD已存在，跳过（REGENERATE_FILLED=false）")
                else:
                    if not api_key:
                        raise ValueError("API Key 未设置")
                    shutil.copy2(md_base, md_filled)
                    fill_md_with_ai(md_filled, modules, project, api_key, model, base_url)

                # --- Stage 3: 生成 Excel ---
                if os.path.exists(out_xlsx) and not biz_config['regenerate_excel']:
                    logger.info(f"  Excel已存在，跳过（REGENERATE_EXCEL=false）")
                else:
                    # 优先用已填充的MD，没有则用模板MD
                    md_to_use = md_filled if os.path.exists(md_filled) else md_base
                    items = parse_md_to_items(md_to_use)
                    if items:
                        write_to_template(_default_template_path(), out_xlsx, items)
                        total_cfp = sum(item.total_cfp() for item in items)
                        logger.info(f"  Excel已生成: {out_xlsx} ({len(items)} 过程, {total_cfp} CFP)")
                    else:
                        logger.warning(f"  MD中无数据，跳过Excel生成")

                if os.path.exists(out_xlsx):
                    excel_ok.append(docx_path)
                else:
                    processed_no_excel.append(docx_path)
                logger.info("")  # 分隔空行

            except Exception as e:
                logger.error(f"  ❌ 处理失败: {e}")
                failed.append(docx_path)
                logger.info("")  # 分隔空行

        _section("批量处理完成")
        if excel_ok:
            logger.info("成功:")
            for d in excel_ok:
                logger.info(f"  ✅ {d}")
        if processed_no_excel:
            logger.info("已处理但未生成Excel（如无AI数据、--no-llm等）:")
            for d in processed_no_excel:
                logger.info(f"  ⚠ {d}")
        if failed:
            logger.info("失败:")
            for d in failed:
                logger.info(f"  ❌ {d}")
        return

    # === Mode 1: init-md (docx → empty MD) ===
    if args.init_md is not None:  # "" is auto-name, explicit path is used as-is
        if not args.docx:
            parser.error("--init-md 需要 --docx")
        if not args.init_md:
            args.init_md = _auto_md_path(args.docx, '_拆分表')
        _setup_docx_logging(args.docx)
        # 生成原文MD（与模板MD同目录）
        docx_name = os.path.splitext(os.path.basename(args.docx))[0]
        md_dir = os.path.dirname(args.init_md) or '.'
        raw_md = os.path.join(md_dir, f'{docx_name}_原文.md')
        _section("阶段0: 需求说明书 → 原文Markdown")
        convert_to_md(args.docx, raw_md, args.chapter_detection)
        logger.info(f"  原文MD已生成: {raw_md}")

        _section("阶段1: 原文MD → 生成COSMIC模板")
        modules = _build_modules_from_md(raw_md, args.docx, args.mapping, args.chapter_detection)
        project = get_project_name_from_md(raw_md)
        # Statistics
        l1_count = len([m for m in modules if m.level == 1])
        l2_count = len([m for m in modules if m.level == 2])
        l3_count = len([m for m in modules if m.level == 3])
        proc_count = sum(len(m.children) for m in modules if m.level == 3 and m.children)
        logger.info(f"模块层级: {l1_count} 个一级 / {l2_count} 个二级 / {l3_count} 个三级")
        export_empty_md(modules, project, args.init_md)
        logger.info(f"\n下一步:")
        logger.info(f"  python -m cosmic_tool.main --docx \"{args.docx}\" --md         # 生成Excel")
        return

    # === Mode 2: fill-md (复制一份MD，AI填充到副本) ===
    if args.fill_md is not None:
        if not api_key:
            logger.warning("⚠ 未设置 API Key。请先运行 --init-config 或设置环境变量")
            return
        _section("阶段2: AI填充COSMIC数据到MD副本")
        if not args.fill_md:
            # 自动推导MD路径：从docx找对应MD文件
            if args.docx:
                args.fill_md = _auto_md_path(args.docx, '_拆分表')
            else:
                # 尝试在当前目录找 _拆分表.md 文件
                for f in os.listdir('.'):
                    if f.endswith('_拆分表.md'):
                        args.fill_md = f
                        break
        if not args.fill_md:
            logger.error("MD文件不存在，请先运行阶段1生成模板MD：")
            return
        if not os.path.exists(args.fill_md):
            logger.error(f"MD文件不存在: {args.fill_md}")
            return
        docx_path = args.docx or _find_docx_from_md(args.fill_md)
        if not docx_path:
            parser.error("--fill-md 需要 --docx 或将MD放在docx同目录下")

        # 设置专属日志目录
        _setup_docx_logging(docx_path)

        # 生成输出路径：在原名基础上加 _已填充
        if args.fill_md.endswith('.md'):
            output_md = args.fill_md[:-3] + '_已填充.md'
        else:
            output_md = args.fill_md + '_已填充.md'

        # 复制原MD → 填充副本
        shutil.copy2(args.fill_md, output_md)
        logger.info(f"源文件: {args.fill_md}")

        modules = _build_modules(docx_path, args.parse_by_ai, api_key, model, base_url,
                                  mapping_name=args.mapping, chapter_detection=args.chapter_detection)
        project = get_project_name(docx_path)
        # 统计实际功能过程数（来自docx，非模板MD）
        l3_modules = [m for m in modules if m.level == 3]
        proc_count = sum(len(m.children) for m in l3_modules if m.children)
        fill_md_with_ai(output_md, modules, project, api_key, model, base_url)
        logger.info(f"\n下一步:")
        logger.info(f"  然后: python -m cosmic_tool.main --docx \"{docx_path}\" --md")
        return

    # === Mode 3: md → Excel ===
    if args.md is not None:
        if not args.template:
            args.template = _default_template_path()
        # Auto-find MD from docx if not specified
        if not args.md:
            if args.docx:
                # Prefer _已填充.md, fall back to _拆分表.md
                filled = _auto_md_path(args.docx, '_AI填充cosmic')
                base = _auto_md_path(args.docx, '_拆分表')
                args.md = filled if os.path.exists(filled) else base
            else:
                # Try to find any _拆分表.md in current dir
                for f in sorted(os.listdir('.'), reverse=True):
                    if f.endswith('_拆分表.md'):
                        args.md = f
                        break
        if not args.md:
            parser.error("无法自动确定MD文件，请指定 --md <路径> 或提供 --docx")
        if not os.path.exists(args.md):
            logger.error(f"MD文件不存在: {args.md}")
            logger.info(f"  python -m cosmic_tool.main --docx \"{args.docx}\" --init-md")
            return
        if not args.output:
            args.output = args.md.replace('.md', '.xlsx')
        _setup_docx_logging(args.docx or args.md)
        _section("阶段3: 从MD生成Excel拆分表")
        items = parse_md_to_items(args.md)
        if not items:
            logger.warning("⚠ MD中未解析到COSMIC数据，请先运行 --fill-md 或手动填写表格")
            return
        write_to_template(args.template, args.output, items)
        total_cfp = sum(item.total_cfp() for item in items)
        logger.info(f"\n总计: {len(items)} 功能过程, {total_cfp} CFP")
        return

    # === Mode 4: --all (docx → MD → AI填充 → Excel) ===
    if args.all:
        if not args.docx:
            parser.error("--all 需要 --docx")
        if not args.template:
            args.template = _default_template_path()
        # Auto-generate output and MD paths from docx
        if not args.output:
            args.output = _auto_output_path(args.docx)

        _setup_docx_logging(args.docx)
        # All md files named after the source docx
        docx_name = os.path.splitext(os.path.basename(args.docx))[0]
        out_dir = os.path.dirname(args.output) or '.'
        md_raw = os.path.join(out_dir, f'{docx_name}_原文.md')
        base_md = os.path.join(out_dir, f'{docx_name}_拆分表.md')
        filled_md = os.path.join(out_dir, f'{docx_name}_AI填充cosmic.md')
        _section("阶段0: 需求说明书 → 原文Markdown")
        convert_to_md(args.docx, md_raw, args.chapter_detection)
        logger.info(f"  原文MD已生成: {md_raw}")

        # Stage 1: 原文 MD → 生成 COSMIC 模板
        _section("阶段1: 原文MD → 生成COSMIC模板")
        modules = _build_modules_from_md(md_raw, args.docx)
        project = get_project_name_from_md(md_raw)
        l1_count = len([m for m in modules if m.level == 1])
        l2_count = len([m for m in modules if m.level == 2])
        l3_count = len([m for m in modules if m.level == 3])
        proc_count = sum(len(m.children) for m in modules if m.level == 3 and m.children)
        logger.info(f"模块层级: {l1_count} 个一级 / {l2_count} 个二级 / {l3_count} 个三级")
        export_empty_md(modules, project, base_md)

        # Stage 2: AI fill MD
        if not args.no_llm:
            if not api_key:
                logger.warning("⚠ 未设置 API Key。请先运行 --init-config 或设置环境变量")
                return
            _section("阶段2: AI填充COSMIC数据到MD副本")
            shutil.copy2(base_md, filled_md)
            fill_md_with_ai(filled_md, modules, project, api_key, model, base_url)

        # Stage 3: MD → Excel
        _section("阶段3: 从MD生成Excel拆分表")
        md_to_use = filled_md if not args.no_llm else base_md
        items = parse_md_to_items(md_to_use)
        if items:
            write_to_template(args.template, args.output, items)
            total_cfp = sum(item.total_cfp() for item in items)
            logger.info(f"\n总计: {len(items)} 功能过程, {total_cfp} CFP")
        else:
            logger.warning("⚠ MD中未解析到COSMIC数据，生成空白模板")
            write_to_template(args.template, args.output, [])
        logger.info(f"中间文件: {md_raw}, {base_md}, {filled_md}")
        return

    # === Mode 5: Direct docx → LLM → Excel (one shot) ===
    if args.docx:
        if not args.template:
            args.template = _default_template_path()
        if not args.output:
            args.output = _auto_output_path(args.docx)
        _setup_docx_logging(args.docx)
        docx_name = os.path.splitext(os.path.basename(args.docx))[0]
        out_dir = os.path.dirname(args.output) or '.'
        _section("阶段0: 需求说明书 → 原文Markdown")
        md_raw = os.path.join(out_dir, f'{docx_name}_原文.md')
        convert_to_md(args.docx, md_raw, args.chapter_detection)
        logger.info(f"  原文MD已生成: {md_raw}")

        _section("阶段1: 原文MD → 构建模块树")
        modules = _build_modules_from_md(md_raw, args.docx)
        project = get_project_name_from_md(md_raw)
        logger.info(f"项目: {project}")
        print_tree(modules)

        items = []
        if not args.no_llm:
            if not api_key:
                logger.warning("⚠ 未设置 API Key。请先运行 --init-config 或设置环境变量")
                return
            _section("阶段2: AI生成COSMIC功能点拆分")
            if base_url:
                logger.info(f"端点: {base_url}")
            items = generate_cosmic_items(
                modules=modules, project_name=project,
                api_key=api_key, base_url=base_url, model=model,
            )

        if items:
            _section("阶段3: 生成Excel")
            write_to_template(args.template, args.output, items)
            total_cfp = sum(item.total_cfp() for item in items)
            logger.info(f"\n总计: {len(items)} 功能过程, {total_cfp} CFP")
        elif args.no_llm:
            write_to_template(args.template, args.output, [])
            logger.info("生成空白模板（无数据行）")
        return

    def _write_combined_ai_log():
        """合并 ai_prompts 和 ai_responses 为一个日志文件。"""
        log_dir = os.environ.get('COSMIC_LOG_DIR', '')
        if not log_dir:
            return
        prompt_dir = os.path.join(log_dir, 'ai_prompts')
        resp_dir = os.path.join(log_dir, 'ai_responses')
        if not os.path.isdir(prompt_dir) and not os.path.isdir(resp_dir):
            return

        combined = []
        # 按文件名排序，将 prompt 和对应 response 配对
        all_files = {}
        for d in [prompt_dir, resp_dir]:
            if os.path.isdir(d):
                for fname in os.listdir(d):
                    if fname.endswith('.txt'):
                        all_files[fname] = os.path.join(d, fname)

        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        out_path = os.path.join(log_dir, f'ai_对话日志_{ts}.md')
        with open(out_path, 'w', encoding='utf-8') as out:
            out.write(f"# AI 对话日志\n")
            out.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            for fname in sorted(all_files.keys()):
                filepath = all_files[fname]
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                # 用文件类型作为标题（prompt / response）
                ftype = "📤 提示词" if "prompt" in fname else "📥 响应"
                out.write(f"## {ftype}: {fname}\n\n")
                out.write(content)
                out.write("\n\n---\n\n")

    # === Mode 6: --from-excel 系列（功能清单 → 全套交付物） ===
    if any([args.gen_basedata, args.gen_fpa, args.gen_cosmic, args.gen_list,
             args.gen_spec, args.gen_all]):
        _section("Excel 功能清单 → 全套交付物")

        # 未指定 --from-excel 时，默认找当前目录下的 功能清单-录入-模板.xlsx 或 功能清单.xlsx
        excel_path = args.from_excel
        if not excel_path:
            import glob
            for name in ["功能清单-录入-模板.xlsx", "功能清单.xlsx"]:
                matches = glob.glob(name)
                if matches:
                    excel_path = matches[0]
                    break
            if not excel_path:
                logger.error("未指定 --from-excel，且当前目录未找到 功能清单-录入-模板.xlsx")
                return
        if not os.path.exists(excel_path):
            logger.error(f"文件不存在: {excel_path}")
            return

        out_dir = args.output_dir or os.path.join(os.path.dirname(os.path.abspath(excel_path)), 'products')
        os.makedirs(out_dir, exist_ok=True)

        # 设置 per-output 日志目录
        log_dir = os.path.join(out_dir, 'log')
        os.makedirs(log_dir, exist_ok=True)
        setup_logging(log_dir, '功能清单')
        os.environ['COSMIC_LOG_DIR'] = log_dir
        logger.info(f"日志目录: {log_dir}")

        # 模板文件路径（默认与输出同目录）
        fpa_template = os.path.join(out_dir, 'FPA工作量评估.xlsx')
        cosmic_template = os.path.join(out_dir, '项目功能点拆分表.xlsx')
        require_template = os.path.join(out_dir, '项目需求清单.xlsx')
        doc_template = os.path.join(out_dir, '项目需求说明书.docx')

        # 从元数据解析输出文件名（各 sheet 中的 文件名 字段）
        import re as _re
        def _resolve_output_filename(sheet_name: str, default: str) -> str:
            if not os.path.exists(meta_md):
                return default
            with open(meta_md, encoding='utf-8') as f:
                c = f.read()
            sec = _re.search(
                rf'##\s*{_re.escape(sheet_name)}.*?(?=##|\Z)', c, _re.DOTALL
            )
            if not sec:
                return default
            m = _re.search(r'\|\s*文件名\s*\|\s*(.+?)\s*(?:\||$)', sec.group())
            if not m:
                return default
            name = m.group(1).strip()
            for ph, key in [('${工单编号}', '工单编号'), ('${工单名称}', '工单标题'),
                            ('${工单标题}', '工单标题'), ('${子系统（模块）}', '子系统（模块）')]:
                pm = _re.search(rf'{key}\s*\|\s*(.+?)(?:\s*\||$)', c)
                if pm:
                    name = name.replace(ph, pm.group(1).strip())
            return os.path.join(out_dir, name)
        # 从元数据解析各输出文件名（覆盖默认值）


        # 数据源中间文件路径
        md_dir = os.path.join(out_dir, 'md')
        os.makedirs(md_dir, exist_ok=True)
        meta_md_tpl = os.path.join(md_dir, '文档元数据模板.md')
        meta_md = os.path.join(md_dir, 'AI填充文档元数据.md')
        if not os.path.exists(meta_md) and os.path.exists(meta_md_tpl):
            meta_md = meta_md_tpl  # 无 AI填充版本时回退模板
        cosmic_template = _resolve_output_filename("6、项目功能点拆分表-元数据录入", cosmic_template)
        require_template = _resolve_output_filename("7、项目需求清单-元数据录入", require_template)
        doc_template = _resolve_output_filename("4、项目需求说明书-元数据录入", doc_template)
        tree_md = os.path.join(md_dir, '功能清单模块树.md')
        fpa_sum_md = os.path.join(md_dir, 'FPA工作量.md')
        meta_filled_md = os.path.join(md_dir, 'AI填充文档元数据.md')

        # AI 配置
        api_key = args.api_key or load_api_key()
        model = args.model or load_model_name("deepseek-v4-flash")
        base_url = load_base_url()

        # 是否需要先生成数据源中间文件
        needs_md = not (os.path.exists(meta_md) and os.path.exists(tree_md))
        if needs_md:
            logger.info("第1步: 生成功能清单模块树.md 和 文档元数据模板.md...")
            generate_md_files(excel_path, md_dir)
        else:
            logger.info("数据源中间文件已存在，跳过生成")

        # MD 生成后再检查一次（首次运行模板刚生成，AI填充版还未创建）
        if not os.path.exists(meta_md) and os.path.exists(meta_md_tpl):
            meta_md = meta_md_tpl

        # 验证模块树统计（功能清单模块树.md ↔ 文档元数据模板.md ## 9）

        verify_module_tree_stats(tree_md, meta_md)
        # 读取模板路径配置（功能清单-录入-模板.xlsx → sheet 8）
        tpl_cfg = read_template_config(excel_path)
        _project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        def _tpl(key: str, fallback: str, cli_arg: str = "") -> str:
            """解析模板路径，优先级：CLI > Excel sheet 8 > data/templates/。"""
            if cli_arg:
                cli_val = getattr(args, cli_arg, "").strip()
                if cli_val:
                    if os.path.exists(cli_val):
                        return cli_val
                    logger.warning(f"CLI 指定的模板路径不存在: {cli_val}")
            cfg_path = tpl_cfg.get(key, "")
            if cfg_path and os.path.exists(cfg_path):
                return cfg_path
            full = os.path.join(_project_root, 'data', 'templates', fallback)
            full = os.path.normpath(full)
            if os.path.exists(full):
                return full
            return os.path.join('data', 'templates', fallback)

        fpa_src_template = _tpl('FPA工作量评估-模板', 'FPA工作量评估-模板.xlsx', 'fpa_template')
        cosmic_src_template = _tpl('项目功能点拆分表-模板', '项目功能点拆分表-模板.xlsx', 'cosmic_template')
        require_src_template = _tpl('项目需求清单-模板', '项目需求清单-模板.xlsx', 'list_template')
        doc_src_template = _tpl('项目需求说明书-模板', '项目需求说明书-模板.docx', 'spec_template')

        # --gen-all: 按依赖顺序自动执行
        if args.gen_all:
            logger.info("全流程模式：按依赖顺序执行...")

            # Step 0: 生成数据源中间文件
            _ensure_basedata(excel_path, md_dir, meta_md, tree_md, meta_md_tpl)
            fpa_template = _resolve_output_filename("3、FPA工作量评估-元数据录入", fpa_template)

            # Step 1: FPA（MD → 模板MD → AI填充FPA.md → Excel）
            fpa_md = os.path.join(md_dir, 'FPA模板.md')
            fpa_filled_md = os.path.join(md_dir, 'AI填充FPA.md')
            if not os.path.exists(fpa_template):
                logger.info("第1步：FPA → 模板 MD...")
                init_fpa_template_md(tree_md, meta_md, fpa_md)
                if api_key:
                    import shutil
                    shutil.copy2(fpa_md, fpa_filled_md)
                    logger.info("第1步：AI 填充 FPA...")
                    ai_fill_fpa_md(fpa_filled_md, meta_md, api_key=api_key, model=model, base_url=base_url)
                logger.info("第1步：生成 FPA Excel...")
                fpa_src = fpa_filled_md if api_key else fpa_md
            fpa_template_file = fpa_src_template
            generate_fpa_xlsx_from_md(fpa_src, meta_md, fpa_template_file, fpa_template)
            _write_fpa_summary(fpa_template, fpa_sum_md)

            # 读取核减后工作量（从 FPA Excel > 元数据 > 用户输入 > 默认值）
            fpa_reduced = _resolve_fpa_sum(fpa_sum_md)

            # Step 2: COSMIC
            if not os.path.exists(cosmic_template):
                logger.info("第2步：生成 项目功能点拆分表.xlsx...")
                # 使用现有链路：init_base_data_md + ai_fill_cosmic_data_md + write_to_template
                logger.info("  步骤2a: 从模块树生成拆分表 MD...")
                from cosmic_tool.docx_parser import FunctionModule
                modules = _build_modules_from_md(tree_md)
                project = modules[0].name if modules else "项目"

                init_md_path = os.path.join(md_dir, 'cosmic模板.md')
                filled_md_path = os.path.join(md_dir, 'AI填充cosmic.md')
                export_empty_md(modules, project, init_md_path)

                if api_key:
                    logger.info("  步骤2b: AI 填充 COSMIC 数据...")
                    import shutil
                    shutil.copy2(init_md_path, filled_md_path)
                    from cosmic_tool.cosmic_llm import load_user_config_from_meta
                    _user_cfg = load_user_config_from_meta(meta_md)
                    fill_md_with_ai(filled_md_path, modules, project, api_key, model, base_url,
                                    **_user_cfg)
                else:
                    logger.warning("  跳过 AI 填充（未设置 API Key）")
                    filled_md_path = init_md_path

                logger.info("  步骤2c: 写入 Excel...")
                items = parse_md_to_items(filled_md_path)
                if items:
                    from cosmic_tool.excel_writer import write_to_template
                    write_to_template(cosmic_src_template, cosmic_template, items)
                    total_cfp = sum(item.total_cfp() for item in items)
                    logger.info(f"  CFP 总和: {total_cfp}")
                else:
                    logger.warning("  MD 中无数据")
            else:
                logger.info("项目功能点拆分表.xlsx 已存在，跳过")

            # 读取 CFP 总和
            cfp_total = 0
            if os.path.exists(cosmic_template):
                # 从已填充 MD 读取 CFP
                filled_md_path = os.path.join(md_dir, 'AI填充cosmic.md')
                if os.path.exists(filled_md_path):
                    items = parse_md_to_items(filled_md_path)
                    cfp_total = sum(item.total_cfp() for item in items)
            logger.info(f"CFP 总和: {cfp_total}")

            # Step 3: 需求清单
            if not os.path.exists(require_template):
                logger.info("第3步：生成 项目需求清单.xlsx...")
                generate_require_xlsx(meta_md, tree_md, require_src_template, require_template,
                                      cfp_total=cfp_total)
            else:
                logger.info("项目需求清单.xlsx 已存在，跳过")

            # Step 可选: docx
            if not os.path.exists(doc_template):
                logger.info("可选：生成 项目需求说明书.docx...")
                generate_spec(doc_template, doc_template, meta_md, tree_md,
                              api_key=api_key, model=model, base_url=base_url)
            else:
                logger.info("项目需求说明书.docx 已存在，跳过")

            _write_combined_ai_log()
            _section("全流程完成")
            return

        # --gen-basedata
        if args.gen_basedata:
            logger.info("第1步: 生成功能清单模块树.md 和 文档元数据模板.md...")
            generate_md_files(excel_path, md_dir)
            verify_module_tree_stats(tree_md, meta_md_tpl)

            if api_key and (not os.path.exists(meta_filled_md)):
                logger.info("第2步: AI 填充文档元数据...")
                _ai_fill_meta_md(meta_md_tpl, meta_filled_md, api_key, model, base_url)
            elif os.path.exists(meta_filled_md):
                logger.info("AI填充文档元数据.md 已存在，跳过")
            else:
                logger.warning("未设置 API Key，跳过 AI 填充")
                import shutil
                shutil.copy2(meta_md_tpl, meta_filled_md)

            _write_combined_ai_log()
            logger.info("数据源中间文件已生成:")
            logger.info(f"  {meta_md_tpl}")
            if os.path.exists(meta_filled_md):
                logger.info(f"  {meta_filled_md}")
            return

        # --gen-fpa: MD → FPA模板MD → AI填充FPA.md → Excel
        if args.gen_fpa:
            _ensure_basedata(excel_path, md_dir, meta_md, tree_md, meta_md_tpl)
            fpa_template = _resolve_output_filename("3、FPA工作量评估-元数据录入", fpa_template)
            fpa_md = os.path.join(md_dir, 'FPA模板.md')
            fpa_filled_md = os.path.join(md_dir, 'AI填充FPA.md')
            logger.info("第1步: 生成 FPA 模板 MD...")
            init_fpa_template_md(tree_md, meta_md, fpa_md)

            if api_key:
                logger.info("第2步: AI 填充 FPA 数据...")
                import shutil
                shutil.copy2(fpa_md, fpa_filled_md)
                ai_fill_fpa_md(fpa_filled_md, meta_md, api_key=api_key, model=model, base_url=base_url)
            else:
                logger.warning("未设置 API Key，跳过 AI 填充")
                fpa_filled_md = fpa_md

            logger.info("第3步: 生成 FPA 工作量评估 Excel...")
            generate_fpa_xlsx_from_md(fpa_filled_md, meta_md, fpa_src_template, fpa_template)
            _write_fpa_summary(fpa_template, fpa_sum_md)
            _write_combined_ai_log()
            logger.info(f"FPA工作量评估已生成: {fpa_template}")
            return

        # --gen-cosmic
        if args.gen_cosmic:
            logger.info("生成 项目功能点拆分表.xlsx...")
            from cosmic_tool.docx_parser import FunctionModule
            modules = _build_modules_from_md(tree_md)
            project = _read_project_name(meta_md) or (modules[0].name if modules else "项目")

            # 确保数据源存在，提示输入核减后工作量
            _ensure_basedata(excel_path, md_dir, meta_md, tree_md, meta_md_tpl)
            _resolve_fpa_sum(fpa_sum_md)

            init_md_path = os.path.join(md_dir, 'cosmic模板.md')
            filled_md_path = os.path.join(md_dir, 'AI填充cosmic.md')
            export_empty_md(modules, project, init_md_path)

            if api_key:
                import shutil
                shutil.copy2(init_md_path, filled_md_path)
                from cosmic_tool.cosmic_llm import load_user_config_from_meta
                _user_cfg = load_user_config_from_meta(meta_md)
                fill_md_with_ai(filled_md_path, modules, project, api_key, model, base_url,
                                **_user_cfg)

                items = parse_md_to_items(filled_md_path)
                if items:
                    from cosmic_tool.excel_writer import write_to_template
                    write_to_template(cosmic_src_template, cosmic_template, items)
                    total_cfp = sum(item.total_cfp() for item in items)
                    logger.info(f"CFP 总和: {total_cfp}")
                    _write_combined_ai_log()
                    logger.info(f"项目功能点拆分表已生成: {cosmic_template}")
            else:
                logger.warning("未设置 API Key，无法生成 COSMIC 拆分数据")
            return

        # --gen-require
        if args.gen_list:
            _ensure_basedata(excel_path, md_dir, meta_md, tree_md, meta_md_tpl)
            # 读取 CFP 总和
            cfp_total = 0
            filled_md_path = os.path.join(md_dir, 'AI填充cosmic.md')
            if os.path.exists(filled_md_path):
                items = parse_md_to_items(filled_md_path)
                cfp_total = sum(item.total_cfp() for item in items)
                logger.info(f"从已填充 MD 读取 CFP 总和: {cfp_total}")
            elif os.path.exists(cosmic_template):
                # 尝试从已生成的 xlsx 读取
                import openpyxl
                try:
                    wb = openpyxl.load_workbook(cosmic_template, data_only=True)
                    # 取功能点拆分表 sheet 的最后一列求和
                    ws = wb['2、功能点拆分表']
                    cfp_total = 0
                    for row in ws.iter_rows(min_row=6, values_only=True):
                        val = row[12] if len(row) > 12 else None  # M列
                        if val:
                            try:
                                cfp_total += float(val)
                            except (ValueError, TypeError):
                                pass
                    wb.close()
                    logger.info(f"从 Excel 读取 CFP 总和: {cfp_total}")
                except Exception as e:
                    logger.warning(f"从 Excel 读取 CFP 失败: {e}")

            generate_require_xlsx(meta_md, tree_md, require_src_template, require_template,
                                  cfp_total=cfp_total)
            _write_combined_ai_log()
            logger.info(f"项目需求清单已生成: {require_template}")
            return

        # --gen-spec
        if args.gen_spec:
            _ensure_basedata(excel_path, md_dir, meta_md, tree_md, meta_md_tpl)
            spec_md = os.path.join(md_dir, 'spec模板.md')
            spec_filled = os.path.join(md_dir, 'AI填充spec.md')

            logger.info("第1步: 生成 spec 模板 MD...")
            export_spec_template_md(excel_path, tree_md, spec_md)

            if api_key and os.path.exists(spec_filled):
                logger.info("第2步: AI填充spec.md 已存在，跳过 AI 生成")
            elif api_key:
                logger.info("第2步: AI 填充 spec 数据...")
                import shutil
                shutil.copy2(spec_md, spec_filled)
                fill_spec_md(spec_filled, meta_md, api_key=api_key, model=model, base_url=base_url)
            else:
                spec_filled = spec_md

            logger.info("第3步: 生成 项目需求说明书.docx...")
            generate_spec(doc_src_template, doc_template, meta_md, tree_md,
                          filled_md_path=spec_filled,
                          api_key=api_key, model=model, base_url=base_url)
            _write_combined_ai_log()
            logger.info(f"项目需求说明书已生成: {doc_template}")
            return

    # === No valid mode ===
    # Batch mode (above) handles the default case when no args given
    pass


def _project_root() -> str:
    """Get project root dir (works for both source and PyInstaller exe)."""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(__file__))


def _default_template_path() -> str:
    """Return template path from ~/.cosmic-tool/business_rules.yaml or default."""
    rules_path = os.path.join(os.path.expanduser('~'), '.cosmic-tool', 'business_rules.yaml')
    if os.path.exists(rules_path):
        try:
            import yaml
            with open(rules_path, 'r', encoding='utf-8') as f:
                rules = yaml.safe_load(f) or {}
            yaml_path = (rules.get('template_path') or '').strip()
            if yaml_path:
                if not os.path.isabs(yaml_path):
                    yaml_path = os.path.join(_project_root(), yaml_path)
                if os.path.exists(yaml_path):
                    return yaml_path
        except Exception:
            pass
    # 优先 data/templates/项目功能点拆分表-模板.xlsx，回退 data/项目功能点拆分表.xlsx
    tpl = os.path.join(_project_root(), 'data', 'templates', '项目功能点拆分表-模板.xlsx')
    if os.path.exists(tpl):
        return tpl
    return os.path.join(_project_root(), 'data', '项目功能点拆分表.xlsx')


def _auto_md_path(docx_path: str, suffix: str = '') -> str:
    """Derive MD file path from docx filename.

    suffix: '_拆分表' or '' (auto-chooses based on existing files)
    """
    base = os.path.basename(docx_path)
    name, _ = os.path.splitext(base)
    return os.path.join(os.path.dirname(docx_path), name + suffix + '.md')


def _auto_output_path(docx_path: str) -> str:
    """Derive Excel output path from docx filename automatically.

    规则:
      - docx 中的"需求说明书" → "功能点拆分表"
      - "附件1" → "附件2"
      - .docx → .xlsx
    """
    base = os.path.basename(docx_path)
    name, _ = os.path.splitext(base)
    name = name.replace('需求说明书', '功能点拆分表')
    if name.startswith('附件1'):
        name = name.replace('附件1', '附件2', 1)
    return os.path.join(os.path.dirname(docx_path), name + '.xlsx')


def _find_docx_from_md(md_path: str) -> str:
    """Try to find the corresponding docx for an MD file."""
    md_dir = os.path.dirname(os.path.abspath(md_path))
    for f in os.listdir(md_dir):
        if f.endswith('.docx') and not f.startswith('~$'):
            return os.path.join(md_dir, f)
    parent = os.path.dirname(md_dir)
    for f in os.listdir(parent):
        if f.endswith('.docx') and not f.startswith('~$'):
            return os.path.join(parent, f)
    return ""


if __name__ == '__main__':
    _exit_code = 0
    try:
        main()
    except Exception:
        _exit_code = 1
        import traceback
        traceback.print_exc()
    if getattr(sys, 'frozen', False):
        input("\n按 Enter 键退出...")
    sys.exit(_exit_code)
