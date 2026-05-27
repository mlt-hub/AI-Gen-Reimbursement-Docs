"""CLI 交互式输入 —— FPA核减后工作量、送审功能点。"""

import logging
import os
import re

logger = logging.getLogger('ai_gen_reimbursement_docs.cli.interactive')


def _read_md_value(path: str, pattern: str) -> float:
    """从 MD 文件中按正则提取数值，文件不存在返回 0。"""
    if not os.path.exists(path):
        return 0.0
    with open(path, encoding='utf-8') as f:
        for line in f:
            m = re.search(pattern, line)
            if m:
                return float(m.group(1))
    return 0.0


def prompt_list_values(md_dir: str) -> tuple[float, float]:
    """提示用户输入送审功能点和送审工作量（gen-list 使用）。

    从 gen-cosmic-CFP-总和.md / gen-cosmic-FPA核减后的工作量-总和.md（回退 gen-fpa-FPA工作量-总和.md）读取默认值。
    返回 (cfp_total, fpa_reduced)。
    """
    # 送审工作量
    _fpa_raw = _read_md_value(
        os.path.join(md_dir, '3.1.gen-cosmic-FPA核减后的工作量-总和.md'),
        r'FPA核减后的工作量（人/天）[：:]\s*([\d.]+)')
    
    if _fpa_raw > 0:
        _prompt2 = f"请输入送审工作量（人/天）（直接回车使用FPA核减后的工作量总和：{_fpa_raw}）: "
    else:
        _prompt2 = "请输入送审工作量（人/天）: "
    try:
        _inp2 = input(_prompt2).strip()
        fpa_reduced = float(_inp2) if _inp2 else _fpa_raw
    except (EOFError, OSError, ValueError):
        fpa_reduced = _fpa_raw
        logger.info(f"送审工作量（人/天): {fpa_reduced}（默认值）")

    # 送审功能点
    _cfp_raw = _read_md_value(
        os.path.join(md_dir, '3.5.gen-cosmic-CFP-总和.md'),
        r'CFP 总和[：:]\s*([\d.]+)')

    if _cfp_raw > 0:
        _prompt = f"\n请输入送审功能点（个）（直接回车使用CFP总和：{_cfp_raw}）: "
    else:
        _prompt = "\n请输入送审功能点（个）: "
    try:
        _inp = input(_prompt).strip()
        cfp_total = float(_inp) if _inp else _cfp_raw
    except (EOFError, OSError, ValueError):
        cfp_total = _cfp_raw
        logger.info(f"送审功能点（个）: {cfp_total}（默认值）")

    logger.info(f"送审工作量（人/天）: {fpa_reduced}, 送审功能点（个）: {cfp_total}")
    return cfp_total, fpa_reduced
