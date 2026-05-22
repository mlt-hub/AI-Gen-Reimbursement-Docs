"""AI生成项目报账文档 - CLI入口"""

import argparse
import logging
import os
import re
import shutil
import sys

from ai_gen_reimbursement_docs.config_utils import load_api_key, load_base_url, load_model_name

logger = logging.getLogger('ai_gen_reimbursement_docs')


def _get_version() -> str:
    """Read version from pyproject.toml."""
    import tomllib
    try:
        root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        toml_path = os.path.join(root, 'pyproject.toml')
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


def _start_web_ui(root: str) -> None:
    """启动 Web UI 服务器并打开浏览器。"""
    try:
        import uvicorn
        import webbrowser
    except ImportError:
        print("Web UI 需要安装 uvicorn: pip install uvicorn[standard]")
        return

    host = "127.0.0.1"
    port = 8000
    webbrowser.open(f"http://{host}:{port}")
    print(f"Web UI 已启动: http://{host}:{port}")
    # exe 模式用 exe 所在目录（web_app/ 外挂在该目录），源码模式用项目根
    if getattr(sys, 'frozen', False):
        app_dir = os.path.dirname(sys.executable)
    else:
        app_dir = root
    uvicorn.run("web_app.server:app", host=host, port=port,
                app_dir=app_dir, log_level="info")


def _auto_detect_and_run(api_key: str, model: str, base_url: str) -> None:
    """零参数模式：在当前目录搜索符合规范的功能清单 xlsx，找到唯一匹配则自动全流程执行。"""
    import glob

    from ai_gen_reimbursement_docs.excel_source import is_valid_input_xlsx
    from ai_gen_reimbursement_docs.pipeline import _try_read_project_name

    xlsx_files = glob.glob("*.xlsx")
    if not xlsx_files:
        print("当前目录未找到任何 .xlsx 文件")
        print("使用方式: ard --from-excel <功能清单路径> --gen-all")
        return

    valid = [f for f in xlsx_files if is_valid_input_xlsx(f)]

    if len(valid) == 0:
        print(f"当前目录找到 {len(xlsx_files)} 个 .xlsx 文件，但都不符合功能清单录入文档规范")
        print(f"文件列表: {', '.join(xlsx_files)}")
        print("使用方式: ard --from-excel <功能清单路径> --gen-all")
        return

    if len(valid) > 1:
        print(f"当前目录找到 {len(valid)} 个符合规范的功能清单文件，请指定其中一个:")
        for f in valid:
            print(f"  ard --from-excel \"{f}\" --gen-all")
        return

    # 唯一匹配，自动执行
    excel_path = valid[0]
    print(f"检测到功能清单: {excel_path}")

    project_name = _try_read_project_name(excel_path)
    if project_name:
        print(f"项目名称: {project_name}")

    print("自动执行全流程...")
    _run_pipeline_with_args(excel_path, api_key, model, base_url, project_name)


def _run_pipeline_with_args(
    excel_path: str,
    api_key: str = "",
    model: str = "",
    base_url: str = "",
    project_name: str = "",
) -> None:
    """执行管道并输出摘要（零参数模式复用）。"""
    from ai_gen_reimbursement_docs.cli.logging import setup_logging
    from ai_gen_reimbursement_docs.pipeline import run_pipeline_simple

    result = run_pipeline_simple(
        mode='gen-all',
        file_path=excel_path,
        api_key=api_key,
        model=model,
        base_url=base_url,
        project_name=project_name,
    )

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
            print(f"  ✅ {_label}: {_path} ({_size/1024:.0f} KB)")
        else:
            print(f"  ⏭️  {_label}: 跳过（已存在或未生成）")
    print()

    from ai_gen_reimbursement_docs.cli.logging import write_combined_ai_log
    from ai_gen_reimbursement_docs.cli.notify import play_notify_sound
    write_combined_ai_log('gen-all')
    play_notify_sound()


def _auto_init_config(root: str) -> None:
    """exe 首次运行自动初始化用户配置文件（不覆盖已有配置）。"""
    import shutil

    home_cfg = os.path.join(os.path.expanduser('~'), '.ai-gen-reimbursement-docs')
    cfg_dir = os.path.join(root, 'config')
    if not os.path.isdir(cfg_dir):
        return
    os.makedirs(home_cfg, exist_ok=True)
    pairs = [
        (os.path.join(cfg_dir, '.env.example'), os.path.join(home_cfg, '.env')),
        (os.path.join(cfg_dir, 'system_config.yaml.example'), os.path.join(home_cfg, 'system_config.yaml')),
        (os.path.join(cfg_dir, 'business_rules.yaml.example'), os.path.join(home_cfg, 'business_rules.yaml')),
    ]
    for src, dst in pairs:
        if not os.path.exists(src):
            continue
        if os.path.exists(dst):
            continue
        shutil.copy2(src, dst)
        print(f"已自动创建配置文件: {dst}")


def _read_l3_descriptions_from_excel(excel_path: str) -> list[str]:
    """从 Excel 功能清单中读取三级模块整体功能描述（去重，处理合并单元格继承）。"""
    from ai_gen_reimbursement_docs.config_utils import load_sheet_names
    import openpyxl

    _s = load_sheet_names()
    wb = openpyxl.load_workbook(excel_path, data_only=True)
    ws = wb[_s["func_content"]]

    descriptions: list[str] = []
    seen: set[str] = set()
    prev_desc = ""
    for row in ws.iter_rows(min_row=2, values_only=True):
        desc = str(row[5]).strip() if len(row) > 5 and row[5] else ""
        if not desc:
            desc = prev_desc  # 合并单元格继承上一行
        else:
            prev_desc = desc
        if desc and desc not in seen:
            seen.add(desc)
            descriptions.append(desc)
    wb.close()
    return descriptions


def _read_meta_field_value(excel_path: str, field_key: str) -> tuple[str, str]:
    """在所有元数据 sheet 中搜索指定字段的值，返回 (sheet名, 值)。"""
    from ai_gen_reimbursement_docs.config_utils import load_sheet_names
    import openpyxl

    _s = load_sheet_names()
    wb = openpyxl.load_workbook(excel_path, data_only=True)
    for sheet_key in ["meta", "fpa_meta", "spec_meta", "cosmic_meta", "require_meta"]:
        sheet_name = _s.get(sheet_key, "")
        if not sheet_name or sheet_name not in wb.sheetnames:
            continue
        ws = wb[sheet_name]
        for row in ws.iter_rows(min_row=2, values_only=True):
            key = str(row[0]).strip() if row[0] else ""
            val = str(row[1]).strip() if len(row) > 1 and row[1] else ""
            if key == field_key:
                wb.close()
                return sheet_name, val
    wb.close()
    return "", ""


def _read_meta_all_keys(excel_path: str) -> list[tuple[str, str]]:
    """列出所有元数据 sheet 的字段 key，返回 [(sheet名, key), ...]。"""
    from ai_gen_reimbursement_docs.config_utils import load_sheet_names
    import openpyxl

    _s = load_sheet_names()
    wb = openpyxl.load_workbook(excel_path, data_only=True)
    keys: list[tuple[str, str]] = []
    for sheet_key in ["meta", "fpa_meta", "spec_meta", "cosmic_meta", "require_meta"]:
        sheet_name = _s.get(sheet_key, "")
        if not sheet_name or sheet_name not in wb.sheetnames:
            continue
        ws = wb[sheet_name]
        for row in ws.iter_rows(min_row=2, values_only=True):
            key = str(row[0]).strip() if row[0] else ""
            if key:
                keys.append((sheet_name, key))
    wb.close()
    return keys


def _read_l3_names_from_excel(excel_path: str) -> list[str]:
    """从 Excel 功能清单中读取三级模块名称（去重，处理合并单元格继承）。"""
    from ai_gen_reimbursement_docs.config_utils import load_sheet_names
    import openpyxl

    _s = load_sheet_names()
    wb = openpyxl.load_workbook(excel_path, data_only=True)
    ws = wb[_s["func_content"]]

    names: list[str] = []
    seen: set[str] = set()
    prev_name = ""
    for row in ws.iter_rows(min_row=2, values_only=True):
        name = str(row[3]).strip() if len(row) > 3 and row[3] else ""
        if not name:
            name = prev_name
        else:
            prev_name = name
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    wb.close()
    return names


def _build_parser() -> argparse.ArgumentParser:
    """构建 CLI 参数解析器。"""
    parser = argparse.ArgumentParser(
        description="AI生成项目报账文档 — 从功能清单自动生成全套报账交付物",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""  示例:

  ard --init-config                 初始化配置
  ard --from-excel 功能清单.xlsx --gen-all      全流程
  ard --from-excel 功能清单.xlsx --gen-fpa      仅 FPA""",
    )

    parser.add_argument('--api-key', '-k', default='',
                        help='API Key（默认从 .env 读取）')
    parser.add_argument('--model', '-m', default='',
                        help='模型名称（默认 deepseek-v4-flash）')
    parser.add_argument('--from-excel', default='',
                        help='功能清单.xlsx 路径')
    parser.add_argument('--gen-fpa', action='store_true',
                        help='生成 FPA工作量评估.xlsx')
    parser.add_argument('--gen-cosmic', action='store_true',
                        help='生成 项目功能点拆分表.xlsx')
    parser.add_argument('--gen-list', action='store_true',
                        help='生成 项目需求清单.xlsx')
    parser.add_argument('--gen-spec', action='store_true',
                        help='生成 项目需求说明书.docx')
    parser.add_argument('--gen-basedata', action='store_true',
                        help='生成 模块树.md + 元数据.md')
    parser.add_argument('--gen-all', action='store_true',
                        help='全流程自动执行')
    parser.add_argument('--output-dir', default='',
                        help='输出目录')
    parser.add_argument('--project-name', default='',
                        help='输出文件夹名称')
    parser.add_argument('--fpa-out-template', default='',
                        help='FPA 输出模板路径')
    parser.add_argument('--cosmic-out-template', default='',
                        help='COSMIC 输出模板路径')
    parser.add_argument('--list-out-template', default='',
                        help='需求清单 输出模板路径')
    parser.add_argument('--spec-out-template', default='',
                        help='需求说明书 输出模板路径')
    parser.add_argument('--clean', action='store_true',
                        help='删除旧输出再重新生成')
    parser.add_argument('--init-config', action='store_true',
                        help='初始化配置文件')
    parser.add_argument('--log', nargs='?', const='tail', default=None,
                        help='查看日志')
    parser.add_argument('--version', '-v', action='store_true',
                        help='显示版本号')
    parser.add_argument('--test-sound', action='store_true',
                        help='测试提示音')
    parser.add_argument('--max-tokens', type=str, default='',
                        help='覆盖 AI max_tokens')
    parser.add_argument('--test-ai-gen-reliability-desc', action='store_true',
                        help='测试"调整因子中的可靠性描述"AI生成（仅控制台+日志输出）')
    parser.add_argument('--test-ai-gen-metadata', type=str, default='',
                        help='测试元数据中指定字段的#AI生成#（仅控制台+日志输出）')
    parser.add_argument('--web', action='store_true',
                        help='启动 Web UI 界面')

    return parser


def main():
    from ai_gen_reimbursement_docs.cli.logging import (
        init_global_logging, setup_logging, write_combined_ai_log,
    )
    from ai_gen_reimbursement_docs.cli.notify import play_notify_sound
    from ai_gen_reimbursement_docs.cli.interactive import (
        resolve_fpa_sum, prompt_list_values,
    )
    from ai_gen_reimbursement_docs.excel_source import project_root

    init_global_logging()

    parser = _build_parser()
    args = parser.parse_args()
    if args.max_tokens:
        os.environ['AI_REIMBURSEMENT_MAX_TOKENS'] = args.max_tokens
    logger.debug(f"CLI args: {args}")

    ver = _get_version()
    run_mode = "exe" if getattr(sys, 'frozen', False) else "源码"
    root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    run_path = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else root
    logger.info(f"[CLI] AI生成项目报账文档 v{ver} ({run_mode}: {run_path})")

    from ai_gen_reimbursement_docs.config_utils import config_dir, migrate_config
    logger.info(f"配置文件目录: {config_dir()}")
    migrate_config()

    try:
        from ai_gen_reimbursement_docs.version_check import check_version
        check_version(ver)
    except Exception:
        pass  # 版本检查失败不影响主流程

    # ── 纯 CLI 功能 ──
    if args.test_sound:
        try:
            import winsound
            _ap = os.path.join(root, 'data', 'audio', 'ticktick_pop.wav')
            if os.path.isfile(_ap):
                winsound.PlaySound(_ap, winsound.SND_FILENAME | winsound.SND_SYNC)
                print("提示音已播放")
            else:
                print(f"音频文件不存在: {_ap}")
        except Exception as e:
            print(f"提示音播放失败: {e}")
        return

    log_root = os.path.join(root, 'log')
    if getattr(sys, 'frozen', False):
        log_root = os.path.join(os.path.expanduser('~'), '.ai-gen-reimbursement-docs', 'log')
    if args.log:
        if args.log == 'open':
            os.startfile(log_root)
            return
        log_files = sorted([f for f in os.listdir(log_root) if f.endswith('.log')], reverse=True)
        if not log_files:
            logger.error("没有找到日志文件")
            return
        latest = os.path.join(log_root, log_files[0])
        if args.log == 'watch':
            try:
                os.system(f'tail -f "{latest}"')
            except Exception:
                os.system(f'powershell -command "Get-Content \\"{latest}\\" -Wait"')
            return
        with open(latest, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        if args.log == 'tail':
            lines = lines[-30:]
        print(''.join(lines))
        return

    if args.version:
        print(f"AI生成项目报账文档 v{_get_version()}")
        return

    if args.web:
        _auto_init_config(root)
        _start_web_ui(root)
        return

    if args.init_config:
        cfg_dir = os.path.join(root, 'config')
        home_cfg = os.path.join(os.path.expanduser('~'), '.ai-gen-reimbursement-docs')
        os.makedirs(home_cfg, exist_ok=True)
        pairs = [
            (os.path.join(cfg_dir, '.env.example'), os.path.join(home_cfg, '.env')),
            (os.path.join(cfg_dir, 'system_config.yaml.example'), os.path.join(home_cfg, 'system_config.yaml')),
            (os.path.join(cfg_dir, 'business_rules.yaml.example'), os.path.join(home_cfg, 'business_rules.yaml')),
        ]
        for src, dst in pairs:
            if os.path.exists(dst):
                logger.info(f"已存在，跳过: {dst}")
                continue
            shutil.copy2(src, dst)
            logger.info(f"已创建: {dst}")
        logger.info("请编辑 ~/.ai-gen-reimbursement-docs/.env 填入你的 API Key 后使用")
        return

    # ── 配置加载 ──
    api_key = args.api_key or load_api_key()
    base_url = load_base_url()
    model = args.model or load_model_name()
    logger.debug(f"API Key: {'已设置' if api_key else '未设置'}, 端点: {base_url or '默认'}, 模型: {model}")

    from ai_gen_reimbursement_docs.config_utils import load_max_tokens, load_business_config, load_cfp_formula
    logger.info(f"配置: MAX_TOKENS={load_max_tokens()}, CFP公式={load_cfp_formula()}")
    biz_cfg = load_business_config()
    logger.info(f"配置: REGENERATE_MD={biz_cfg['regenerate_md']}, ENABLE_AI_GENERATE_COSMIC={biz_cfg['enable_ai_generate_cosmic']}")

    # ── 测试：调整因子中的可靠性描述 AI 生成 ──
    if args.test_ai_gen_reliability_desc:
        excel_path = args.from_excel
        if not excel_path:
            import glob
            for name in ["功能清单-录入模板.xlsx", "功能清单.xlsx"]:
                matches = glob.glob(name)
                if matches:
                    excel_path = matches[0]
                    break
            if not excel_path:
                logger.error("未指定 --from-excel，且当前目录未找到功能清单文件")
                return
        if not os.path.exists(excel_path):
            logger.error(f"文件不存在: {excel_path}")
            return

        if not api_key:
            logger.error("未配置 API Key")
            return

        descriptions = _read_l3_descriptions_from_excel(excel_path)
        if not descriptions:
            logger.warning("未找到三级模块整体功能描述")
            return

        logger.info(f"共读取到 {len(descriptions)} 条三级模块整体功能描述")

        user_prompt = (
            f"根据功能清单，提取其中涉及与可靠性方面的模块，生成一句关于可靠性业务描述。不少于50字。\n"
            f"功能清单：\n" + '\n'.join(f'- {d}' for d in descriptions)
        )

        from ai_gen_reimbursement_docs.config_utils import load_ai_system_prompt
        system_prompt = load_ai_system_prompt("reliability_desc")
        if not system_prompt:
            logger.warning("未找到 reliability_desc 系统提示词，将使用默认提示词")

        _section("测试：调整因子中的可靠性描述 AI 生成")
        logger.info("用户提示词:\n%s", user_prompt)
        logger.info("系统提示词:\n%s", system_prompt)

        from ai_gen_reimbursement_docs.llm_client import call_llm
        try:
            result = call_llm(
                prompt=user_prompt,
                system=system_prompt,
                api_key=api_key,
                model=model,
                base_url=base_url,
                tag="test_reliability_desc",
            )
            _section("AI 生成结果")
            print(result)
            logger.info("可靠性描述生成结果:\n%s", result)
        except Exception as e:
            logger.error("AI 调用失败: %s", e)
            print(f"AI 调用失败: {e}")
        return

    # ── 测试：元数据 #AI生成# 字段 ──
    if args.test_ai_gen_metadata:
        excel_path = args.from_excel
        if not excel_path:
            import glob
            for name in ["功能清单-录入模板.xlsx", "功能清单.xlsx"]:
                matches = glob.glob(name)
                if matches:
                    excel_path = matches[0]
                    break
            if not excel_path:
                logger.error("未指定 --from-excel，且当前目录未找到功能清单文件")
                return
        if not os.path.exists(excel_path):
            logger.error(f"文件不存在: {excel_path}")
            return

        if not api_key:
            logger.error("未配置 API Key")
            return

        field_key = args.test_ai_gen_metadata
        found_sheet, raw_value = _read_meta_field_value(excel_path, field_key)
        if not raw_value:
            all_keys = _read_meta_all_keys(excel_path)
            logger.warning(f"未找到字段「{field_key}」，所有可用字段: {all_keys}")
            print(f"未找到字段「{field_key}」")
            print("所有元数据字段: ")
            for sn, k in all_keys:
                print(f"  [{sn}] {k}")
            return

        from ai_gen_reimbursement_docs.excel_source import strip_ai_marker
        prompt_template, needs_ai = strip_ai_marker(raw_value)
        if not needs_ai:
            logger.warning(f"字段「{field_key}」不含 #AI生成# 标记，当前值: {raw_value}")
            return

        # 解析占位符
        import openpyxl
        from ai_gen_reimbursement_docs.config_utils import load_sheet_names
        _s = load_sheet_names()
        wb = openpyxl.load_workbook(excel_path, data_only=True)
        # Sheet 1: 工单需求-元数据录入
        project_info: dict[str, str] = {}
        for row in wb[_s["meta"]].iter_rows(min_row=2, values_only=True):
            k = str(row[0]).strip() if row[0] else ""
            v = str(row[1]).strip() if len(row) > 1 and row[1] else ""
            if k:
                project_info[k] = v
        # Sheet 3: FPA工作量评估-元数据录入
        fpa_meta: dict[str, str] = {}
        for row in wb[_s["fpa_meta"]].iter_rows(min_row=2, values_only=True):
            k = str(row[0]).strip() if row[0] else ""
            v = str(row[1]).strip() if len(row) > 1 and row[1] else ""
            if k:
                fpa_meta[k] = v
        wb.close()

        user_prompt = prompt_template
        user_prompt = user_prompt.replace('${工单编号}', project_info.get('工单编号', ''))
        user_prompt = user_prompt.replace('${工单名称}', project_info.get('工单标题', ''))
        user_prompt = user_prompt.replace('${工单标题}', project_info.get('工单标题', ''))
        user_prompt = user_prompt.replace('${工单内容}', project_info.get('工单内容', ''))
        user_prompt = user_prompt.replace('${子系统（模块）}', fpa_meta.get('子系统（模块）', ''))

        if '${三级模块}' in user_prompt:
            l3_names = _read_l3_names_from_excel(excel_path)
            user_prompt = user_prompt.replace('${三级模块}', '、'.join(l3_names))
        if '${三级模块整体功能描述}' in user_prompt:
            l3_descs = _read_l3_descriptions_from_excel(excel_path)
            user_prompt = user_prompt.replace('${三级模块整体功能描述}',
                                              '\n'.join(f'- {d}' for d in l3_descs))

        from ai_gen_reimbursement_docs.config_utils import load_ai_system_prompt
        system_prompt = load_ai_system_prompt("metadata_gen")
        if not system_prompt:
            logger.warning("未找到 metadata_gen 系统提示词")

        _section(f"测试：元数据 #AI生成# — {field_key}")
        logger.info("字段来源: [%s] %s", found_sheet, field_key)
        logger.info("用户提示词:\n%s", user_prompt)
        logger.info("系统提示词:\n%s", system_prompt)

        from ai_gen_reimbursement_docs.llm_client import call_llm
        try:
            result = call_llm(
                prompt=user_prompt,
                system=system_prompt,
                api_key=api_key,
                model=model,
                base_url=base_url,
                tag=f"test_meta_{field_key}",
            )
            _section("AI 生成结果")
            print(result)
            logger.info("AI 生成结果 [%s]:\n%s", field_key, result)
        except Exception as e:
            logger.error("AI 调用失败: %s", e)
            print(f"AI 调用失败: {e}")
        return

    # ── 零参数模式：自动搜索当前目录功能清单并全流程执行 ──
    if not any([args.gen_basedata, args.gen_fpa, args.gen_cosmic, args.gen_list,
                args.gen_spec, args.gen_all]):
        _auto_detect_and_run(api_key, model, base_url)
        # 自动检测失败（无可识别文件）时返回，继续往下走，由 gen-* 块报错

    # ── from-excel 管道 ──
    if any([args.gen_basedata, args.gen_fpa, args.gen_cosmic, args.gen_list,
             args.gen_spec, args.gen_all]):

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

        excel_dir = os.path.dirname(os.path.abspath(excel_path))
        if args.output_dir:
            out_dir = args.output_dir
        elif args.project_name:
            safe = re.sub(r'[\/:*?"<>|]', '_', args.project_name)
            out_dir = os.path.join(excel_dir, safe)
        else:
            from ai_gen_reimbursement_docs.pipeline import _try_read_project_name
            auto_name = _try_read_project_name(excel_path)
            if auto_name:
                safe = re.sub(r'[\/:*?"<>|]', '_', auto_name)
                out_dir = os.path.join(excel_dir, safe)
                args.project_name = auto_name
            else:
                out_dir = excel_dir

        if args.clean and args.project_name:
            safe = re.sub(r'[\/:*?"<>|]', '_', args.project_name)
            target = os.path.join(excel_dir, safe)
            if os.path.exists(target):
                shutil.rmtree(target)
                logger.info(f"已删除输出目录: {target}")

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

        templates = {}
        for key, arg_name in [('fpa', 'fpa_out_template'), ('cosmic', 'cosmic_out_template'),
                              ('list', 'list_out_template'), ('spec', 'spec_out_template')]:
            val = getattr(args, arg_name, '').strip()
            if val and os.path.exists(val):
                templates[key] = val

        # 交互式参数：在调 pipeline 之前提示用户
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
                print(f"  ✅ {_label}: {_path} ({_size/1024:.0f} KB)")
            else:
                print(f"  ⏭️  {_label}: 跳过（已存在或未生成）")
        print()

        write_combined_ai_log(mode)
        play_notify_sound()
        return


if __name__ == '__main__':
    _exit_code = 0
    try:
        main()
    except Exception as _e:
        _exit_code = 1
        print(f"\n  错误: {_e}", file=sys.stderr)
        try:
            logger.debug("未捕获异常", exc_info=True)
        except Exception:
            pass
    if getattr(sys, 'frozen', False):
        input("\n按 Enter 键退出...")
    sys.exit(_exit_code)
