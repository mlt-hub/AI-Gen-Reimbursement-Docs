"""Generate COSMIC decompositions using Claude API."""

import json
import logging
import os
import sys
from datetime import datetime
from typing import Optional

from ai_gen_reimbursement_docs.exceptions import ConfigError, ParseError
from ai_gen_reimbursement_docs.models import CosmicItem, DataMovement
from ai_gen_reimbursement_docs.models import FunctionModule
from ai_gen_reimbursement_docs.module_utils import get_module_by_name

logger = logging.getLogger('ai_gen_reimbursement_docs.cosmic_llm')

# Fuzzy matching for common move_type variations
_MOVE_TYPE_FUZZY = {
    'entry': 'E', 'enter': 'E', 'input': 'E', 'import': 'E',
    'e': 'E',
    'exit': 'X', 'output': 'X', 'export': 'X', 'display': 'X',
    'x': 'X',
    'read': 'R', 'query': 'R', 'select': 'R', 'load': 'R', 'retrieve': 'R',
    'r': 'R',
    'write': 'W', 'save': 'W', 'insert': 'W', 'update': 'W',
    'delete': 'W', 'remove': 'W', 'store': 'W', 'create': 'W',
    'w': 'W',
}


def _resolve_move_type(raw: str) -> tuple[str, bool]:
    """Resolve move_type with fuzzy matching. Returns (standardized, was_flagged)."""
    t = raw.strip().upper()
    if t in ('E', 'X', 'R', 'W'):
        return t, False
    t_lower = raw.strip().lower()
    if t_lower in _MOVE_TYPE_FUZZY:
        return _MOVE_TYPE_FUZZY[t_lower], True
    # Completely unknown: default to E and flag
    return 'E', True

def parse_user_rules(text: str) -> tuple[str, list[tuple[str, str]]]:
    """解析"默认：操作员\\n分销：分销员" → ("操作员", [("分销","分销员")])"""
    default = ""
    rules: list[tuple[str, str]] = []
    for line in text.split('\n'):
        line = line.strip().rstrip('|').strip()
        if not line:
            continue
        if '：' not in line:
            continue
        key, val = line.split('：', 1)
        key = key.strip()
        val = val.strip()
        if key == '默认':
            default = val
        else:
            rules.append((key, val))
    return default, rules


def load_user_config_from_meta(meta_md_path: str) -> dict:
    """从文档元数据读取功能用户-发起者/接收者判定，返回配置字典。"""
    from ai_gen_reimbursement_docs.gen_spec import _parse_meta_md
    meta = _parse_meta_md(meta_md_path)
    result: dict = {
        "user_default_initiator": "",
        "user_default_receiver": "",
        "user_initiator_rules": None,
        "user_receiver_rules": None,
    }
    initiator_text = meta.get("功能用户-发起者判定", "")
    if initiator_text:
        default, rules = parse_user_rules(initiator_text)
        if default:
            result["user_default_initiator"] = default
        if rules:
            result["user_initiator_rules"] = rules
    else:
        logger.warning("Excel 模板未配置「功能用户-发起者判定」，发起者将为空，请在模板 Sheet 6 中补充")
    receiver_text = meta.get("功能用户-接收者判定", "")
    if receiver_text:
        default, rules = parse_user_rules(receiver_text)
        if default:
            result["user_default_receiver"] = default
        if rules:
            result["user_receiver_rules"] = rules
    else:
        logger.warning("Excel 模板未配置「功能用户-接收者判定」，接收者将为空，请在模板 Sheet 6 中补充")
    return result


def _build_user(module: FunctionModule, modules: list[FunctionModule],
                initiator_rules: list[tuple[str, str]] | None = None,
                receiver_rules: list[tuple[str, str]] | None = None,
                default_initiator: str = "",
                default_receiver: str = "") -> str:
    """Determine the user for a module using configurable keyword rules.

    Checks order: grandparent → parent → module name.
    Initiator and receiver are matched independently against their respective rule sets.
    Falls back to defaults for any unmatched role.
    """
    # Collect ancestor names to check
    names_to_check = [module.name]
    # L3.parent 可能是 "L1/L2" 复合格式
    _raw_parent = module.parent or ""
    if "/" in _raw_parent:
        _l1_name, _l2_name = _raw_parent.split("/", 1)
        names_to_check.append(_l2_name)
        names_to_check.append(_l1_name)
    else:
        parent = get_module_by_name(modules, module.parent) if module.parent else None
        if parent:
            names_to_check.append(parent.name)
            if parent.parent:
                grandparent = get_module_by_name(modules, parent.parent)
                if grandparent:
                    names_to_check.append(grandparent.name)

    # Match initiator
    initiator = default_initiator
    if initiator_rules:
        for keyword, val in initiator_rules:
            for name in names_to_check:
                if keyword in name:
                    initiator = val
                    break
            if initiator != default_initiator:
                break

    # Match receiver
    receiver = default_receiver
    if receiver_rules:
        for keyword, val in receiver_rules:
            for name in names_to_check:
                if keyword in name:
                    receiver = val
                    break
            if receiver != default_receiver:
                break

    return f"发起者：{initiator}|接收者：{receiver}"


def _build_trigger(module: FunctionModule) -> str:
    """Determine the trigger type."""
    if '同步' in module.name or '定时' in module.description:
        return "定时触发"
    return "用户触发"


def _build_module_prompt(l3_module: FunctionModule, modules: list[FunctionModule]) -> str:
    """Build the prompt for a single L3 module."""
    parent = ""
    _raw_parent = l3_module.parent or ""
    if "/" in _raw_parent:
        # 复合格式 "L1/L2" → 直接拼接
        _l1, _l2 = _raw_parent.split("/", 1)
        parent = f"{_l1} > {_l2} > "
    elif _raw_parent:
        p = get_module_by_name(modules, l3_module.parent)
        if p:
            pp = ""
            if p.parent:
                pp_obj = get_module_by_name(modules, p.parent)
                if pp_obj:
                    pp = pp_obj.name + " > "
            parent = f"{pp}{p.name} > "

    prompt = f"## 模块：{parent}{l3_module.name}\n"
    prompt += f"### 功能描述\n{l3_module.description}\n\n"

    if l3_module.children:
        prompt += "### 功能过程列表（需为每个过程生成COSMIC数据移动链）\n"
        for i, child in enumerate(l3_module.children, 1):
            prompt += f"{i}. {child}\n"
    return prompt



def _clean_json(raw: str) -> str:
    """Clean malformed JSON: trailing commas, single quotes, etc."""
    import re
    text = raw.strip()

    # Remove trailing commas before ] or }
    text = re.sub(r',\s*([}\]])', r'\1', text)

    # Replace single quotes used as string delimiters
    in_string = False
    chars = []
    i = 0
    while i < len(text):
        c = text[i]
        if c == '"' and (i == 0 or text[i-1] != '\\'):
            in_string = not in_string
            chars.append(c)
        elif c == "'" and not in_string:
            chars.append('"')
        else:
            chars.append(c)
        i += 1
    text = ''.join(chars)

    # Remove line comments
    text = re.sub(r'//[^\n]*', '', text)

    return text.strip()


def _parse_llm_response(module_name: str, user: str, trigger: str,
                        response_text: str, project_name: str,
                        l1_name: str, l2_name: str) -> list[CosmicItem]:
    """Parse LLM JSON response into CosmicItem objects."""
    items = []

    from ai_gen_reimbursement_docs.llm_client import strip_markdown_code_block
    text = strip_markdown_code_block(response_text)

    # Find JSON array in text（找 [ 后紧跟 { 的位置，避免在思考文本中匹配到 [）
    start = text.find('[{')
    if start == -1:
        start = text.find('[')
    end = text.rfind(']')
    if start == -1 or end == -1:
        raise ParseError(f"No JSON array found in response for module: {module_name}")

    json_str = text[start:end+1]

    # Clean common JSON issues before parsing
    json_str = _clean_json(json_str)

    data = json.loads(json_str)

    for proc in data:
        movements = []
        item_warnings: list[str] = []
        raw_movements = proc.get('movements', [])

        for i, m in enumerate(raw_movements, 1):
            # Resolve move_type with fuzzy matching
            raw_type = m.get('move_type', 'E')
            move_type, flagged = _resolve_move_type(raw_type)
            data_attrs = m.get('data_attrs', '')
            data_group = m.get('data_group', '')

            # Movement-level validations
            if flagged:
                item_warnings.append(f"步{i}: 移动类型「{raw_type}」→ {move_type}（模糊匹配）")

            if data_attrs:
                attr_count = len([a for a in data_attrs.replace('、', ',').split(',') if a.strip()])
                if attr_count < 3:
                    item_warnings.append(f"步{i}: 数据属性仅{attr_count}个（建议≥3）")

            if not data_attrs:
                item_warnings.append(f"步{i}: 数据属性为空")

            movements.append(DataMovement(
                order=i,
                sub_process=m.get('sub_process', ''),
                move_type=move_type,
                data_group=data_group,
                data_attrs=data_attrs,
                reuse=m.get('reuse', '新增'),
                move_type_flagged=flagged,
            ))

        # Process-level validations
        if len(movements) < 2:
            item_warnings.append(f"数据移动仅{len(movements)}步（建议≥2）")

        if movements and movements[0].move_type != 'E':
            item_warnings.append(f"首步应为E（当前为{movements[0].move_type}）")

        if movements and movements[-1].move_type not in ('W', 'X'):
            item_warnings.append(f"末步应为W或X（当前为{movements[-1].move_type}）")

        process_name = proc.get('process', '')
        if not process_name:
            item_warnings.append("功能过程名称为空")

        items.append(CosmicItem(
            project=project_name,
            module_l1=l1_name or module_name,
            module_l2=l2_name or module_name,
            module_l3=module_name,
            user=proc.get('user', user),
            trigger=proc.get('trigger', trigger),
            process=process_name,
            movements=movements,
            warnings=item_warnings,
        ))

    return items


def generate_cosmic_items(
    modules: list[FunctionModule],
    project_name: str = "",
    api_key: Optional[str] = None,
    model: str = "",
    base_url: Optional[str] = None,
    interactive: bool = False,
    user_default_initiator: str = "",
    user_default_receiver: str = "",
    user_initiator_rules: list[tuple[str, str]] | None = None,
    user_receiver_rules: list[tuple[str, str]] | None = None,
) -> list[CosmicItem]:
    """Generate COSMIC decompositions for all L3 modules using Claude API.

    Args:
        modules: Flat list of FunctionModules from module_utils
        project_name: Project name
        api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        model: Claude model to use (default: deepseek-v4-flash)
        base_url: Custom API base URL (e.g., for DeepSeek compat)
        interactive: If True, prompt user before each API call

    Returns:
        List of CosmicItem objects
    """
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ConfigError(
            "未配置 API Key，请在 ~/.ai-gen-reimbursement-docs/.env 中设置 ANTHROPIC_API_KEY 或传入 --api-key"
        )

    base_url = base_url or os.environ.get("ANTHROPIC_BASE_URL", "")

    # Filter L3 modules
    l3_modules = [m for m in modules if m.level == 3]
    if not l3_modules:
        logger.warning("No L3 modules found in the module tree.")
        return []

    # Load config
    from ai_gen_reimbursement_docs.config_utils import load_max_tokens, load_ai_system_prompt, load_ai_examples, load_flow_max_ai
    max_tokens = load_max_tokens()
    logger.info(f"MAX_TOKENS = {max_tokens}")

    max_ai_l3 = load_flow_max_ai("gen_cosmic")
    if max_ai_l3 > 0:
        logger.info(f"仅对前 {max_ai_l3} 个 L3 模块调用 AI，超过的跳过")

    all_items = []
    error_modules: list[tuple[str, str, str, str]] = []  # (l1, l2, l3, error_msg)
    total = len(l3_modules)
    logger.info(f"Generating COSMIC decompositions for {total} modules...")

    from ai_gen_reimbursement_docs.config_utils import load_gen_cosmic_ai_limit
    _cosmic_proc_limit = load_gen_cosmic_ai_limit()
    _cosmic_proc_count = 0
    if _cosmic_proc_limit > 0:
        logger.info(f"仅对前 {_cosmic_proc_limit} 个功能过程调用 AI，超过的跳过")
    _skip_ai_limit = 0
    _skip_proc_limit = 0
    _ai_called = 0

    for idx, l3 in enumerate(l3_modules, 1):
        # L3.parent 可能是 "L1/L2" 复合格式，需拆分
        _parent_raw = l3.parent or ""
        if "/" in _parent_raw:
            _parts = _parent_raw.split("/", 1)
            l1_name = _parts[0]
            l2_name = _parts[1]
        else:
            l2_name = _parent_raw
            l1_name = ""
            if l2_name:
                l2 = get_module_by_name(modules, l2_name)
                if l2 and l2.parent:
                    l1_name = l2.parent
        # 按功能过程累计数跳过
        if _cosmic_proc_limit > 0:
            _module_procs = len(l3.children) if l3.children else 1
            if _cosmic_proc_count >= _cosmic_proc_limit:
                from ai_gen_reimbursement_docs.models import CosmicItem
                # 每个功能过程生成一行（保留 L1/L2/L3 信息，movements 为空）
                for _child in (l3.children or [l3.name]):
                    all_items.append(CosmicItem(
                        project=project_name,
                        module_l1=l1_name, module_l2=l2_name, module_l3=l3.name,
                        process=_child, user="", trigger="", movements=[]
                    ))
                logger.info(f"    [{idx}/{total}] 跳过 {l3.name}（超过功能过程限制 {_cosmic_proc_limit}）")
                _skip_proc_limit += 1
                continue
            _cosmic_proc_count += _module_procs

        # 超过现有限制的模块跳过 AI

        # 超过限制的模块跳过 AI
        if max_ai_l3 > 0 and idx > max_ai_l3:
            logger.info(f"    [{idx}/{total}] 跳过 {l3.name}（超过 AI 限制 {max_ai_l3}）")
            _skip_ai_limit += 1
            from ai_gen_reimbursement_docs.models import CosmicItem
            for _child in (l3.children or [l3.name]):
                all_items.append(CosmicItem(
                    project=project_name,
                    module_l1=l1_name, module_l2=l2_name, module_l3=l3.name,
                    process=_child, user="", trigger="", movements=[]
                ))
            continue

        user = _build_user(l3, modules, user_initiator_rules, user_receiver_rules,
                           user_default_initiator, user_default_receiver)
        trigger = _build_trigger(l3)

        prompt = _build_module_prompt(l3, modules)

        logger.info(f"  [{idx}/{total}] {l1_name} > {l2_name} > {l3.name}...")

        if interactive:
            input("Press Enter to continue (Ctrl+C to skip)...")

        _current_max_tokens = max_tokens
        _abort_module = False
        while True:
            try:
                _ai_called += 1
                _save_ai_prompt(l3.name, l2_name, l1_name, prompt, "generate_cosmic")

                from ai_gen_reimbursement_docs.llm_client import call_llm
                resp_text = call_llm(
                    prompt=prompt,
                    system=load_ai_system_prompt("cosmic_split") + "\n\n" + load_ai_examples("cosmic_split"),
                    api_key=api_key, model=model, base_url=base_url,
                    max_tokens=_current_max_tokens, temperature=0.1,
                    tag=f"cosmic_{idx}", save_logs=False,
                )

                _save_ai_response(l3.name, l2_name, l1_name, resp_text, "")

                items = _parse_llm_response(l3.name, user, trigger, resp_text,
                                            project_name, l1_name, l2_name)
                all_items.extend(items)
                warn_count = sum(1 for it in items if it.warnings)
                if warn_count:
                    for it in items:
                        if it.warnings:
                            logger.warning(f"  [{idx}/{total}] ⚠ {it.process}: {'; '.join(it.warnings)}")
                sub_count = sum(len(it.movements) for it in items)
                logger.info(f"  [{idx}/{total}] → {sub_count} 个子过程描述"
                            + (f"（{warn_count}个有警告）" if warn_count else ""))
                break  # success, exit while loop

            except Exception as e:
                logger.warning(f"  [{idx}/{total}] → ERROR: {e}")
                if not sys.stdin.isatty():
                    error_modules.append((l1_name, l2_name, l3.name, str(e)[:200]))
                    break
                try:
                    choice = input(f"  错误: {e}\n  输入 r 12000 重试(r后有空格)，q 结束，Enter跳过: ").strip()
                    if choice == 'q':
                        _abort_module = True
                        break
                    if choice.startswith('r ') and len(choice) > 2:
                        _current_max_tokens = int(choice[2:].strip())
                        logger.info(f"  重试，max_tokens 设为 {_current_max_tokens}")
                        continue
                    error_modules.append((l1_name, l2_name, l3.name, str(e)[:200]))
                    break
                except (EOFError, KeyboardInterrupt):
                    error_modules.append((l1_name, l2_name, l3.name, str(e)[:200]))
                    break
        if _abort_module:
            logger.warning(f"用户选择结束，已处理 {idx}/{total} 个模块")
            break

    # --- 数据组名去重（从功能过程中提取动词作后缀） ---
    _seen_groups: dict[str, str] = {}
    for _item in all_items:
        _verb = _item.process[:2] if len(_item.process) >= 2 else _item.process
        for _m in _item.movements:
            _orig = _m.data_group
            if _orig in _seen_groups:
                _first_verb = _seen_groups[_orig]
                if _first_verb != _verb:
                    _m.data_group = f"{_orig}{_verb}"
            else:
                _seen_groups[_orig] = _verb

    # --- 数据属性去重（全局唯一，重复时尾部加"等"） ---
    _seen_attrs: set[str] = set()
    for _item in all_items:
        for _m in _item.movements:
            _orig = _m.data_attrs
            if not _orig:
                continue
            _key = _orig
            while _key in _seen_attrs:
                _key += "等"
            if _key != _orig:
                _m.data_attrs = _key
            _seen_attrs.add(_key)

    # 汇总：全部跳过时提示配置限制
    if _ai_called == 0 and total > 0:
        _reasons = []
        if max_ai_l3 > 0 and _skip_ai_limit > 0:
            _reasons.append(f"max_ai_l3_modules={max_ai_l3}（跳过 {_skip_ai_limit} 个模块）")
        if _cosmic_proc_limit > 0 and _skip_proc_limit > 0:
            _reasons.append(f"gen_cosmic_ai_limit={_cosmic_proc_limit}（跳过 {_skip_proc_limit} 个模块）")
        if _reasons:
            logger.warning(
                "⚠ COSMIC AI 全部跳过（共 %d 个模块），请检查配置限制：%s。"
                "如需 AI 填充，请在 ~/.ai-gen-reimbursement-docs/system_config.yaml 中将对应值设为 0",
                total, "、".join(_reasons),
            )

    # --- Final summary ---
    total_ok = len(all_items)
    warn_items = [it for it in all_items if it.warnings]
    logger.info(f"Total COSMIC items generated: {total_ok}")
    has_issues = warn_items or error_modules
    if has_issues:
        if warn_items:
            module_warns: dict[str, list] = {}
            for it in warn_items:
                mod_path = f"{it.module_l1}>{it.module_l2}>{it.module_l3}"
                module_warns.setdefault(mod_path, []).append(it)
            logger.warning(f"⚠ {len(module_warns)} 个模块存在数据异常（共{len(warn_items)}个功能过程）:")
            for mod_path, processes in module_warns.items():
                logger.warning(f"  • {mod_path}（{len(processes)}个过程）")
                for it in processes:
                    for w in it.warnings:
                        logger.warning(f"    - [{it.process}] {w}")
        if error_modules:
            logger.warning(f"❌ {len(error_modules)} 个模块解析失败:")
            for l1, l2, l3, err in error_modules:
                mod_path = f"{l1}>{l2}>{l3}" if l1 else l3
                logger.warning(f"  • {mod_path}: {err}")
    else:
        logger.info("所有模块数据正常，无异常")
    return all_items


def _save_ai_prompt(l3: str, l2: str, l1: str, text: str, tag: str = "") -> None:
    """Save full AI prompt text to log/ai_prompts/ for review."""
    base_log = os.environ.get('AI_REIMBURSEMENT_LOG_DIR', '') or os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 'log'
    )
    log_dir = os.path.join(base_log, 'ai_prompts')
    os.makedirs(log_dir, exist_ok=True)

    parts = [p for p in [l1, l2, l3] if p]
    safe_name = '_'.join(parts).replace('/', '_').replace('\\', '_').strip()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    tag_str = f'_{tag}' if tag else ''
    filename = f"{timestamp}_{safe_name}{tag_str}_prompt.txt"
    filepath = os.path.join(log_dir, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"# AI Prompt: {' > '.join(parts)} ({tag})\n")
        f.write(f"# Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(text)
    logger.debug(f"AI提示词已保存: {filepath}")


def _save_ai_response(l3: str, l2: str, l1: str, text: str, reasoning: str = "") -> None:
    """Save raw AI response text to log/ai_responses/ for review."""
    base_log = os.environ.get('AI_REIMBURSEMENT_LOG_DIR', '') or os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 'log'
    )
    log_dir = os.path.join(base_log, 'ai_responses')
    os.makedirs(log_dir, exist_ok=True)

    # Safe filename from module hierarchy
    parts = [p for p in [l1, l2, l3] if p]
    safe_name = '_'.join(parts).replace('/', '_').replace('\\', '_').strip()

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{timestamp}_{safe_name}.md"
    filepath = os.path.join(log_dir, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"# AI Response: {' > '.join(parts)}\n")
        f.write(f"# Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        if reasoning:
            f.write("## AI 判断依据\n\n")
            f.write(reasoning)
            f.write("\n\n---\n\n")
        f.write("## 生成结果\n\n")
        f.write(text)

    logger.info(f"AI响应已保存: {filepath}")


def save_to_json(items: list[CosmicItem], output_path: str) -> None:
    """Save generated items to JSON for review."""
    data = []
    for item in items:
        data.append({
            "project": item.project,
            "module_l1": item.module_l1,
            "module_l2": item.module_l2,
            "module_l3": item.module_l3,
            "user": item.user,
            "trigger": item.trigger,
            "process": item.process,
            "movements": [
                {
                    "sub_process": m.sub_process,
                    "move_type": m.move_type,
                    "data_group": m.data_group,
                    "data_attrs": m.data_attrs
                }
                for m in item.movements
            ]
        })

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"Saved {len(data)} items to {output_path}")


def load_from_json(input_path: str) -> list[CosmicItem]:
    """Load items from JSON (after manual review/edit)."""
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    items = []
    for d in data:
        movements = [
            DataMovement(order=i+1, **m)
            for i, m in enumerate(d.get('movements', []))
        ]
        items.append(CosmicItem(
            project=d.get('project', ''),
            module_l1=d.get('module_l1', ''),
            module_l2=d.get('module_l2', ''),
            module_l3=d.get('module_l3', ''),
            user=d.get('user', ''),
            trigger=d.get('trigger', ''),
            process=d.get('process', ''),
            movements=movements
        ))
    return items
