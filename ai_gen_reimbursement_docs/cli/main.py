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
    logger.info(f"AI生成项目报账文档 v{ver} ({run_mode}: {run_path})")

    from ai_gen_reimbursement_docs.config_utils import config_dir, migrate_config
    logger.info(f"配置文件目录: {config_dir()}")
    migrate_config()

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
            out_dir = excel_dir

        if args.clean and args.project_name:
            safe = re.sub(r'[\/:*?"<>|]', '_', args.project_name)
            target = os.path.join(excel_dir, safe)
            if os.path.exists(target):
                shutil.rmtree(target)
                logger.info(f"已删除输出目录: {target}")

        log_dir = os.path.join(out_dir, '日志')
        os.makedirs(log_dir, exist_ok=True)
        setup_logging(log_dir, 'AI生成项目报账文档')
        os.environ['AI_REIMBURSEMENT_LOG_DIR'] = log_dir

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
