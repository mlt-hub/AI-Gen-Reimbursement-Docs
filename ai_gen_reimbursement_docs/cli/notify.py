"""播放提示音。"""

import os


def play_notify_sound():
    """根据 notify_sound 配置播放提示音。"""
    try:
        import yaml as _y
        _notify = False
        for _p in [
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                         'config', 'system_config.yaml'),
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
            _audio_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'data', 'audio', 'ticktick_pop.wav'
            )
            if os.path.isfile(_audio_path):
                winsound.PlaySound(_audio_path, winsound.SND_FILENAME | winsound.SND_SYNC)
    except Exception:
        pass
