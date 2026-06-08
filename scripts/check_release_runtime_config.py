"""Release preflight for runtime configuration files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ai_gen_reimbursement_docs.config_utils import (  # noqa: E402
    FpaConfigError,
    validate_fpa_runtime_config_files,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check FPA runtime config files before release.")
    parser.add_argument(
        "--config-dir",
        default="",
        help="Config directory to check. Defaults to ~/.ai-gen-reimbursement-docs.",
    )
    args = parser.parse_args(argv)

    target_dir = Path(args.config_dir).expanduser() if args.config_dir else None
    try:
        status = validate_fpa_runtime_config_files(target_dir)
    except FpaConfigError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 1

    print(f"[通过] FPA 运行配置完整: {status['config_dir']}")
    for filename in status["files"]:
        print(f"  - {filename}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
