"""COSMIC 功能点拆分工具 - CLI入口

推荐工作流（MD中间件模式）:
  1. python -m cosmic_tool.main --docx 需求书.docx --init-md 拆分表.md
  2. python -m cosmic_tool.main --fill-md 拆分表.md
     (编辑拆分表.md 人工审核修正)
  3. python -m cosmic_tool.main --md 拆分表.md --template 模板.xlsx --output 结果.xlsx

快捷模式（一键全流程）:
  python -m cosmic_tool.main --docx "需求书.docx" --template "模板.xlsx" --output "结果.xlsx" --all

一键直出（跳过MD中间文件）:
  python -m cosmic_tool.main --docx 需求书.docx --template 模板.xlsx --output 结果.xlsx

默认批处理（无参数时自动处理当前目录所有docx）:
  python -m cosmic_tool.main
"""

import argparse
import logging
import os
import shutil
from datetime import datetime

from cosmic_tool.docx_parser import build_module_tree, print_tree, get_project_name
from cosmic_tool.cosmic_llm import generate_cosmic_items
from cosmic_tool.excel_writer import write_to_template
from cosmic_tool.config_utils import load_api_key, load_base_url, load_model_name
from cosmic_tool.md_handler import (
    export_empty_md,
    export_filled_md,
    parse_md_to_items,
    fill_md_with_ai,
)

# 启动时自动清理 cosmic_tool 自身的字节码缓存，避免代码修改后缓存过期问题
_pycache = os.path.join(os.path.dirname(__file__), '__pycache__')
if os.path.isdir(_pycache):
    shutil.rmtree(_pycache, ignore_errors=True)


def setup_logging(log_dir: str = ""):
    """配置日志：控制台 + 日志文件（可指定目录）。"""
    if not log_dir:
        log_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 'log'
        )
    os.makedirs(log_dir, exist_ok=True)

    main_log = os.path.join(log_dir, 'cosmic_tool.log')
    run_stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    run_log = os.path.join(log_dir, f'run_{run_stamp}.log')

    logger = logging.getLogger('cosmic_tool')
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    fmt = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    fh = logging.FileHandler(main_log, encoding='utf-8', mode='a')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    rh = logging.FileHandler(run_log, encoding='utf-8', mode='w')
    rh.setLevel(logging.DEBUG)
    rh.setFormatter(fmt)
    logger.addHandler(rh)

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(ch)

    return logger, run_log


logger, _run_log_path = setup_logging()


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


def _section(title: str):
    """Print a section header to both console and log."""
    sep = "=" * 60
    logger.info(sep)
    logger.info(title)
    logger.info(sep)
    logger.debug("--- section start ---")


def main():
    parser = argparse.ArgumentParser(
        description="COSMIC 功能点拆分工具 - 从需求说明书自动生成功能点拆分表（无参数时自动批量处理当前目录docx）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
工作流示例:

  # (推荐) MD中间件模式：docx → MD → 编辑MD → Excel
  python -m cosmic_tool.main --docx 需求书.docx --init-md 拆分表.md
  python -m cosmic_tool.main --fill-md 拆分表.md
  python -m cosmic_tool.main --md 拆分表.md --template 模板.xlsx --output 结果.xlsx

  # (快捷) 一键直出：docx → LLM → Excel
  python -m cosmic_tool.main --docx 需求书.docx --template 模板.xlsx --output 结果.xlsx

  # (快捷) 一键全流程：docx → MD → AI填充 → Excel（含中间MD文件）
  python -m cosmic_tool.main --docx "需求书.docx" --template "模板.xlsx" --output "结果.xlsx" --all

  # 仅查看模块树
  python -m cosmic_tool.main --docx 需求书.docx --show-tree

  # 初始化API Key配置
  python -m cosmic_tool.main --init-config
        """
    )

    # === CLI Arguments ===
    parser.add_argument('--docx', '-d', default='',
                        help='需求说明书 .docx 文件路径')

    parser.add_argument('--init-md', nargs='?', const='', default=None,
                        help='生成空白MD中间文件；省略路径时从docx自动命名')

    parser.add_argument('--fill-md', nargs='?', const='', default=None,
                        help='AI填充MD中的COSMIC数据；省略路径时从docx自动命名')

    parser.add_argument('--md', nargs='?', const='', default=None,
                        help='从MD文件生成Excel；省略路径时从docx自动查找')

    parser.add_argument('--template', '-t', default='',
                        help='功能点拆分表 .xlsx 模板文件路径（默认 data/template.xlsx）')

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

    parser.add_argument('--all', action='store_true',
                        help='一键全流程: docx → MD → AI填充 → Excel')

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

    # 配置迁移（新模板键自动追加到用户配置文件）
    from cosmic_tool.config_utils import _migrate_config
    _migrate_config()

    # === Log viewer ===
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
        home_cfg = os.path.join(os.path.expanduser('~'), '.cosmic-tool')
        os.makedirs(home_cfg, exist_ok=True)
        env_path = os.path.join(home_cfg, '.env')
        sys_path = os.path.join(home_cfg, 'system_config.yaml')
        biz_path = os.path.join(home_cfg, 'business_rules.yaml')
        if os.path.exists(env_path):
            logger.info("配置文件已存在，跳过创建")
            return
        # 创建 AI 模型配置
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write("""# COSMIC 功能点拆分工具 — AI 模型配置
ANTHROPIC_API_KEY=your_api_key_here
ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
ANTHROPIC_MODEL=deepseek-v4-flash
""")
        # 创建通用配置
        with open(sys_path, 'w', encoding='utf-8') as f:
            f.write("""# COSMIC 功能点拆分工具 — 通用配置
max_tokens: 16000
regenerate_md: false
regenerate_filled: false
regenerate_excel: false
regenerate_all: false
enable_ai: true
""")
        # 创建业务规则配置
        with open(biz_path, 'w', encoding='utf-8') as f:
            f.write("""# COSMIC 功能点拆分工具 — 业务规则配置
cfp_formula: "IF(L{row}=\\"新增\\",1,IF(L{row}=\\"复用\\",1/3,0))"
user_initiator_default: 操作员
user_receiver_default: 地市后台
user_initiator_rules: {}
user_receiver_rules:
  用户: 用户前台
template_path: data/template.xlsx
""")
        logger.info(f"配置文件已创建至用户主目录:")
        logger.info(f"  AI 模型: {env_path}")
        logger.info(f"  通用配置: {sys_path}")
        logger.info(f"  业务规则: {biz_path}")
        logger.info("请编辑 .env 填入你的 API Key 后使用")
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

    # === Show tree ===
    if args.docx and args.show_tree:
        modules = build_module_tree(args.docx)
        project = get_project_name(args.docx)
        logger.info(f"项目名称: {project}")
        logger.info(f"模块总数: {len(modules)}")
        print_tree(modules)
        logger.debug("show-tree completed")
        return

    # === Batch mode: 处理当前目录下所有 docx（默认行为） ===
    if not any([args.docx, args.init_md is not None, args.fill_md is not None,
                args.md is not None, args.all, args.show_tree,
                args.init_config, args.log]):
        _section("批量处理模式")
        import glob
        docx_files = glob.glob("*.docx")
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
        logger.info(f"  配置: ENABLE_AI={biz_config['enable_ai']}, "
                    f"REGENERATE_ALL={biz_config['regenerate_all']}")

        for idx, docx_path in enumerate(docx_files, 1):
            base_name = os.path.splitext(docx_path)[0]
            out_dir = os.path.abspath(base_name)
            md_dir = os.path.join(out_dir, 'md')
            log_dir = os.path.join(out_dir, 'log')

            xlsx_path = _auto_output_path(docx_path)
            out_xlsx = os.path.join(out_dir, os.path.basename(xlsx_path))
            md_base = os.path.join(md_dir, '拆分表.md')
            md_filled = os.path.join(md_dir, '拆分表_已填充.md')

            os.makedirs(md_dir, exist_ok=True)
            os.makedirs(log_dir, exist_ok=True)

            logger.info(f"  [{idx}/{total}] {docx_path}")
            logger.info(f"  {'-' * 40}")

            # Reconfigure logging and AI response paths for this docx
            setup_logging(log_dir)
            os.environ['COSMIC_LOG_DIR'] = log_dir

            try:
                # --- Stage 1: 生成空白 MD ---
                if os.path.exists(md_base) and not biz_config['regenerate_md']:
                    logger.info(f"  空白MD已存在，跳过（REGENERATE_MD=false）")
                    modules = build_module_tree(docx_path)
                    project = get_project_name(docx_path)
                else:
                    modules = build_module_tree(docx_path)
                    project = get_project_name(docx_path)
                    export_empty_md(modules, project, md_base)
                    logger.info(f"  空白MD已生成: {md_base}")

                # --- Stage 2: AI 填充 ---
                if not biz_config['enable_ai']:
                    logger.info(f"  AI已禁用（ENABLE_AI=false），跳过填充")
                elif os.path.exists(md_filled) and not biz_config['regenerate_filled']:
                    logger.info(f"  已填充MD已存在，跳过（REGENERATE_FILLED=false）")
                else:
                    if not api_key:
                        raise ValueError("API Key 未设置")
                    shutil.copy2(md_base, md_filled)
                    fill_md_with_ai(md_filled, modules, project, api_key, model, base_url)
                    logger.info(f"  AI填充完成: {md_filled}")

                # --- Stage 3: 生成 Excel ---
                if os.path.exists(out_xlsx) and not biz_config['regenerate_excel']:
                    logger.info(f"  Excel已存在，跳过（REGENERATE_EXCEL=false）")
                else:
                    # 优先用已填充的MD，没有则用空白MD
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

        # Restore default logging
        setup_logging()
        _section("批量处理完成")
        logger.info(f"总数: {total}，Excel生成成功: {len(excel_ok)}，处理未生成Excel: {len(processed_no_excel)}，失败: {len(failed)}")
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
        _section("阶段1: 解析需求说明书 → 生成空白MD")
        modules = build_module_tree(args.docx)
        project = get_project_name(args.docx)
        # Statistics
        l1_count = len([m for m in modules if m.level == 1])
        l2_count = len([m for m in modules if m.level == 2])
        l3_count = len([m for m in modules if m.level == 3])
        proc_count = sum(len(m.children) for m in modules if m.level == 3 and m.children)
        logger.info(f"模块层级: {l1_count} 个一级 / {l2_count} 个二级 / {l3_count} 个三级")
        logger.info(f"功能过程: {proc_count} 个")
        export_empty_md(modules, project, args.init_md)
        logger.info(f"\n下一步:")
        logger.info(f"  python -m cosmic_tool.main --docx \"{args.docx}\" --fill-md    # AI填充")
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
            logger.error("MD文件不存在，请先运行阶段1生成空白MD：")
            logger.info(f"  python -m cosmic_tool.main --docx \"{args.docx}\" --init-md")
            return
        if not os.path.exists(args.fill_md):
            logger.error(f"MD文件不存在: {args.fill_md}")
            logger.info("请先运行阶段1生成空白MD")
            return
        docx_path = args.docx or _find_docx_from_md(args.fill_md)
        if not docx_path:
            parser.error("--fill-md 需要 --docx 或将MD放在docx同目录下")

        # 生成输出路径：在原名基础上加 _已填充
        if args.fill_md.endswith('.md'):
            output_md = args.fill_md[:-3] + '_已填充.md'
        else:
            output_md = args.fill_md + '_已填充.md'

        # 复制原MD → 填充副本
        shutil.copy2(args.fill_md, output_md)
        logger.info(f"源文件: {args.fill_md}")
        logger.info(f"副本文件: {output_md}")

        modules = build_module_tree(docx_path)
        project = get_project_name(docx_path)
        # 统计实际功能过程数（来自docx，非空白MD）
        l3_modules = [m for m in modules if m.level == 3]
        proc_count = sum(len(m.children) for m in l3_modules if m.children)
        logger.info(f"待AI填充: {len(l3_modules)} 个模块, {proc_count} 个功能过程")
        fill_md_with_ai(output_md, modules, project, api_key, model, base_url)
        logger.info(f"\n下一步:")
        logger.info(f"  编辑 {output_md} 人工审核修正")
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
                filled = _auto_md_path(args.docx, '_拆分表_已填充')
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
            logger.info(f"请先运行阶段1和阶段2生成MD文件：")
            logger.info(f"  python -m cosmic_tool.main --docx \"{args.docx}\" --init-md")
            logger.info(f"  python -m cosmic_tool.main --docx \"{args.docx}\" --fill-md")
            return
        if not args.output:
            args.output = args.md.replace('.md', '.xlsx')
        _section("阶段3: 从MD生成Excel拆分表")
        items = parse_md_to_items(args.md)
        if not items:
            logger.warning("⚠ MD中未解析到COSMIC数据，请先运行 --fill-md 或手动填写表格")
            return
        write_to_template(args.template, args.output, items)
        total_cfp = sum(item.total_cfp() for item in items)
        logger.info(f"\n总计: {len(items)} 功能过程, {total_cfp} CFP")
        logger.info(f"输出: {os.path.abspath(args.output)}")
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
        base_md = args.output.replace('.xlsx', '_拆分表.md')
        filled_md = base_md.replace('.md', '_已填充.md')

        # Stage 1: docx → blank MD
        _section("阶段1: 解析需求说明书 → 生成空白MD")
        modules = build_module_tree(args.docx)
        project = get_project_name(args.docx)
        l1_count = len([m for m in modules if m.level == 1])
        l2_count = len([m for m in modules if m.level == 2])
        l3_count = len([m for m in modules if m.level == 3])
        proc_count = sum(len(m.children) for m in modules if m.level == 3 and m.children)
        logger.info(f"模块层级: {l1_count} 个一级 / {l2_count} 个二级 / {l3_count} 个三级")
        logger.info(f"功能过程: {proc_count} 个")
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
        logger.info(f"中间文件: {base_md}, {filled_md}")
        logger.info(f"输出: {os.path.abspath(args.output)}")
        return

    # === Mode 5: Direct docx → LLM → Excel (one shot) ===
    if args.docx:
        if not args.template:
            args.template = _default_template_path()
        if not args.output:
            args.output = _auto_output_path(args.docx)
        _section("阶段1: 解析需求说明书")
        modules = build_module_tree(args.docx)
        project = get_project_name(args.docx)
        logger.info(f"项目: {project}")
        logger.info(f"模块: {len(modules)}")
        print_tree(modules)

        items = []
        if not args.no_llm:
            if not api_key:
                logger.warning("⚠ 未设置 API Key。请先运行 --init-config 或设置环境变量")
                return
            _section("阶段2: AI生成COSMIC功能点拆分")
            logger.info(f"模型: {model}")
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
            logger.info(f"输出: {os.path.abspath(args.output)}")
        elif args.no_llm:
            write_to_template(args.template, args.output, [])
            logger.info("生成空白模板（无数据行）")
        return

    # === No valid mode ===
    # Batch mode (above) handles the default case when no args given
    pass


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
                    yaml_path = os.path.join(
                        os.path.dirname(os.path.dirname(__file__)), yaml_path
                    )
                if os.path.exists(yaml_path):
                    return yaml_path
        except Exception:
            pass
    return os.path.join(os.path.dirname(__file__), '..', 'data', 'template.xlsx')


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
        if f.endswith('.docx'):
            return os.path.join(md_dir, f)
    parent = os.path.dirname(md_dir)
    for f in os.listdir(parent):
        if f.endswith('.docx'):
            return os.path.join(parent, f)
    return ""


if __name__ == '__main__':
    main()
