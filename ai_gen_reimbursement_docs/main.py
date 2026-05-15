"""AI生成项目报账文档 - CLI入口

推荐工作流（Excel 功能清单）:
  python -m ai_gen_reimbursement_docs.main --from-excel 功能清单.xlsx --gen-all

分步执行:
  python -m ai_gen_reimbursement_docs.main --from-excel 功能清单.xlsx --gen-basedata
  python -m ai_gen_reimbursement_docs.main --from-excel 功能清单.xlsx --gen-fpa
  python -m ai_gen_reimbursement_docs.main --from-excel 功能清单.xlsx --gen-cosmic
  python -m ai_gen_reimbursement_docs.main --from-excel 功能清单.xlsx --gen-list
  python -m ai_gen_reimbursement_docs.main --from-excel 功能清单.xlsx --gen-spec
"""

import argparse
import logging
import os
import shutil
import sys
from datetime import datetime

from ai_gen_reimbursement_docs.exceptions import ConfigError
from ai_gen_reimbursement_docs.models import FunctionModule
from ai_gen_reimbursement_docs.config_utils import load_api_key, load_base_url, load_model_name, load_business_config
from ai_gen_reimbursement_docs.md_handler import (
    export_empty_md,
    export_filled_md,
    parse_md_to_items,
    fill_md_with_ai,
)
from ai_gen_reimbursement_docs.gen_spec import generate_spec_docx_from_md, ai_fill_spec_md, init_spec_template_md
from ai_gen_reimbursement_docs.gen_xlsx import generate_fpa_xlsx_from_md, generate_list_xlsx_from_md
from ai_gen_reimbursement_docs.gen_xlsx import init_fpa_template_md, ai_fill_fpa_md




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


logger = logging.getLogger('ai_gen_reimbursement_docs')


def _get_version() -> str:
    """Read version from pyproject.toml (single source of truth)."""
    import tomllib
    try:
        # 先尝试项目根目录（开发模式），再尝试 _MEIPASS（PyInstaller 打包）
        toml_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'pyproject.toml')
        if not os.path.exists(toml_path):
            toml_path = os.path.join(project_root(), 'pyproject.toml')
        with open(toml_path, 'rb') as f:
            return tomllib.load(f)['project']['version']
    except Exception:
        return "unknown"


def _section(title: str):
    """Print a section header to both console and log."""
    sep = "=" * 60
    logger.info(sep)
    logger.info(title)
    logger.info(sep)
    logger.debug("--- section start ---")


def build_modules_from_tree_md(md_path: str) -> list[FunctionModule]:
    """从 功能清单-模块树.md 的表格格式构建 FunctionModule 列表。

    自动去重并构建 L1→L2→L3 层级，功能过程作为 L3 的 children。
    """
    from ai_gen_reimbursement_docs.excel_source import parse_module_tree_md
    rows = parse_module_tree_md(md_path)

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


def read_project_name(meta_md_path: str) -> str:
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


def resolve_fpa_sum(fpa_sum_md_path: str) -> float:
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


def read_md_value(path: str, pattern: str) -> float:
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


def prompt_list_values(fpa_sum_md_path: str) -> tuple[float, float]:
    """提示用户输入送审功能点和送审工作量（gen-list 使用）。

    从 gen-cosmic-CFP-总和.md / gen-fpa-FPA工作量-总和.md 读取默认值。
    返回 (cfp_total, fpa_reduced)。
    """
    _cfp_raw = read_md_value(
        os.path.join(os.path.dirname(fpa_sum_md_path), 'gen-cosmic-CFP-总和.md'),
        r'CFP 总和[：:]\s*([\d.]+)')
    _fpa_raw = read_md_value(fpa_sum_md_path,
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


def write_cfp_sum(md_dir: str, total: float) -> None:
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


def _build_parser() -> argparse.ArgumentParser:
    """构建 CLI 参数解析器。"""
    parser = argparse.ArgumentParser(
        description="AI生成项目报账文档 — 从功能清单自动生成全套报账交付物",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""工作流示例:

      # 初始化API Key配置
      python -m ai_gen_reimbursement_docs.main --init-config

      # Excel 功能清单 → 全套交付物
      python -m ai_gen_reimbursement_docs.main --from-excel 功能清单.xlsx --gen-all

      # 分步执行
      python -m ai_gen_reimbursement_docs.main --from-excel 功能清单.xlsx --gen-basedata
      python -m ai_gen_reimbursement_docs.main --from-excel 功能清单.xlsx --gen-fpa
      python -m ai_gen_reimbursement_docs.main --from-excel 功能清单.xlsx --gen-cosmic
      python -m ai_gen_reimbursement_docs.main --from-excel 功能清单.xlsx --gen-list
      python -m ai_gen_reimbursement_docs.main --from-excel 功能清单.xlsx --gen-spec
        """
    )

    # === CLI Arguments ===
    parser.add_argument('--api-key', '-k', default='',
                        help='API Key（默认从 .env 读取）')

    parser.add_argument('--model', '-m', default='',
                        help='模型名称（默认从 .env 读取，否则 deepseek-v4-flash）')

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
    _init_global_logging()

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
    from ai_gen_reimbursement_docs.config_utils import config_dir
    logger.info(f"配置文件目录: {config_dir()}")

    # 配置迁移（新模板键自动追加到用户配置文件）
    from ai_gen_reimbursement_docs.config_utils import migrate_config
    migrate_config()

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

    logger.debug(f"API Key: {'已设置' if api_key else '未设置'}, 端点: {base_url or '默认'}, 模型: {model}")

    # 记录实际使用的配置值
    from ai_gen_reimbursement_docs.config_utils import load_max_tokens, load_business_config, load_cfp_formula
    logger.info(f"配置: MAX_TOKENS={load_max_tokens()}, CFP公式={load_cfp_formula()}")
    biz_cfg = load_business_config()
    logger.info(f"配置: REGENERATE_MD={biz_cfg['regenerate_md']}, ENABLE_AI_GENERATE_COSMIC={biz_cfg['enable_ai_generate_cosmic']}")
    # === from-excel 管道（委托至 pipeline.py） ===
    if any([args.gen_basedata, args.gen_fpa, args.gen_cosmic, args.gen_list,
             args.gen_spec, args.gen_all]):

        # 查找输入文件
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

        # 输出目录
        import re as _re_po
        excel_dir = os.path.dirname(os.path.abspath(excel_path))
        if args.output_dir:
            out_dir = args.output_dir
        elif args.project_name:
            safe = _re_po.sub(r'[\/:*?"<>|]', '_', args.project_name)
            out_dir = os.path.join(excel_dir, safe)
        else:
            out_dir = excel_dir

        if args.clean and args.project_name:
            safe = _re_po.sub(r'[\/:*?"<>|]', '_', args.project_name)
            target = os.path.join(excel_dir, safe)
            if os.path.exists(target):
                shutil.rmtree(target)
                logger.info(f"已删除输出目录: {target}")

        # 按任务日志
        log_dir = os.path.join(out_dir, '日志')
        os.makedirs(log_dir, exist_ok=True)
        setup_logging(log_dir, 'AI生成项目报账文档')
        os.environ['AI_REIMBURSEMENT_LOG_DIR'] = log_dir

        # 解析模式
        mode_map = {
            'gen_all': 'gen-all', 'gen_basedata': 'gen-basedata',
            'gen_fpa': 'gen-fpa', 'gen_cosmic': 'gen-cosmic',
            'gen_list': 'gen-list', 'gen_spec': 'gen-spec',
        }
        mode = 'gen-all'
        for arg_key, mode_val in mode_map.items():
            if getattr(args, arg_key, False):
                mode = mode_val
                break

        # 收集 CLI 模板覆盖
        templates = {}
        for key, arg_name in [('fpa', 'fpa_out_template'), ('cosmic', 'cosmic_out_template'),
                              ('list', 'list_out_template'), ('spec', 'spec_out_template')]:
            val = getattr(args, arg_name, '').strip()
            if val and os.path.exists(val):
                templates[key] = val

        # 交互式参数：在调 pipeline 之前提示用户（仅 gen-cosmic / gen-list）
        _fpa_reduced = None
        _cfp_total = None
        if mode in ('gen-cosmic', 'gen-all'):
            from ai_gen_reimbursement_docs.config_utils import load_fpa_reduced_use_workload
            if not load_fpa_reduced_use_workload():
                _fpa_reduced = resolve_fpa_sum(
                    os.path.join(out_dir, 'md', 'gen-fpa-FPA工作量-总和.md'))
        if mode in ('gen-list',):
            _cfp_total, _fpa_reduced = prompt_list_values(
                os.path.join(out_dir, 'md', 'gen-fpa-FPA工作量-总和.md'))

        # 调用共享 pipeline
        from ai_gen_reimbursement_docs.pipeline import run_pipeline
        result = run_pipeline(
            mode=mode,
            file_path=excel_path,
            output_dir=out_dir,
            api_key=api_key,
            model=model,
            base_url=base_url,
            project_name=args.project_name,
            templates=templates or None,
            fpa_reduced=_fpa_reduced,
            cfp_total=_cfp_total,
        )

        # 输出汇总
        _section("完成")
        _summary_files = [
            ("FPA 工作量评估", result.fpa_xlsx),
            ("项目功能点拆分表", result.cosmic_xlsx),
            ("项目需求清单", result.require_xlsx),
            ("项目需求说明书", result.spec_docx),
        ]
        print()
        for _label, _path in _summary_files:
            if _path and os.path.exists(_path):
                _size = os.path.getsize(_path)
                print(f"  \u2705 {_label}: {_path} ({_size/1024:.0f} KB)")
            else:
                print(f"  \u23ed\ufe0f  {_label}: 跳过（已存在或未生成）")
        print()

        _write_combined_ai_log(mode)
        _play_notify_sound()
        return



def project_root() -> str:
    """Get project root dir (works for both source and PyInstaller exe)."""
    if getattr(sys, 'frozen', False):
        # exe 所在目录（模板放同级 data/out_templates/ 下）
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(__file__))


if __name__ == '__main__':
    # 清理字节码缓存
    _pycache = os.path.join(os.path.dirname(__file__), '__pycache__')
    if os.path.isdir(_pycache):
        shutil.rmtree(_pycache, ignore_errors=True)

    _exit_code = 0
    try:
        main()
    except Exception as _e:
        _exit_code = 1
        # 用户终端：简洁消息
        print(f"\n  错误: {_e}", file=sys.stderr)
        # 日志文件：完整堆栈（若 logger 已初始化）
        try:
            logger.debug("未捕获异常", exc_info=True)
        except Exception:
            pass
    if getattr(sys, 'frozen', False):
        input("\n按 Enter 键退出...")
    sys.exit(_exit_code)
