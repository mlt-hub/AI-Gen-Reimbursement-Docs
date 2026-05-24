"""CLI 日志初始化 —— 文件 + 控制台 handler，文件句柄即写即释。"""

import logging
import os
from datetime import datetime


class PathShortener(logging.Filter):
    """将日志中的绝对路径缩短为基于交付物输出目录的相对路径。

    环境变量 AI_REIMBURSEMENT_OUTPUT_DIR 指定输出根目录，
    日志中该前缀 + 分隔符会被替换为空，使路径更可读。
    """

    def filter(self, record: logging.LogRecord) -> bool:
        base = os.environ.get("AI_REIMBURSEMENT_OUTPUT_DIR", "")
        if base:
            record.msg = _replace_path(str(record.msg), base + os.sep, "")
            record.msg = _replace_path(str(record.msg), base, "")
        return True


def _replace_path(text: str, old: str, new: str) -> str:
    return text.replace(old, new).replace(old.replace("\\", "/"), new)


class ReleaseFileHandler(logging.Handler):
    """每次写日志时打开文件 → 写入 → 关闭，不长期持有文件句柄。
    mode='w' 仅首次写入时截断，后续追加。"""

    def __init__(self, filename: str, encoding: str = "utf-8", mode: str = "a"):
        super().__init__()
        self.filename = filename
        self.encoding = encoding
        self._init_mode = mode  # 首次写入模式
        self._first_write = True

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            m = self._init_mode if self._first_write else "a"
            with open(self.filename, m, encoding=self.encoding) as f:
                f.write(msg + "\n")
            self._first_write = False
        except Exception:
            self.handleError(record)


_global_logging_done = False


def init_global_logging(level: str = "INFO"):
    """初始化全局日志：~/.ai-gen-reimbursement-docs/log/（控制台 + 总日志 + 运行日志）。
    level: DEBUG / INFO / WARNING / ERROR，控制台输出级别。文件始终 DEBUG。
    多次调用不会重复添加 handler。
    """
    global _global_logging_done
    if _global_logging_done:
        return logging.getLogger('ai_gen_reimbursement_docs'), None
    _global_logging_done = True

    log_dir = os.path.join(os.path.expanduser('~'), '.ai-gen-reimbursement-docs', 'log')
    os.makedirs(log_dir, exist_ok=True)

    main_log = os.path.join(log_dir, 'global_ai_gen_reimbursement_docs.log')
    run_stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    run_log = os.path.join(log_dir, f'global_run_{run_stamp}.log')

    _lv = getattr(logging, level.upper(), logging.INFO)
    logger = logging.getLogger('ai_gen_reimbursement_docs')
    logger.setLevel(logging.DEBUG)

    _ps = PathShortener()

    fmt = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    fh = ReleaseFileHandler(main_log, encoding='utf-8', mode='a')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    fh.addFilter(_ps)
    logger.addHandler(fh)

    rh = ReleaseFileHandler(run_log, encoding='utf-8', mode='w')
    rh.setLevel(logging.DEBUG)
    rh.setFormatter(fmt)
    rh.addFilter(_ps)
    logger.addHandler(rh)

    ch = logging.StreamHandler()
    ch.setLevel(_lv)
    ch.setFormatter(logging.Formatter('%(message)s'))
    ch.addFilter(_ps)
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

    rh = ReleaseFileHandler(run_log, encoding='utf-8', mode='w')
    rh.setLevel(logging.DEBUG)
    rh.setFormatter(fmt)
    rh.addFilter(PathShortener())
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

    think_dir = os.path.join(log_dir, 'ai_thinking')

    NL = chr(10)
    dirs = {
        'ai_对话日志.md': (prompt_dir, resp_dir, think_dir),
        'ai_prompts_日志.md': (prompt_dir,),
        'ai_responses_日志.md': (resp_dir,),
        'ai_thinking_日志.md': (think_dir,),
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
