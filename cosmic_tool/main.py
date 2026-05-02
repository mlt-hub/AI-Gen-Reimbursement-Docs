"""COSMIC 功能点拆分工具 - CLI入口

推荐工作流（MD中间件模式）:
  1. python -m cosmic_tool.main --docx 需求书.docx --init-md 拆分表.md
  2. python -m cosmic_tool.main --fill-md 拆分表.md
     (编辑拆分表.md 人工审核修正)
  3. python -m cosmic_tool.main --md 拆分表.md --template 模板.xlsx --output 结果.xlsx

快捷模式（一键直出）:
  python -m cosmic_tool.main --docx 需求书.docx --template 模板.xlsx --output 结果.xlsx
"""

import argparse
import os
import shutil

from .docx_parser import build_module_tree, print_tree, get_project_name
from .cosmic_llm import generate_cosmic_items
from .excel_writer import write_to_template
from .config_utils import load_api_key, load_base_url, load_model_name
from .md_handler import (
    export_empty_md,
    export_filled_md,
    parse_md_to_items,
    fill_md_with_ai,
)

# 启动时自动清理 cosmic_tool 自身的字节码缓存，避免代码修改后缓存过期问题
_pycache = os.path.join(os.path.dirname(__file__), '__pycache__')
if os.path.isdir(_pycache):
    shutil.rmtree(_pycache, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(
        description="COSMIC 功能点拆分工具 - 从需求说明书自动生成功能点拆分表",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
工作流示例:

  # (推荐) MD中间件模式：docx → MD → 编辑MD → Excel
  python -m cosmic_tool.main --docx 需求书.docx --init-md 拆分表.md
  python -m cosmic_tool.main --fill-md 拆分表.md
  python -m cosmic_tool.main --md 拆分表.md --template 模板.xlsx --output 结果.xlsx

  # (快捷) 一键直出：docx → LLM → Excel
  python -m cosmic_tool.main --docx 需求书.docx --template 模板.xlsx --output 结果.xlsx

  # 仅查看模块树
  python -m cosmic_tool.main --docx 需求书.docx --show-tree

  # 初始化API Key配置
  python -m cosmic_tool.main --init-config
        """
    )

    # === CLI Arguments ===
    parser.add_argument('--docx', '-d', default='',
                        help='需求说明书 .docx 文件路径')

    parser.add_argument('--init-md', default='',
                        help='从docx生成空白MD中间文件（不含AI拆分）')

    parser.add_argument('--fill-md', default='',
                        help='AI填充MD中的COSMIC数据（原地更新）')

    parser.add_argument('--md', default='',
                        help='从MD文件生成Excel（MD需已包含COSMIC数据表）')

    parser.add_argument('--template', '-t', default='',
                        help='功能点拆分表 .xlsx 模板文件路径')

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

    parser.add_argument('--init-config', action='store_true',
                        help='初始化 .env 配置文件')

    args = parser.parse_args()

    # === Init config ===
    if args.init_config:
        env_path = os.path.join(os.path.dirname(__file__), '.env')
        if os.path.exists(env_path):
            print(f"配置文件已存在: {env_path}")
            return
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write("""# COSMIC 功能点拆分工具 配置文件
ANTHROPIC_API_KEY=your_api_key_here
ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
ANTHROPIC_MODEL=deepseek-v4-flash
""")
        print(f"配置文件已创建: {env_path}")
        print("请编辑该文件填入你的 API Key")
        return

    # === Load config ===
    api_key = args.api_key or load_api_key()
    base_url = load_base_url()
    model = args.model or load_model_name("deepseek-v4-flash")

    if api_key:
        os.environ["ANTHROPIC_API_KEY"] = api_key
    if base_url:
        os.environ["ANTHROPIC_BASE_URL"] = base_url

    # === Show tree ===
    if args.docx and args.show_tree:
        modules = build_module_tree(args.docx)
        project = get_project_name(args.docx)
        print(f"项目名称: {project}")
        print(f"模块总数: {len(modules)}")
        print("-" * 60)
        print_tree(modules)
        return

    # === Mode 1: init-md (docx → empty MD) ===
    if args.init_md:
        if not args.docx:
            parser.error("--init-md 需要 --docx")
        print("=" * 60)
        print("阶段1: 解析需求说明书 → 生成空白MD")
        print("=" * 60)
        modules = build_module_tree(args.docx)
        project = get_project_name(args.docx)
        export_empty_md(modules, project, args.init_md)
        print(f"\n下一步:")
        print(f"  python -m cosmic_tool.main --fill-md {args.init_md}")
        return

    # === Mode 2: fill-md (AI fill MD in-place) ===
    if args.fill_md:
        if not api_key:
            print("⚠ 未设置 API Key。请先运行 --init-config 或设置环境变量")
            return
        print("=" * 60)
        print("阶段2: AI填充MD中的COSMIC数据")
        print("=" * 60)
        # Need docx to build module tree context
        docx_path = args.docx or _find_docx_from_md(args.fill_md)
        if not docx_path:
            parser.error("--fill-md 需要 --docx 或将MD放在docx同目录下")
        modules = build_module_tree(docx_path)
        project = get_project_name(docx_path)
        fill_md_with_ai(args.fill_md, modules, project, api_key, model, base_url)
        print(f"\n下一步:")
        print(f"  编辑 {args.fill_md} 人工审核修正")
        print(f"  然后: python -m cosmic_tool.main --md {args.fill_md} --template 模板.xlsx --output 结果.xlsx")
        return

    # === Mode 3: md → Excel ===
    if args.md:
        if not args.template:
            parser.error("--md 需要 --template")
        if not args.output:
            args.output = "output_COSMIC_拆分表.xlsx"
        print("=" * 60)
        print("阶段3: 从MD生成Excel拆分表")
        print("=" * 60)
        items = parse_md_to_items(args.md)
        if not items:
            print("⚠ MD中未解析到COSMIC数据，请先运行 --fill-md 或手动填写表格")
            return
        write_to_template(args.template, args.output, items)
        total_cfp = sum(item.total_cfp() for item in items)
        print(f"\n总计: {len(items)} 功能过程, {total_cfp} CFP")
        print(f"输出: {os.path.abspath(args.output)}")
        return

    # === Mode 4: Direct docx → LLM → Excel (one shot) ===
    if args.docx and args.template:
        if not args.output:
            args.output = "output_COSMIC_拆分表.xlsx"
        print("=" * 60)
        print("阶段1: 解析需求说明书")
        print("=" * 60)
        modules = build_module_tree(args.docx)
        project = get_project_name(args.docx)
        print(f"项目: {project}")
        print(f"模块: {len(modules)}")
        print_tree(modules)

        items = []
        if not args.no_llm:
            if not api_key:
                print("⚠ 未设置 API Key。请先运行 --init-config 或设置环境变量")
                return
            print("\n" + "=" * 60)
            print("阶段2: AI生成COSMIC功能点拆分")
            print("=" * 60)
            print(f"模型: {model}")
            if base_url:
                print(f"端点: {base_url}")
            items = generate_cosmic_items(
                modules=modules, project_name=project,
                api_key=api_key, base_url=base_url, model=model,
            )

        if items:
            print("\n" + "=" * 60)
            print("阶段3: 生成Excel")
            print("=" * 60)
            write_to_template(args.template, args.output, items)
            total_cfp = sum(item.total_cfp() for item in items)
            print(f"\n总计: {len(items)} 功能过程, {total_cfp} CFP")
            print(f"输出: {os.path.abspath(args.output)}")
        elif args.no_llm:
            write_to_template(args.template, args.output, [])
            print("生成空白模板（无数据行）")
        return

    # === No valid mode ===
    parser.print_help()


def _find_docx_from_md(md_path: str) -> str:
    """Try to find the corresponding docx for an MD file."""
    md_dir = os.path.dirname(os.path.abspath(md_path))
    for f in os.listdir(md_dir):
        if f.endswith('.docx'):
            return os.path.join(md_dir, f)
    # Try parent directory
    parent = os.path.dirname(md_dir)
    for f in os.listdir(parent):
        if f.endswith('.docx'):
            return os.path.join(parent, f)
    return ""


if __name__ == '__main__':
    main()
