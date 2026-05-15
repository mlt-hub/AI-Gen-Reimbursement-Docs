"""AI生成项目报账文档 - CLI入口

推荐工作流（MD中间件模式）:
  0. python -m ai_gen_reimbursement_docs.main --docx 需求书.docx --init-md 需求书_拆分表.md   (含原文转MD)
  1. python -m ai_gen_reimbursement_docs.main --fill-md 需求书_拆分表.md
     (编辑拆分表.md 人工审核修正)
  2. python -m ai_gen_reimbursement_docs.main --md 需求书_拆分表.md --template 模板.xlsx --output 结果.xlsx

快捷模式（一键全流程）:
  python -m ai_gen_reimbursement_docs.main --docx "需求书.docx" --template "模板.xlsx" --output "结果.xlsx" --all

一键直出（跳过MD中间文件）:
  python -m ai_gen_reimbursement_docs.main --docx 需求书.docx --template 模板.xlsx --output 结果.xlsx

批量处理Word文件:
  python -m ai_gen_reimbursement_docs.main --docx-all
"""

import argparse
import logging
import os
import shutil
import sys
from datetime import datetime

from ai_gen_reimbursement_docs.exceptions import ConfigError
from ai_gen_reimbursement_docs.models import FunctionModule
from ai_gen_reimbursement_docs.excel_writer import generate_cosmic_xlsx_from_md
from ai_gen_reimbursement_docs.config_utils import load_api_key, load_base_url, load_model_name, load_business_config
from ai_gen_reimbursement_docs.md_handler import (
    export_empty_md,
    export_filled_md,
    parse_md_to_items,
    fill_md_with_ai,
)
from ai_gen_reimbursement_docs.excel_source import generate_md_files, read_template_config, verify_module_tree_stats
from ai_gen_reimbursement_docs.gen_spec import generate_spec_docx_from_md, ai_fill_spec_md, init_spec_template_md
from ai_gen_reimbursement_docs.gen_xlsx import generate_fpa_xlsx_from_md, generate_list_xlsx_from_md
from ai_gen_reimbursement_docs.gen_xlsx import init_fpa_template_md, ai_fill_fpa_md

# 启动时自动清理 ai_gen_reimbursement_docs 自身的字节码缓存，避免代码修改后缓存过期问题
_pycache = os.path.join(os.path.dirname(__file__), '__pycache__')
if os.path.isdir(_pycache):
    shutil.rmtree(_pycache, ignore_errors=True)


def _init_global_logging():
    """初始化全局日志：项目根目录 log/（控制台 + 总日志 + 运行日志）"""
    if getattr(sys, 'frozen', False):
        log_dir = os.path.join(os.path.expanduser('~'), '.ai-gen-reimbursement-docs', 'log')
    else:
        log_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 'log'
        )
    os.makedirs(log_dir, exist_ok=True)

    main_log = os.path.join(log_dir, 'ai_gen_reimbursement_docs.log')
    run_stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    run_log = os.path.join(log_dir, f'global_run_{run_stamp}.log')

    logger = logging.getLogger('ai_gen_reimbursement_docs')
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 全局总日志（持续追加，永不删除）
    main_log = os.path.join(log_dir, 'global_ai_gen_reimbursement_docs.log')
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

    # 序号：扫描已有日志，自动递增
    _seq = 1
    if docx_name:
        import re as _re_seq
        _max_seq = 0
        try:
            for _fn in os.listdir(log_dir):
                _m = _re_seq.match(re.escape(docx_name) + r'_run_(\d+)_\d{8}_\d{6}\.log$', _fn)
                if _m:
                    _max_seq = max(_max_seq, int(_m.group(1)))
        except Exception:
            pass
        _seq = _max_seq + 1

    prefix = f"{docx_name}_" if docx_name else ""
    run_stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    seq_str = f"{_seq}_" if docx_name else ""
    run_log = os.path.join(log_dir, f'{prefix}run_{seq_str}{run_stamp}.log')

    logger = logging.getLogger('ai_gen_reimbursement_docs')

    fmt = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    rh = logging.FileHandler(run_log, encoding='utf-8', mode='w')
    rh.setLevel(logging.DEBUG)
    rh.setFormatter(fmt)
    logger.addHandler(rh)

    return logger, run_log


logger, _run_log_path = _init_global_logging()


def _get_version() -> str:
    """Read version from pyproject.toml (single source of truth)."""
    import tomllib
    try:
        # 先尝试项目根目录（开发模式），再尝试 _MEIPASS（PyInstaller 打包）
        toml_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'pyproject.toml')
        if not os.path.exists(toml_path):
            toml_path = os.path.join(_project_root(), 'pyproject.toml')
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
    os.environ['AI_REIMBURSEMENT_LOG_DIR'] = log_dir
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
            model=model or "",
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
        from ai_gen_reimbursement_docs.docx_parser import build_module_tree
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
    """从gen-basedata-功能清单-模块树.md 的表格格式构建 FunctionModule 列表。

    表格列：入口 | 一级模块 | 二级模块 | 三级模块 | ... | 功能过程 | ...
    自动去重并构建 L1→L2→L3 层级，功能过程作为 L3 的 children。
    """
    from ai_gen_reimbursement_docs.md_table import parse_md_table_row

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
    seen_l3: dict[tuple[str, str], set[str]] = {}  # (l1, l2) → set of l3 names
    l3_desc: dict[str, str] = {}                     # l3 name → description
    l3_procs: dict[tuple[str, str, str], list[str]] = {}  # (l1, l2, l3) → processes（保持原始顺序）

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
        # L2 用 "L1/L2" 复合 parent 区分不同 L1 下的同名 L2
        l2_parent = f"{l1}/{l2}" if l2 else ""
        if l2 and l2 not in seen_l2[l1]:
            seen_l2[l1].add(l2)
            modules.append(FunctionModule(name=l2, level=2, parent=l1))
        l3_key = (l1, l2)
        if l3_key not in seen_l3:
            seen_l3[l3_key] = set()
        if l3 not in seen_l3[l3_key]:
            seen_l3[l3_key].add(l3)
            # L3 parent 用 "L1/L2" 确保不同 L1 下同名 L2 的 L3 不串
            modules.append(FunctionModule(name=l3, level=3, parent=l2_parent,
                                          description=desc))
            l3_desc[l3] = desc
        procs_key = (l1, l2, l3)
        if procs_key not in l3_procs:
            l3_procs[procs_key] = []
        if proc and proc not in l3_procs[procs_key]:
            l3_procs[procs_key].append(proc)

    # 将功能过程挂到 L3 的 children（用 (L1,L2,L3) 三元组精确匹配，避免不同 L1 下同名模块串数据）
    for m in modules:
        if m.level == 3:
            # parent 格式为 "L1/L2"，直接拆分得到完整路径
            parent_parts = m.parent.split("/") if m.parent else []
            l1_name = parent_parts[0] if len(parent_parts) >= 1 else ""
            l2_name = parent_parts[1] if len(parent_parts) >= 2 else m.parent
            procs_key = (l1_name, l2_name, m.name)
            m.children = l3_procs.get(procs_key, [])

    l3_count = len([m for m in modules if m.level == 3])
    logger.info(f"从表格解析到模块层级: {len(seen_l1)}个L1, "
                f"{sum(len(v) for v in seen_l2.values())}个L2, "
                f"{l3_count}个L3")
    return modules


def _read_project_name(meta_md_path: str) -> str:
    """从gen-basedata-录入文档元数据-模板.md 读取项目名称（工单标题）。"""
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
    """确保数据源中间文件存在（gen-basedata-功能清单-模块树.md + gen-basedata-录入文档元数据-模板.md）。"""
    tpl = meta_md_tpl or meta_md
    needs_md = not (os.path.exists(tpl) and os.path.exists(tree_md))
    if needs_md:
        logger.info("第1步: 生成gen-basedata-功能清单-模块树.md 和 gen-basedata-录入文档元数据-模板.md...")
        generate_md_files(excel_path, md_dir)
    verify_module_tree_stats(tree_md, tpl)


def _resolve_fpa_sum(fpa_sum_md_path: str) -> float:
    """从 FPA工作量.md 读取值作为默认，提示用户输入FPA核减后工作量。"""
    from ai_gen_reimbursement_docs.config_utils import load_fpa_reduced_use_workload
    if load_fpa_reduced_use_workload():
        import re
        if os.path.exists(fpa_sum_md_path):
            with open(fpa_sum_md_path, encoding='utf-8') as f:
                for line in f:
                    m = re.search(r'FPA工作量（人/天）[：:]\s*([\d.]+)', line)
                    if m:
                        val = float(m.group(1))
                        logger.info(f"FPA核减后工作量: {val}（直接用 FPA 工作量）")
                        return val
        return 0

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
        print(f"\n请输入送审工作量（直接回车使用FPA工作量总和：{md_val}）: ", end="")
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
    print(f"\n{msg}")
    return 0


def _read_md_value(path: str, pattern: str) -> float:
    """从 MD 文件中按正则提取数值，文件不存在返回 0。"""
    import re
    if not os.path.exists(path):
        return 0.0
    with open(path, encoding='utf-8') as f:
        for line in f:
            m = re.search(pattern, line)
            if m:
                return float(m.group(1))
    return 0.0


def _prompt_list_values(fpa_sum_md_path: str) -> tuple[float, float]:
    """提示用户输入送审功能点和送审工作量（gen-list 使用）。

    从 gen-cosmic-CFP-总和.md / gen-fpa-FPA工作量-总和.md 读取默认值。
    返回 (cfp_total, fpa_reduced)。
    """
    _cfp_raw = _read_md_value(
        os.path.join(os.path.dirname(fpa_sum_md_path), 'gen-cosmic-CFP-总和.md'),
        r'CFP 总和[：:]\s*([\d.]+)')
    _fpa_raw = _read_md_value(fpa_sum_md_path,
        r'FPA工作量（人/天）[：:]\s*([\d.]+)')

    # 送审功能点
    if _cfp_raw > 0:
        _prompt = f"\n请输入送审功能点（直接回车使用CFP总和：{_cfp_raw}）: "
    else:
        _prompt = "\n请输入送审功能点: "
    try:
        _inp = input(_prompt).strip()
        cfp_total = float(_inp) if _inp else _cfp_raw
    except (EOFError, OSError, ValueError):
        cfp_total = _cfp_raw
        logger.info(f"送审功能点: {cfp_total}（默认值）")

    # 送审工作量
    if _fpa_raw > 0:
        _prompt2 = f"请输入送审工作量（直接回车使用FPA工作量总和：{_fpa_raw}）: "
    else:
        _prompt2 = "请输入送审工作量: "
    try:
        _inp2 = input(_prompt2).strip()
        fpa_reduced = float(_inp2) if _inp2 else _fpa_raw
    except (EOFError, OSError, ValueError):
        fpa_reduced = _fpa_raw
        logger.info(f"送审工作量: {fpa_reduced}（默认值）")

    logger.info(f"送审功能点: {cfp_total}, 送审工作量: {fpa_reduced}")
    return cfp_total, fpa_reduced


def _write_combined_ai_log(stage: str = ""):
    """增量追加 AI 对话日志（合并版 + prompts 版 + responses 版）。

    stage: 当前 gen-* 阶段名（如 gen-basedata, gen-fpa 等），写入日志标记。
    """
    log_dir = os.environ.get('AI_REIMBURSEMENT_LOG_DIR', '')
    if not log_dir:
        return
    prompt_dir = os.path.join(log_dir, 'ai_prompts')
    resp_dir = os.path.join(log_dir, 'ai_responses')
    if not os.path.isdir(prompt_dir) and not os.path.isdir(resp_dir):
        return

    NL = chr(10)
    dirs = {
        'ai_对话日志.md': (prompt_dir, resp_dir),
        'ai_prompts_日志.md': (prompt_dir,),
        'ai_responses_日志.md': (resp_dir,),
    }

    for out_name, sub_dirs in dirs.items():
        out_path = os.path.join(log_dir, out_name)
        # 收集文件
        all_files = {}
        for d in sub_dirs:
            if os.path.isdir(d):
                for fname in os.listdir(d):
                    if fname.endswith('.txt'):
                        all_files[fname] = os.path.join(d, fname)

        # 已写入的不重复
        logged_files: set[str] = set()
        if os.path.exists(out_path):
            with open(out_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('## ') and '.txt' in line:
                        logged_files.add(line.split(':', 1)[1].strip())

        new_count = 0
        with open(out_path, 'a', encoding='utf-8') as out:
            if not logged_files:
                title = out_name.replace('.md', '').replace('_', ' ')
                out.write(f'# {title}{NL}')
                out.write(f'**首次生成**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}{NL}{NL}')
            # 先收集本轮新文件
            new_fnames = [f for f in sorted(all_files.keys()) if f not in logged_files]
            if new_fnames and stage:
                out.write(f'{NL}---{NL}')
                out.write(f'## {stage}{NL}{NL}')
            for fname in new_fnames:
                new_count += 1
                with open(all_files[fname], 'r', encoding='utf-8') as f:
                    fc = f.read()
                ftype = '提示词' if 'prompt' in fname else '响应'
                out.write(f'## {ftype}: {fname}{NL}{NL}')
                out.write(fc)
                out.write(f'{NL}{NL}---{NL}{NL}')

        if new_count > 0:
            logger.info(f"{out_name} 追加 {new_count} 条新记录")


def _write_cfp_sum(md_dir: str, total: float) -> None:
    """将 CFP 总和写入 gen-cosmic-CFP-总和.md。"""
    path = os.path.join(md_dir, 'gen-cosmic-CFP-总和.md')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(f"# CFP 总和\n\n")
        f.write(f"CFP 总和: {total}\n")
    logger.info(f"CFP 总和已写入: {path}")


def _play_notify_sound():
    """根据 notify_sound 配置播放提示音。"""
    try:
        import yaml as _y
        _notify = False
        for _p in [
            os.path.join(os.path.dirname(os.path.dirname(__file__)),
                         'config', 'system_config.yaml'),
            os.path.join(os.environ.get('USERPROFILE', os.environ.get('HOME', '')),
                         '.ai-gen-reimbursement-docs', 'system_config.yaml'),
        ]:
            if os.path.isfile(_p):
                with open(_p, encoding='utf-8') as _f:
                    _c = _y.safe_load(_f)
                if _c and _c.get('notify_sound'):
                    _notify = True
                    break
        if _notify:
            import winsound
            _audio_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'data', 'audio', 'ticktick_pop.wav'
            )
            if os.path.isfile(_audio_path):
                winsound.PlaySound(_audio_path, winsound.SND_FILENAME | winsound.SND_SYNC)
    except Exception:
        pass


def _collect_l3_names(tree_md: str) -> list[str]:
    """从gen-basedata-功能清单-模块树.md 收集所有去重的三级模块名（保持原始顺序）。"""
    from ai_gen_reimbursement_docs.md_table import parse_md_table_row
    names: list[str] = []
    seen: set[str] = set()
    if not os.path.exists(tree_md):
        return names
    with open(tree_md, encoding='utf-8') as f:
        for line in f:
            cells = parse_md_table_row(line, min_cols=4)
            if cells is not None and cells[3]:
                name = cells[3].strip()
                if name and name not in seen:
                    seen.add(name)
                    names.append(name)
    return names


def _call_llm_once(prompt: str, api_key: str, model: str, base_url: str,
                   tag: str = "") -> str:
    """单次 LLM 调用（委托至 llm_client 公共模块）。"""
    from ai_gen_reimbursement_docs.config_utils import load_ai_system_prompt
    system_prompt = load_ai_system_prompt("metadata_gen")
    from ai_gen_reimbursement_docs.llm_client import call_llm
    try:
        return call_llm(
            prompt=prompt, system=system_prompt,
            api_key=api_key, model=model, base_url=base_url, tag=tag,
        )
    except Exception as e:
        logger.warning("AI 调用失败 [%s]: %s", tag, e)
        return ""


def _call_llm_once(prompt: str, api_key: str, model: str, base_url: str,
                   tag: str = "") -> str:
    """单次 LLM 调用（委托至 llm_client 公共模块）。"""
    from ai_gen_reimbursement_docs.config_utils import load_ai_system_prompt
    system_prompt = load_ai_system_prompt("metadata_gen")
    from ai_gen_reimbursement_docs.llm_client import call_llm
    try:
        return call_llm(
            prompt=prompt, system=system_prompt,
            api_key=api_key, model=model, base_url=base_url, tag=tag,
        )
    except Exception as e:
        logger.warning("AI 调用失败 [%s]: %s", tag, e)
        return ""


def _ai_fill_meta_md(src_md: str, dst_md: str, api_key: str, model: str, base_url: str,
                     tree_md: str = "") -> str:
    """读取gen-basedata-录入文档元数据-模板.md，AI 填充 #AI生成# 标记，写入 gen-basedata-AI填充-录入文档元数据.md。

    处理 #AI生成#（包含 #AI生成-XXX# 格式），跳过 #AI补充#。
    tree_md: gen-basedata-功能清单-模块树.md 路径，用于解析 ${三级模块} 等占位符。
    """
    from ai_gen_reimbursement_docs.excel_source import strip_ai_marker, replace_placeholders
    from ai_gen_reimbursement_docs.md_table import parse_md_table_row

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
                        # 解析 ${三级模块}：用所有 L3 模块名拼接
                        if '${三级模块}' in prompt_raw and tree_md:
                            _l3_names = _collect_l3_names(tree_md)
                            prompt_raw = prompt_raw.replace('${三级模块}', '、'.join(_l3_names))
                    resp = _call_llm_once(prompt_raw, api_key, model, base_url,
                                          tag=f"meta_{key}")
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
    """单次 LLM 调用，返回文本（委托至 llm_client 公共模块）。"""
    if not api_key:
        return ""

    from ai_gen_reimbursement_docs.config_utils import load_ai_system_prompt
    system_prompt = load_ai_system_prompt("metadata_gen")

    from ai_gen_reimbursement_docs.llm_client import call_llm
    try:
        return call_llm(
            prompt=prompt, system=system_prompt,
            api_key=api_key, model=model, base_url=base_url, tag=tag,
        )
    except Exception as e:
        logger.warning("AI 调用失败 [%s]: %s", tag, e)
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


def _build_parser() -> argparse.ArgumentParser:
    """构建 CLI 参数解析器。"""
    parser = argparse.ArgumentParser(
        description="AI生成项目报账文档 — 从功能清单自动生成全套报账交付物",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
    工作流示例:

      # (推荐) MD中间件模式：docx → MD → 编辑MD → Excel
      python -m ai_gen_reimbursement_docs.main --docx 需求书.docx --init-md 需求书_拆分表.md
      python -m ai_gen_reimbursement_docs.main --fill-md 需求书_拆分表.md
      python -m ai_gen_reimbursement_docs.main --md 需求书_拆分表.md --template 模板.xlsx --output 结果.xlsx

      # (快捷) 一键直出：docx → LLM → Excel
      python -m ai_gen_reimbursement_docs.main --docx 需求书.docx --template 模板.xlsx --output 结果.xlsx

      # (快捷) 一键全流程：docx → MD → AI填充 → Excel（含gen-basedata-功能清单-模块树.md和gen-basedata-录入文档元数据-模板.md）
      python -m ai_gen_reimbursement_docs.main --docx "需求书.docx" --template "模板.xlsx" --output "结果.xlsx" --all

      # 仅查看模块树
      python -m ai_gen_reimbursement_docs.main --docx 需求书.docx --show-tree

      # 初始化API Key配置
      python -m ai_gen_reimbursement_docs.main --init-config

      # 批量处理当前目录下所有Word文件
      python -m ai_gen_reimbursement_docs.main --docx-all

      # Excel 功能清单 → 全套交付物
      python -m ai_gen_reimbursement_docs.main --from-excel 功能清单.xlsx --gen-all
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
                        help='功能点拆分表 .xlsx 模板文件路径（默认 data/out_templates/）')

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
                        help='指定层级映射名（来自 ~/.ai-gen-reimbursement-docs/docx_parse_mapping_rules.yaml 中的 mapping 名称）')

    parser.add_argument('--chapter-detection', default='',
                        help='指定章节检测配置名（来自 ~/.ai-gen-reimbursement-docs/docx_parse_mapping_rules.yaml 中的 章节检测 分组）')

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
                        help='第0步：生成gen-basedata-功能清单-模块树.md 和 gen-basedata-录入文档元数据-模板.md')

    parser.add_argument('--gen-all', action='store_true',
                        help='全流程：按依赖顺序自动执行 --gen-basedata → --gen-fpa → --gen-spec → --gen-cosmic → --gen-list')

    parser.add_argument('--output-dir', default='',
                        help='--from-excel 系列命令的输出目录（默认输入文件所在目录）')
    parser.add_argument('--project-name', default='',
                        help='--from-excel 系列命令的输出文件夹名称（默认从 Excel 自动读取工单标题）')

    # 模板路径覆盖（优先级: CLI > Excel sheet 8 > data/out_templates/）
    parser.add_argument('--fpa-out-template', default='',
                        help='FPA工作量评估 输出模板路径')
    parser.add_argument('--cosmic-out-template', default='',
                        help='项目功能点拆分表 输出模板路径')
    parser.add_argument('--list-out-template', default='',
                        help='项目需求清单 输出模板路径')
    parser.add_argument('--spec-out-template', default='',
                        help='项目需求说明书 输出模板路径')

    parser.add_argument('--clean', action='store_true',
                        help='--from-excel 时，删除 Excel 同级目录下以工单标题命名的输出文件夹（如有），再重新生成')
    parser.add_argument('--init-config', action='store_true',
                        help='初始化 .env 配置文件')


    parser.add_argument('--log', nargs='?', const='tail', default=None,
                        help='查看日志：--log（末30行），--log full，--log watch，--log open')

    parser.add_argument('--version', '-v', action='store_true',
                        help='显示版本号')
    parser.add_argument('--test-sound', action='store_true',
                        help='测试提示音')
    parser.add_argument('--max-tokens', type=str, default='',
                        help='覆盖 AI max_tokens（如 6000、8K、1M），默认取配置文件')

    return parser

def main():
    parser = _build_parser()
    args = parser.parse_args()
    if args.max_tokens:
        os.environ['AI_REIMBURSEMENT_MAX_TOKENS'] = args.max_tokens
    logger.debug(f"CLI args: {args}")

    # 版本信息
    ver = _get_version()
    run_mode = "exe" if getattr(sys, 'frozen', False) else "源码"
    run_path = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.dirname(__file__))
    logger.info(f"AI生成项目报账文档 v{ver} ({run_mode}: {run_path})")

    # 当前配置目录
    from ai_gen_reimbursement_docs.config_utils import _config_dir
    logger.info(f"配置文件目录: {_config_dir()}")

    # 配置迁移（新模板键自动追加到用户配置文件）
    from ai_gen_reimbursement_docs.config_utils import _migrate_config
    _migrate_config()

    # 测试提示音
    if args.test_sound:
        try:
            import winsound
            _ap = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                               'data', 'audio', 'ticktick_pop.wav')
            if os.path.isfile(_ap):
                winsound.PlaySound(_ap, winsound.SND_FILENAME | winsound.SND_SYNC)
                print("提示音已播放")
            else:
                print(f"音频文件不存在: {_ap}")
        except Exception as e:
            print(f"提示音播放失败: {e}")
        return

    # === Log viewer ===
    if getattr(sys, 'frozen', False):
        log_dir = os.path.join(os.path.expanduser('~'), '.ai-gen-reimbursement-docs', 'log')
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
        print(f"AI生成项目报账文档 v{_get_version()}")
        return

    # === Init config ===
    if args.init_config:
        config_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config')
        home_cfg = os.path.join(os.path.expanduser('~'), '.ai-gen-reimbursement-docs')
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

        logger.info("请编辑 ~/.ai-gen-reimbursement-docs/.env 填入你的 API Key 后使用")
        return
    # === Load config ===
    api_key = args.api_key or load_api_key()
    base_url = load_base_url()
    model = args.model or load_model_name()

    if api_key:
        os.environ["ANTHROPIC_API_KEY"] = api_key
    if base_url:
        os.environ["ANTHROPIC_BASE_URL"] = base_url
    logger.debug(f"API Key: {'已设置' if api_key else '未设置'}, 端点: {base_url or '默认'}, 模型: {model}")

    # 记录实际使用的配置值
    from ai_gen_reimbursement_docs.config_utils import load_max_tokens, load_business_config, load_cfp_formula
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
        from ai_gen_reimbursement_docs.config_utils import load_business_config
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
            os.environ['AI_REIMBURSEMENT_LOG_DIR'] = log_dir

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
                        raise ConfigError("API Key 未设置")
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
                        generate_cosmic_xlsx_from_md(_default_template_path(), out_xlsx, items)
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
        logger.info(f"  python -m ai_gen_reimbursement_docs.main --docx \"{args.docx}\" --md         # 生成Excel")
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
        logger.info(f"  然后: python -m ai_gen_reimbursement_docs.main --docx \"{docx_path}\" --md")
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
            logger.info(f"  python -m ai_gen_reimbursement_docs.main --docx \"{args.docx}\" --init-md")
            return
        if not args.output:
            args.output = args.md.replace('.md', '.xlsx')
        _setup_docx_logging(args.docx or args.md)
        _section("阶段3: 从MD生成Excel拆分表")
        items = parse_md_to_items(args.md)
        if not items:
            logger.warning("⚠ MD中未解析到COSMIC数据，请先运行 --fill-md 或手动填写表格")
            return
        generate_cosmic_xlsx_from_md(args.template, args.output, items)
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
            generate_cosmic_xlsx_from_md(args.template, args.output, items)
            total_cfp = sum(item.total_cfp() for item in items)
            logger.info(f"\n总计: {len(items)} 功能过程, {total_cfp} CFP")
        else:
            logger.warning("⚠ MD中未解析到COSMIC数据，生成空白模板")
            generate_cosmic_xlsx_from_md(args.template, args.output, [])
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
            generate_cosmic_xlsx_from_md(args.template, args.output, items)
            total_cfp = sum(item.total_cfp() for item in items)
            logger.info(f"\n总计: {len(items)} 功能过程, {total_cfp} CFP")
        elif args.no_llm:
            generate_cosmic_xlsx_from_md(args.template, args.output, [])
            logger.info("生成空白模板（无数据行）")
        return

    # === Mode 6: --from-excel 系列（功能清单 → 全套交付物） ===
    if any([args.gen_basedata, args.gen_fpa, args.gen_cosmic, args.gen_list,
             args.gen_spec, args.gen_all]):
        _section("Excel 功能清单 → 全套交付物")

        # 未指定 --from-excel 时，默认找当前目录下的 功能清单-录入-模板.xlsx 或 功能清单.xlsx
        excel_path = args.from_excel
        if not excel_path:
            import glob
            for name in ["功能清单-录入模板.xlsx", "功能清单.xlsx"]:
                matches = glob.glob(name)
                if matches:
                    excel_path = matches[0]
                    break
            if not excel_path:
                logger.error("未指定 --from-excel，且当前目录未找到 功能清单-录入模板.xlsx")
                return
        if not os.path.exists(excel_path):
            logger.error(f"文件不存在: {excel_path}")
            return

        # 读取工单标题用于创建输出目录（优先 CLI --project-name，其次 md，最后 Excel）
        _p_title = args.project_name.strip() if args.project_name else ''
        if not _p_title:
            _tmp_md_dir = os.path.join(os.path.dirname(os.path.abspath(excel_path)) if not args.output_dir else args.output_dir, 'md')
            _tmp_md_path = os.path.join(_tmp_md_dir, 'gen-basedata-录入文档元数据-模板.md')
            if os.path.exists(_tmp_md_path):
                import re as _re_t
                with open(_tmp_md_path, encoding='utf-8') as _f_t:
                    for _l_t in _f_t:
                        _m_t = _re_t.search(r'工单标题\s*\|\s*(.+?)(?:\s*\||$)', _l_t)
                        if _m_t:
                            _p_title = _m_t.group(1).strip()
                            break
        if not _p_title:
            import re as _re_title
            import openpyxl as _opxl
            try:
                _wb_t = _opxl.load_workbook(excel_path, data_only=True)
                _ws_t = _wb_t['1、工单需求-元数据录入']
                for _r_t in _ws_t.iter_rows(min_row=2, values_only=True):
                    if str(_r_t[0]).strip() == '工单标题':
                        _p_title = str(_r_t[1]).strip() if _r_t[1] else ''
                        break
                _wb_t.close()
            except Exception:
                _p_title = ''
        import re as _re_title
        _safe_t = _re_title.sub(r'[\/:*?"<>|]', '_', _p_title) if _p_title else 'products'
        _excel_dir = os.path.dirname(os.path.abspath(excel_path))
        if args.clean and _p_title:
            import shutil as _su
            _target_dir = os.path.join(_excel_dir, _safe_t)
            if os.path.exists(_target_dir):
                _su.rmtree(_target_dir)
                logger.info(f"已删除输出目录: {_target_dir}")

        out_dir = args.output_dir or os.path.join(_excel_dir, _safe_t)
        doc_dir = os.path.join(out_dir, 'cosmic文档')
        os.makedirs(doc_dir, exist_ok=True)

        log_dir = os.path.join(out_dir, '日志')
        os.makedirs(log_dir, exist_ok=True)
        setup_logging(log_dir, 'AI生成项目报账文档')
        os.environ['AI_REIMBURSEMENT_LOG_DIR'] = log_dir
        logger.info(f"日志目录: {log_dir}")

        # FPA 在根目录，其余在 cosmic文档 下
        fpa_template = os.path.join(out_dir, 'FPA工作量评估.xlsx')
        cosmic_template = os.path.join(doc_dir, '项目功能点拆分表.xlsx')
        require_template = os.path.join(doc_dir, '项目需求清单.xlsx')
        doc_template = os.path.join(doc_dir, '项目需求说明书.docx')

        # 从元数据解析输出文件名（各 sheet 中的 文件名 字段）
        import re as _re
        def _resolve_output_filename(sheet_name: str, default: str,
                                       target_dir: str | None = None) -> str:
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
            _d = target_dir or doc_dir
            return os.path.join(_d, name)
        # 从元数据解析各输出文件名（覆盖默认值）


        # 数据源中间文件路径
        md_dir = os.path.join(out_dir, 'md')
        os.makedirs(md_dir, exist_ok=True)
        tree_md = os.path.join(md_dir, 'gen-basedata-功能清单-模块树.md')
        meta_md_tpl = os.path.join(md_dir, 'gen-basedata-录入文档元数据-模板.md')

        # 是否需要先生成数据源中间文件
        needs_md = not (os.path.exists(meta_md_tpl) and os.path.exists(tree_md))
        if needs_md:
            logger.info("第1步: 生成gen-basedata-功能清单-模块树.md 和 gen-basedata-录入文档元数据-模板.md...")
            generate_md_files(excel_path, md_dir)
        else:
            logger.info("数据源中间文件已存在，跳过生成")

        # 设置 meta_md（优先 AI填充版，无则回退模板）
        meta_md = os.path.join(md_dir, 'gen-basedata-AI填充-录入文档元数据.md')
        if not os.path.exists(meta_md) and os.path.exists(meta_md_tpl):
            meta_md = meta_md_tpl

        # 从元数据解析输出文件名（此时 md 文件已存在）
        cosmic_template = _resolve_output_filename("6、项目功能点拆分表-元数据录入", cosmic_template)
        require_template = _resolve_output_filename("7、项目需求清单-元数据录入", require_template)
        doc_template = _resolve_output_filename("4、项目需求说明书-元数据录入", doc_template)
        from ai_gen_reimbursement_docs.config_utils import load_spec_remind_update_toc
        if load_spec_remind_update_toc():
            _doc_dir, _doc_name = os.path.split(doc_template)
            if not _doc_name.startswith("【提醒】请手动更新整个目录"):
                doc_template = os.path.join(_doc_dir, f"【提醒】请手动更新整个目录 {_doc_name}")
                logger.info(f"需求说明书文件名已添加提醒前缀")
        fpa_sum_md = os.path.join(md_dir, 'gen-fpa-FPA工作量-总和.md')
        meta_filled_md = os.path.join(md_dir, 'gen-basedata-AI填充-录入文档元数据.md')

        # AI 配置
        api_key = args.api_key or load_api_key()
        model = args.model or load_model_name()
        base_url = load_base_url()

        # MD 生成后再检查一次（首次运行模板刚生成，AI填充版还未创建）
        if not os.path.exists(meta_md) and os.path.exists(meta_md_tpl):
            meta_md = meta_md_tpl

        # 验证模块树统计（gen-basedata-功能清单-模块树.md ↔ gen-basedata-录入文档元数据-模板.md ## 9）

        verify_module_tree_stats(tree_md, meta_md)
        # 读取模板路径配置（功能清单-录入模板.xlsx → sheet 8）
        tpl_cfg = read_template_config(excel_path)

        def _tpl(key: str, fallback: str, cli_arg: str = "") -> str:
            """解析模板路径，优先级：CLI > Excel sheet 8 > data/out_templates/。"""
            _source = ""
            if cli_arg:
                cli_val = getattr(args, cli_arg, "").strip()
                if cli_val:
                    if os.path.exists(cli_val):
                        _source = "CLI"
                        logger.info("模板 %s: %s（来源: %s）", key, cli_val, _source)
                        return cli_val
                    logger.warning(f"CLI 指定的模板路径不存在: {cli_val}")
            cfg_path = tpl_cfg.get(key, "")
            if cfg_path:
                _from_proj = os.path.join(_project_root(), cfg_path)
                if os.path.exists(_from_proj):
                    _source = "Sheet 8"
                    logger.info("模板 %s: %s（来源: %s）", key, _from_proj, _source)
                    return _from_proj
                logger.warning("Sheet 8 中 %s 模板路径不存在: %s，请检查配置", key, _from_proj)
            else:
                logger.warning("Sheet 8 中未配置 %s 模板路径，请在 Excel 模板 Sheet「8、各文档-模板路径录入」中补充", key)
            return ""

        fpa_src_template = _tpl('FPA工作量评估-模板', 'FPA工作量评估-输出模板.xlsx', 'fpa_out_template')
        cosmic_src_template = _tpl('项目功能点拆分表-模板', '项目功能点拆分表-输出模板.xlsx', 'cosmic_out_template')
        require_src_template = _tpl('项目需求清单-模板', '项目需求清单-输出模板.xlsx', 'list_out_template')
        doc_src_template = _tpl('项目需求说明书-模板', '项目需求说明书-输出模板.docx', 'spec_out_template')

        # --gen-all: 按依赖顺序自动执行
        if args.gen_all:
            logger.info("全流程模式：按依赖顺序执行...")

            # Step 0: 生成数据源中间文件
            _ensure_basedata(excel_path, md_dir, meta_md, tree_md, meta_md_tpl)
            # AI 填充元数据中的 #AI生成# 标记（由 enable_ai_fill_meta 控制）
            from ai_gen_reimbursement_docs.config_utils import load_enable_ai_fill_meta
            if api_key and (not os.path.exists(meta_filled_md)):
                if load_enable_ai_fill_meta():
                    logger.info("第0步: AI 填充文档元数据...")
                    _ai_fill_meta_md(meta_md_tpl, meta_filled_md, api_key, model, base_url, tree_md=tree_md)
                else:
                    logger.info("enable_ai_fill_meta=false，跳过 AI 填充，直接复制模板")
                    import shutil
                    shutil.copy2(meta_md_tpl, meta_filled_md)
            # 切换到 AI 填充后的版本
            if os.path.exists(meta_filled_md):
                meta_md = meta_filled_md
            fpa_template = _resolve_output_filename("3、FPA工作量评估-元数据录入", fpa_template, target_dir=out_dir)

            # Step 1: FPA（MD → 模板MD → gen-fpa-AI填充-FPA.md → Excel）
            fpa_md = os.path.join(md_dir, 'gen-fpa-FPA-模板.md')
            fpa_filled_md = os.path.join(md_dir, 'gen-fpa-AI填充-FPA.md')
            if not os.path.exists(fpa_template):
                logger.info("第1步：FPA → 模板 MD...")
                init_fpa_template_md(tree_md, meta_md, fpa_md, summary_md_path=fpa_sum_md)
                if api_key:
                    import shutil
                    shutil.copy2(fpa_md, fpa_filled_md)
                    logger.info("第1步：AI 填充 FPA...")
                    ai_fill_fpa_md(fpa_filled_md, meta_md, template_path=fpa_src_template,
                                   api_key=api_key, model=model, base_url=base_url)
                fpa_src = fpa_filled_md if api_key else fpa_md
                fpa_template_file = fpa_src_template
                generate_fpa_xlsx_from_md(fpa_src, meta_md, fpa_template_file, fpa_template)
            elif os.path.exists(fpa_filled_md):
                logger.info("FPA Excel 已存在，重新生成（使用 AI 填充数据）...")
                fpa_template_file = fpa_src_template
                generate_fpa_xlsx_from_md(fpa_filled_md, meta_md, fpa_template_file, fpa_template)
            else:
                logger.info("FPA Excel 已存在，跳过")
            # 送审工作量 = gen-fpa-FPA工作量-总和.md 的值
            fpa_reduced = 0.0
            if os.path.exists(fpa_sum_md):
                import re as _re_fpa3
                with open(fpa_sum_md, encoding='utf-8') as _f3:
                    for _line3 in _f3:
                        _m3 = _re_fpa3.search(r'FPA工作量（人/天）[：:]\s*([\d.]+)', _line3)
                        if _m3:
                            fpa_reduced = float(_m3.group(1))
                            break
            logger.info(f"送审工作量（FPA工作量）: {fpa_reduced}")

            # Step 2: 需求说明书
            if not os.path.exists(doc_template):
                logger.info("第2步：生成 项目需求说明书.docx...")
                spec_md = os.path.join(md_dir, 'gen-spec-spec-功能需求章节-模板.md')
                spec_filled_md = os.path.join(md_dir, 'gen-spec-AI填充-spec-功能需求章节.md')
                if not os.path.exists(spec_filled_md):
                    logger.info("  步骤2a: 生成 spec 模板 MD...")
                    init_spec_template_md(tree_md, meta_md, spec_md)
                    if api_key:
                        logger.info("  步骤2b: AI 填充模块功能描述...")
                        ai_fill_spec_md(spec_md, spec_filled_md,
                                        api_key, model, base_url)
                    else:
                        import shutil
                        shutil.copy2(spec_md, spec_filled_md)
                filled = spec_filled_md if os.path.exists(spec_filled_md) else ""
                generate_spec_docx_from_md(doc_src_template, doc_template, meta_md, tree_md,
                                           filled_md_path=filled)
            else:
                logger.info("项目需求说明书.docx 已存在，跳过")

            # Step 3: COSMIC
            if not os.path.exists(cosmic_template):
                logger.info("第3步：生成 项目功能点拆分表.xlsx...")
                # 使用现有链路：init_base_data_md + ai_fill_cosmic_data_md + generate_cosmic_xlsx_from_md
                logger.info("  步骤3a: 从模块树生成拆分表 MD...")
                from ai_gen_reimbursement_docs.docx_parser import FunctionModule
                modules = _build_modules_from_tree_md(tree_md)
                project = modules[0].name if modules else "项目"

                init_md_path = os.path.join(md_dir, 'gen-cosmic-cosmic模板.md')
                filled_md_path = os.path.join(md_dir, 'gen-cosmic-AI填充cosmic.md')
                export_empty_md(modules, project, init_md_path)

                if api_key:
                    logger.info("  步骤3b: AI 填充 COSMIC 数据...")
                    import shutil
                    shutil.copy2(init_md_path, filled_md_path)
                    from ai_gen_reimbursement_docs.cosmic_llm import load_user_config_from_meta
                    _user_cfg = load_user_config_from_meta(meta_md)
                    fill_md_with_ai(filled_md_path, modules, project, api_key, model, base_url,
                                    **_user_cfg)
                else:
                    logger.warning("  跳过 AI 填充（未设置 API Key）")
                    filled_md_path = init_md_path

                logger.info("  步骤3c: 写入 Excel...")
                items = parse_md_to_items(filled_md_path)
                if items:
                    from ai_gen_reimbursement_docs.excel_writer import generate_cosmic_xlsx_from_md, write_environment_sheet
                    from ai_gen_reimbursement_docs.gen_spec import _parse_meta_md
                    _meta = _parse_meta_md(meta_md)
                    generate_cosmic_xlsx_from_md(cosmic_src_template, cosmic_template, items, meta=_meta)
                    total_cfp = sum(item.total_cfp() for item in items)
                    logger.info(f"  CFP 总和: {total_cfp}")
                    _write_cfp_sum(md_dir, total_cfp)
                    _target = _meta.get("建设目标", "")
                    _necessity = _meta.get("建设必要性", "")
                    if _target or _necessity:
                        write_environment_sheet(
                            cosmic_template, cosmic_template,
                            _p_title, _target, _necessity
                        )
                        logger.info("  环境图 sheet 已更新")
                else:
                    logger.warning("  MD 中无数据")
            else:
                logger.info("项目功能点拆分表.xlsx 已存在，跳过")

            # 送审功能点 = CFP 总和（从 gen-cosmic-CFP-总和.md 读）
            cfp_total = _read_md_value(
                os.path.join(md_dir, 'gen-cosmic-CFP-总和.md'),
                r'CFP 总和[：:]\s*([\d.]+)')
            logger.info(f"送审功能点（CFP总和）: {cfp_total}")

            # Step 4: 需求清单
            if not os.path.exists(require_template):
                logger.info("第4步：生成 项目需求清单.xlsx...")
                generate_list_xlsx_from_md(meta_md, tree_md, require_src_template, require_template,
                                      cfp_total=cfp_total, fpa_reduced=fpa_reduced)
            else:
                logger.info("项目需求清单.xlsx 已存在，跳过")

            _write_combined_ai_log("gen-all")
            _section("全流程完成")
            _play_notify_sound()
            # 输出汇总
            _summary_files = [
                ("FPA 工作量评估", fpa_template),
                ("项目功能点拆分表", cosmic_template),
                ("项目需求清单", require_template),
                ("项目需求说明书", doc_template),
            ]
            print()
            for _label, _path in _summary_files:
                if os.path.exists(_path):
                    _size = os.path.getsize(_path)
                    print(f"  ✅ {_label}: {_path} ({_size/1024:.0f} KB)")
                else:
                    print(f"  ⏭️  {_label}: 跳过（已存在或未生成）")
            print()
            return

        # --gen-basedata
        if args.gen_basedata:
            logger.info("第1步: 生成gen-basedata-功能清单-模块树.md 和 gen-basedata-录入文档元数据-模板.md...")
            generate_md_files(excel_path, md_dir)
            verify_module_tree_stats(tree_md, meta_md_tpl)

            if api_key and (not os.path.exists(meta_filled_md)):
                from ai_gen_reimbursement_docs.config_utils import load_enable_ai_fill_meta
                if load_enable_ai_fill_meta():
                    logger.info("第2步: AI 填充文档元数据...")
                    _ai_fill_meta_md(meta_md_tpl, meta_filled_md, api_key, model, base_url, tree_md=tree_md)
                else:
                    logger.info("enable_ai_fill_meta=false，跳过 AI 填充，直接复制模板")
                    import shutil
                    shutil.copy2(meta_md_tpl, meta_filled_md)
            elif os.path.exists(meta_filled_md):
                logger.info("gen-basedata-AI填充-录入文档元数据.md 已存在，跳过")
            else:
                logger.warning("未设置 API Key，跳过 AI 填充")
                import shutil
                shutil.copy2(meta_md_tpl, meta_filled_md)

            logger.info("数据源中间文件已生成:")
            logger.info(f"  {meta_md_tpl}")
            if os.path.exists(meta_filled_md):
                logger.info(f"  {meta_filled_md}")
            _write_combined_ai_log("gen-basedata")
            _play_notify_sound()
            return

        # --gen-fpa: MD → FPA模板MD → gen-fpa-AI填充-FPA.md → Excel
        if args.gen_fpa:
            _ensure_basedata(excel_path, md_dir, meta_md, tree_md, meta_md_tpl)
            if api_key and (not os.path.exists(meta_filled_md)):
                from ai_gen_reimbursement_docs.config_utils import load_enable_ai_fill_meta
                if load_enable_ai_fill_meta():
                    logger.info("AI 填充文档元数据...")
                    _ai_fill_meta_md(meta_md_tpl, meta_filled_md, api_key, model, base_url, tree_md=tree_md)
                else:
                    logger.info("enable_ai_fill_meta=false，跳过 AI 填充，直接复制模板")
                    import shutil
                    shutil.copy2(meta_md_tpl, meta_filled_md)
            if os.path.exists(meta_filled_md):
                meta_md = meta_filled_md
            fpa_template = _resolve_output_filename("3、FPA工作量评估-元数据录入", fpa_template, target_dir=out_dir)
            fpa_md = os.path.join(md_dir, 'gen-fpa-FPA-模板.md')
            fpa_filled_md = os.path.join(md_dir, 'gen-fpa-AI填充-FPA.md')
            logger.info("第1步: 生成 FPA 模板 MD...")
            init_fpa_template_md(tree_md, meta_md, fpa_md, summary_md_path=fpa_sum_md)

            if api_key:
                logger.info("第2步: AI 填充 FPA 数据...")
                import shutil
                shutil.copy2(fpa_md, fpa_filled_md)
                ai_fill_fpa_md(fpa_filled_md, meta_md, template_path=fpa_src_template,
                               api_key=api_key, model=model, base_url=base_url)
            else:
                fpa_filled_md = fpa_md

            logger.info("第3步: 生成 FPA 工作量评估 Excel...")
            generate_fpa_xlsx_from_md(fpa_filled_md, meta_md, fpa_src_template, fpa_template)
            logger.info(f"FPA工作量评估已生成: {fpa_template}")
            _write_combined_ai_log("gen-fpa")
            _play_notify_sound()
            return

        # --gen-cosmic
        if args.gen_cosmic:
            logger.info("生成 项目功能点拆分表.xlsx...")
            from ai_gen_reimbursement_docs.docx_parser import FunctionModule
            modules = _build_modules_from_tree_md(tree_md)
            project = _read_project_name(meta_md) or (modules[0].name if modules else "项目")

            # 确保数据源存在，提示输入核减后工作量
            _ensure_basedata(excel_path, md_dir, meta_md, tree_md, meta_md_tpl)
            _resolve_fpa_sum(fpa_sum_md)

            init_md_path = os.path.join(md_dir, 'gen-cosmic-cosmic模板.md')
            filled_md_path = os.path.join(md_dir, 'gen-cosmic-AI填充cosmic.md')
            export_empty_md(modules, project, init_md_path)

            if api_key:
                import shutil
                shutil.copy2(init_md_path, filled_md_path)
                from ai_gen_reimbursement_docs.cosmic_llm import load_user_config_from_meta
                _user_cfg = load_user_config_from_meta(meta_md)
                fill_md_with_ai(filled_md_path, modules, project, api_key, model, base_url,
                                **_user_cfg)

                items = parse_md_to_items(filled_md_path)
                if items:
                    from ai_gen_reimbursement_docs.excel_writer import generate_cosmic_xlsx_from_md, write_environment_sheet
                    from ai_gen_reimbursement_docs.gen_spec import _parse_meta_md
                    _meta = _parse_meta_md(meta_md)
                    generate_cosmic_xlsx_from_md(cosmic_src_template, cosmic_template, items, meta=_meta)
                    total_cfp = sum(item.total_cfp() for item in items)
                    logger.info(f"CFP 总和: {total_cfp}")
                    _write_cfp_sum(md_dir, total_cfp)
                    _target = _meta.get("建设目标", "")
                    _necessity = _meta.get("建设必要性", "")
                    if _target or _necessity:
                        write_environment_sheet(
                            cosmic_template, cosmic_template,
                            project, _target, _necessity
                        )
                        logger.info("环境图 sheet 已更新")
                    logger.info(f"项目功能点拆分表已生成: {cosmic_template}")
            else:
                logger.warning("未设置 API Key，无法生成 COSMIC 拆分数据")
            _write_combined_ai_log("gen-cosmic")
            _play_notify_sound()
            return

        # --gen-require
        if args.gen_list:
            _ensure_basedata(excel_path, md_dir, meta_md, tree_md, meta_md_tpl)
            _cfp, _workload = _prompt_list_values(fpa_sum_md)
            generate_list_xlsx_from_md(meta_md, tree_md, require_src_template, require_template,
                                  cfp_total=_cfp, fpa_reduced=_workload)
            logger.info(f"项目需求清单已生成: {require_template}")
            _write_combined_ai_log("gen-list")
            _play_notify_sound()
            return

        # --gen-spec
        if args.gen_spec:
            # 确保基础数据（含 AI 填充元数据）
            _ensure_basedata(excel_path, md_dir, meta_md, tree_md, meta_md_tpl)
            if api_key and (not os.path.exists(meta_filled_md)):
                from ai_gen_reimbursement_docs.config_utils import load_enable_ai_fill_meta
                if load_enable_ai_fill_meta():
                    logger.info("AI 填充文档元数据...")
                    _ai_fill_meta_md(meta_md_tpl, meta_filled_md, api_key, model, base_url, tree_md=tree_md)
            if os.path.exists(meta_filled_md):
                meta_md = meta_filled_md

            spec_md = os.path.join(md_dir, 'gen-spec-spec-功能需求章节-模板.md')
            spec_filled_md = os.path.join(md_dir, 'gen-spec-AI填充-spec-功能需求章节.md')
            if not os.path.exists(spec_filled_md):
                logger.info("生成 spec 模板 MD...")
                init_spec_template_md(tree_md, meta_md, spec_md)
                if api_key:
                    logger.info("AI 填充模块功能描述...")
                    ai_fill_spec_md(spec_md, spec_filled_md,
                                    api_key, model, base_url)
                else:
                    import shutil
                    shutil.copy2(spec_md, spec_filled_md)
            filled = spec_filled_md if os.path.exists(spec_filled_md) else ""

            logger.info("生成 项目需求说明书.docx...")
            generate_spec_docx_from_md(doc_src_template, doc_template, meta_md, tree_md,
                                       filled_md_path=filled)
            logger.info(f"项目需求说明书已生成: {doc_template}")
            _write_combined_ai_log("gen-spec")
            _play_notify_sound()
            return

    # === No valid mode ===
    # Batch mode (above) handles the default case when no args given
    pass


def _project_root() -> str:
    """Get project root dir (works for both source and PyInstaller exe)."""
    if getattr(sys, 'frozen', False):
        # exe 所在目录（模板放同级 data/out_templates/ 下）
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(__file__))


def _default_template_path() -> str:
    """Return template path from ~/.ai-gen-reimbursement-docs/business_rules.yaml or default."""
    rules_path = os.path.join(os.path.expanduser('~'), '.ai-gen-reimbursement-docs', 'business_rules.yaml')
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
    # 优先 data/out_templates/项目功能点拆分表-输出模板.xlsx，回退 data/项目功能点拆分表.xlsx
    tpl = os.path.join(_project_root(), 'data', 'out_templates', '项目功能点拆分表-输出模板.xlsx')
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
