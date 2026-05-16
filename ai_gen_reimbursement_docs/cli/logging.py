"""CLI 日志初始化 —— 文件 + 控制台 handler。"""

import logging
import os
import sys
from datetime import datetime


def init_global_logging():
    """初始化全局日志：项目根目录 log/（控制台 + 总日志 + 运行日志）。"""
    if getattr(sys, 'frozen', False):
        log_dir = os.path.join(os.path.expanduser('~'), '.ai-gen-reimbursement-docs', 'log')
    else:
        log_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'log'
        )
    os.makedirs(log_dir, exist_ok=True)

    main_log = os.path.join(log_dir, 'global_ai_gen_reimbursement_docs.log')
    run_stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    run_log = os.path.join(log_dir, f'global_run_{run_stamp}.log')

    logger = logging.getLogger('ai_gen_reimbursement_docs')
    logger.setLevel(logging.DEBUG)

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


def setup_logging(log_dir: str, docx_name: str = ""):
    """添加 per-docx 日志处理器（保留全局日志）。"""
    os.makedirs(log_dir, exist_ok=True)

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


def write_combined_ai_log(stage: str = ""):
    """增量追加 AI 对话日志（合并版 + prompts 版 + responses 版）。"""
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
        all_files = {}
        for d in sub_dirs:
            if os.path.isdir(d):
                for fname in os.listdir(d):
                    if fname.endswith('.txt'):
                        all_files[fname] = os.path.join(d, fname)

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
            logging.getLogger('ai_gen_reimbursement_docs.cli.logging').info(
                f"{out_name} 追加 {new_count} 条新记录")
