"""COSMIC 功能点拆分工具 - CLI入口

Usage:
    python -m cosmic_tool.main --docx 需求说明书.docx --template 模板.xlsx --output 拆分表.xlsx
    python -m cosmic_tool.main --docx 需求说明书.docx --template 模板.xlsx --output 拆分表.xlsx --intermediate output.json
    python -m cosmic_tool.main --json output.json --template 模板.xlsx --output 拆分表.xlsx
"""

import argparse
import json
import os
import sys

from .docx_parser import build_module_tree, print_tree, get_project_name
from .cosmic_llm import (
    generate_cosmic_items,
    save_to_json,
    load_from_json,
)
from .excel_writer import write_to_template
from .config_utils import load_api_key, load_base_url, load_model_name


def main():
    parser = argparse.ArgumentParser(
        description="COSMIC 功能点拆分工具 - 从需求说明书自动生成功能点拆分表",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 完整流程: docx → LLM → xlsx
  python -m cosmic_tool.main --docx 需求书.docx --template 模板.xlsx --output 拆分表.xlsx

  # 先生成中间JSON供审核
  python -m cosmic_tool.main --docx 需求书.docx --template 模板.xlsx --intermediate output.json

  # 审核后从JSON生成xlsx
  python -m cosmic_tool.main --json output.json --template 模板.xlsx --output 拆分表.xlsx

  # 仅查看模块树结构
  python -m cosmic_tool.main --docx 需求书.docx --show-tree

  # 初始化配置文件
  python -m cosmic_tool.main --init-config
        """
    )

    # Input group
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument(
        '--docx', '-d',
        help='需求说明书 .docx 文件路径'
    )
    input_group.add_argument(
        '--json', '-j',
        help='已审核的中间JSON文件路径（跳过LLM步骤）'
    )

    # Other args
    parser.add_argument(
        '--template', '-t',
        default='',
        help='功能点拆分表 .xlsx 模板文件路径'
    )
    parser.add_argument(
        '--output', '-o',
        default='',
        help='输出 .xlsx 文件路径'
    )
    parser.add_argument(
        '--intermediate', '-i',
        default='',
        help='中间JSON文件路径（用于保存/加载LLM生成结果）'
    )
    parser.add_argument(
        '--api-key', '-k',
        default='',
        help='Anthropic API Key（命令行指定，优先级最高）'
    )
    parser.add_argument(
        '--model', '-m',
        default='',
        help='模型名称（默认从 .env 读取，否则 deepseek-v4-flash）'
    )
    parser.add_argument(
        '--show-tree', '-s',
        action='store_true',
        help='仅显示模块树结构，不生成拆分表'
    )
    parser.add_argument(
        '--no-llm',
        action='store_true',
        help='不调用LLM，仅生成空模板输出（跳过AI步骤）'
    )
    parser.add_argument(
        '--init-config',
        action='store_true',
        help='初始化 .env 配置文件'
    )

    args = parser.parse_args()

    # --- Init config mode ---
    if args.init_config:
        env_path = os.path.join(os.path.dirname(__file__), '.env')
        if os.path.exists(env_path):
            print(f"配置文件已存在: {env_path}")
            print("如需重置，请删除后重新运行 --init-config")
        else:
            with open(env_path, 'w', encoding='utf-8') as f:
                f.write("""# COSMIC 功能点拆分工具 配置文件
# 请将下方 your_api_key_here 替换为你的 Anthropic API Key
ANTHROPIC_API_KEY=your_api_key_here
""")
            print(f"配置文件已创建: {env_path}")
            print("请编辑该文件，将 your_api_key_here 替换为你的 API Key")
        return

    # --- Load API key & config ---
    api_key = args.api_key or load_api_key()
    base_url = load_base_url()
    model = args.model or load_model_name("deepseek-v4-flash")

    if api_key:
        os.environ["ANTHROPIC_API_KEY"] = api_key
    if base_url:
        os.environ["ANTHROPIC_BASE_URL"] = base_url
    elif not args.no_llm and not args.json:
        print("=" * 60)
        print("⚠ 未设置 ANTHROPIC_API_KEY")
        print("=" * 60)
        print()
        print("请通过以下任一方式设置：")
        print("  1. 设置环境变量: export ANTHROPIC_API_KEY=sk-xxx")
        print(f"  2. 运行初始化: python -m cosmic_tool.main --init-config")
        print("     然后编辑 .env 文件填入你的 API Key")
        print("  3. 命令行指定: --api-key sk-xxx")
        print("  4. 跳过LLM: --no-llm (仅解析文档结构)")
        print()
        return

    # --- Show tree mode ---
    if args.docx and args.show_tree:
        print("=" * 60)
        print("功能模块树结构")
        print("=" * 60)
        modules = build_module_tree(args.docx)
        project = get_project_name(args.docx)
        print(f"项目名称: {project}")
        print(f"模块总数: {len(modules)}")
        print("-" * 60)
        print_tree(modules)
        return

    # --- Validate args ---
    if not args.docx and not args.json:
        parser.error("请指定 --docx 或 --json")

    if not args.output:
        args.output = "output_COSMIC_拆分表.xlsx"

    if not args.template:
        # Try to find template in current directory
        import glob
        xlsx_files = glob.glob("*.xlsx")
        if xlsx_files:
            args.template = xlsx_files[0]
            print(f"使用模板文件: {args.template}")
        else:
            parser.error("请指定 --template 模板文件路径")

    if not os.path.exists(args.template):
        parser.error(f"模板文件不存在: {args.template}")

    # --- Stage 1: Parse docx ---
    items = []
    if args.docx:
        print("=" * 60)
        print("阶段1: 解析需求说明书")
        print("=" * 60)
        modules = build_module_tree(args.docx)
        project_name = get_project_name(args.docx)
        print(f"项目名称: {project_name}")
        print(f"识别模块数: {len(modules)}")

        print("\n模块层级:")
        print_tree(modules)

        # --- Stage 2: Generate COSMIC items ---
        if not args.no_llm:
            print("\n" + "=" * 60)
            print("阶段2: AI生成COSMIC功能点拆分")
            print("=" * 60)

            print(f"\n使用模型: {model}")
            if base_url:
                print(f"API端点: {base_url}")

            items = generate_cosmic_items(
                modules=modules,
                project_name=project_name,
                api_key=api_key,
                base_url=base_url,
                model=model,
            )

            if args.intermediate:
                save_to_json(items, args.intermediate)
                print(f"\n中间JSON已保存至: {args.intermediate}")
                print("请审核后使用 --json 选项继续生成Excel。")
                print("如需直接生成Excel，请忽略 --intermediate 选项。" +
                      "若要修改，编辑JSON后运行:\n" +
                      f"  python -m cosmic_tool.main --json {args.intermediate} "
                      f"--template {args.template} --output {args.output}")
        else:
            print("\n跳过LLM阶段（--no-llm）")
    else:
        # Load from JSON
        print("=" * 60)
        print("从JSON加载已审核的COSMIC拆分数据")
        print("=" * 60)
        items = load_from_json(args.json)
        project_name = items[0].project if items else ""
        print(f"项目名称: {project_name}")
        print(f"加载分解项: {len(items)}")

    # --- Stage 3: Write to Excel ---
    if items:
        print("\n" + "=" * 60)
        print("阶段3: 生成Excel拆分表")
        print("=" * 60)

        write_to_template(
            template_path=args.template,
            output_path=args.output,
            items=items
        )

        # Calculate total CFP
        total_cfp = sum(item.total_cfp() for item in items)
        print(f"\n总计: {len(items)} 功能过程, {total_cfp} CFP")
        print(f"输出文件: {os.path.abspath(args.output)}")

    elif args.docx and args.no_llm:
        # Generate template with headers only
        print("\n生成空模板（无数据行）")
        write_to_template(
            template_path=args.template,
            output_path=args.output,
            items=[]
        )


if __name__ == '__main__':
    main()
