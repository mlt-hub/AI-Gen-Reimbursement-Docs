"""播放提示音。"""

import os
import sys


def _app_root() -> str:
    """返回应用根目录。exe 模式取 exe 所在目录，源码模式取项目根。"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


def play_notify_sound():
    """根据 notify_sound 配置播放提示音。"""
    try:
        import yaml as _y
        _notify = False
        root = _app_root()
        for _p in [
            os.path.join(root, 'config', 'system_config.yaml'),
            os.path.join(os.environ.get('USERPROFILE', os.environ.get('HOME', '')),
                         '.ai-gen-reimbursement-docs', 'system_config.yaml'),
        ]:
            if os.path.isfile(_p):
                with open(_p, encoding='utf-8') as _f:
                    _c = _y.safe_load(_f)
                if _c and _c.get('notify_sound'):
                    _notify = True
                    break
        if _notify:
            import winsound
            _audio_path = os.path.join(root, 'assets', 'audio', 'ticktick_pop.wav')
            if os.path.isfile(_audio_path):
                winsound.PlaySound(_audio_path, winsound.SND_FILENAME | winsound.SND_SYNC)
    except Exception:
        pass
