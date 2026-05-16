"""CLI 交互式输入 —— FPA 核减后工作量、送审功能点。"""

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


def resolve_fpa_sum(fpa_sum_md_path: str) -> float:
    """从 FPA工作量.md 读取值作为默认，提示用户输入FPA核减后工作量。"""
    from ai_gen_reimbursement_docs.config_utils import load_fpa_reduced_use_workload
    if load_fpa_reduced_use_workload():
        if os.path.exists(fpa_sum_md_path):
            with open(fpa_sum_md_path, encoding='utf-8') as f:
                for line in f:
                    m = re.search(r'FPA工作量（人/天）[：:]\s*([\d.]+)', line)
                    if m:
                        val = float(m.group(1))
                        logger.info(f"FPA核减后工作量: {val}（直接用 FPA 工作量）")
                        return val
        return 0

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


def prompt_list_values(fpa_sum_md_path: str) -> tuple[float, float]:
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
