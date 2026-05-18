"""AI生成项目报账文档 —— CLI 入口已迁移至 cli/main.py。"""
import sys

from ai_gen_reimbursement_docs.cli.main import main

if __name__ == '__main__':
    _exit_code = 0
    try:
        main()
    except Exception as _e:
        _exit_code = 1
        print(f"\n  错误: {_e}", file=sys.stderr)
    if getattr(sys, 'frozen', False):
        input("\n按 Enter 键退出...")
    sys.exit(_exit_code)
