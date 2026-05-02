"""Generate COSMIC decompositions using Claude API."""

import json
import logging
import os
import sys
from typing import Optional

from .models import CosmicItem, DataMovement
from .docx_parser import FunctionModule, get_module_by_name

logger = logging.getLogger('cosmic_tool.cosmic_llm')

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

SYSTEM_PROMPT = """你是COSMIC功能点拆分专家。你的任务是根据软件功能需求描述，生成标准的COSMIC功能点拆分。

## COSMIC规则约束
1. **每个功能过程由一系列数据移动组成**，每种数据移动记1CFP
2. **数据移动类型**：
   - E (Entry): 用户/系统输入数据，触发功能过程
   - X (eXit): 系统输出数据给用户/系统
   - R (Read): 系统从持久存储读取数据
   - W (Write): 系统将数据写入持久存储
3. **首步必为E**（Entry），末步必为W或X
4. **每个功能过程的子过程 ≥ 2个**
5. **每个数据组 ≥ 3个数据属性**（属性之间用顿号或逗号分隔）
6. **功能用户格式**: "发起者：xxx|接收者：xxx"
7. **触发事件**: 一般为"用户触发"；定时任务用"定时触发"
8. **复用度**: 每个数据移动需标注复用度——"新增"（新开发的功能）、"复用"（已有功能复用了）、"利旧"（沿用旧系统功能不动）

## 常见模式
- **表单展示**：E(请求表单) → X(返回表单页面)
- **查询列表**：E(提交查询条件) → R(读取数据) → X(返回列表)
- **新增数据**：E(提交新增数据) → W(存储数据到数据库)
- **删除数据**：E(提交删除指令) → W(从数据库删除)
- **编辑数据**：E(进入编辑页面) → X(展示编辑表单)
- **执行编辑保存**：E(提交修改数据) → W(更新数据库)
- **导出数据**：E(提交导出请求) → R(读取数据) → X(生成导出文件)

## 输出格式
返回JSON数组，每项格式：
{
  "user": "发起者：操作员|接收者：地市后台",
  "trigger": "用户触发",
  "process": "功能过程名称",
  "movements": [
    {"sub_process": "子过程描述", "move_type": "E", "data_group": "数据组名", "data_attrs": "属性1、属性2、属性3", "reuse": "新增"},
    ...
  ]
}
"""


def _build_user(module: FunctionModule, modules: list[FunctionModule],
                initiator_rules: list[tuple[str, str]] | None = None,
                receiver_rules: list[tuple[str, str]] | None = None,
                default_initiator: str = "操作员",
                default_receiver: str = "地市后台") -> str:
    """Determine the user for a module using configurable keyword rules.

    Checks order: grandparent → parent → module name.
    Initiator and receiver are matched independently against their respective rule sets.
    Falls back to defaults for any unmatched role.
    """
    # Collect ancestor names to check
    names_to_check = [module.name]
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
    if l3_module.parent:
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


def _extract_text(content_blocks: list) -> str:
    """Extract text from response content blocks, handling ThinkingBlock."""
    for block in content_blocks:
        block_type = getattr(block, 'type', None) or type(block).__name__
        if 'text' in block_type.lower() or block_type in ('text', 'TextBlock'):
            return block.text
    # Fallback: try to get text attribute from any block
    for block in content_blocks:
        if hasattr(block, 'text'):
            return block.text
    return ""


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

    # Extract JSON from response (handle markdown code blocks)
    text = response_text.strip()
    if '```json' in text:
        text = text.split('```json')[1]
        if '```' in text:
            text = text.split('```')[0]
    elif '```' in text:
        text = text.split('```')[1]
        if '```' in text:
            text = text.split('```')[0]

    # Find JSON array in text
    start = text.find('[')
    end = text.rfind(']')
    if start == -1 or end == -1:
        raise ValueError(f"No JSON array found in response for module: {module_name}")

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
    model: str = "deepseek-v4-flash",
    base_url: Optional[str] = None,
    interactive: bool = False
) -> list[CosmicItem]:
    """Generate COSMIC decompositions for all L3 modules using Claude API.

    Args:
        modules: Flat list of FunctionModules from docx_parser
        project_name: Project name
        api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        model: Claude model to use (default: deepseek-v4-flash)
        base_url: Custom API base URL (e.g., for DeepSeek compat)
        interactive: If True, prompt user before each API call

    Returns:
        List of CosmicItem objects
    """
    import anthropic

    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY is not set. Please set it or pass --api-key."
        )

    base_url = base_url or os.environ.get("ANTHROPIC_BASE_URL", "")
    client_kwargs = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url

    client = anthropic.Anthropic(**client_kwargs)

    # Filter L3 modules
    l3_modules = [m for m in modules if m.level == 3]
    if not l3_modules:
        logger.warning("No L3 modules found in the module tree.")
        return []

    # Load config
    from .config_utils import load_user_defaults, load_initiator_rules, load_receiver_rules, load_max_tokens
    user_default_initiator, user_default_receiver = load_user_defaults()
    user_initiator_rules = load_initiator_rules()
    user_receiver_rules = load_receiver_rules()
    max_tokens = load_max_tokens()
    logger.info(f"MAX_TOKENS = {max_tokens}")

    all_items = []
    error_modules: list[tuple[str, str, str, str]] = []  # (l1, l2, l3, error_msg)
    total = len(l3_modules)
    total_input_tokens = 0
    total_output_tokens = 0

    logger.info(f"Generating COSMIC decompositions for {total} modules...")

    for idx, l3 in enumerate(l3_modules, 1):
        l2_name = l3.parent or ""
        l1_name = ""
        if l2_name:
            l2 = get_module_by_name(modules, l2_name)
            if l2 and l2.parent:
                l1_name = l2.parent

        user = _build_user(l3, modules, user_initiator_rules, user_receiver_rules,
                           user_default_initiator, user_default_receiver)
        trigger = _build_trigger(l3)

        prompt = _build_module_prompt(l3, modules)

        logger.info(f"  [{idx}/{total}] {l1_name} > {l2_name} > {l3.name}...")

        if interactive:
            input("Press Enter to continue (Ctrl+C to skip)...")

        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=0.1,
                system=SYSTEM_PROMPT + "\n\n## 现有参照示例\n" + _get_examples(),
                messages=[{"role": "user", "content": prompt}]
            )

            # Token usage monitoring
            usage = getattr(response, 'usage', None)
            inp_tok = getattr(usage, 'input_tokens', 0) if usage else 0
            out_tok = getattr(usage, 'output_tokens', 0) if usage else 0
            total_input_tokens += inp_tok
            total_output_tokens += out_tok
            # Per-call usage
            logger.info(f"  [{idx}/{total}] tokens: ↑{inp_tok} ↓{out_tok}（累积 ↑{total_input_tokens} ↓{total_output_tokens}）")

            # Check for truncation
            stop_reason = getattr(response, 'stop_reason', None) or ''
            if stop_reason == 'max_tokens':
                logger.warning(f"  [{idx}/{total}] ⚠ AI输出被截断（{out_tok}/{max_tokens}），结果可能不完整")

            resp_text = _extract_text(response.content)
            if not resp_text:
                raise ValueError("No text content in response")

            # Save raw AI response to log file
            _save_ai_response(l3.name, l2_name, l1_name, resp_text)

            items = _parse_llm_response(l3.name, user, trigger, resp_text,
                                        project_name, l1_name, l2_name)
            all_items.extend(items)
            # Log warnings summary
            warn_count = sum(1 for it in items if it.warnings)
            if warn_count:
                for it in items:
                    if it.warnings:
                        logger.warning(f"  [{idx}/{total}] ⚠ {it.process}: {'; '.join(it.warnings)}")
            logger.info(f"  [{idx}/{total}] → {len(items)} processes"
                        + (f" ({warn_count} with warnings)" if warn_count else ""))

        except Exception as e:
            logger.warning(f"  [{idx}/{total}] → ERROR: {e}")
            error_modules.append((l1_name, l2_name, l3.name, str(e)[:200]))
            # Prompt user on error (only in interactive terminal)
            try:
                if sys.stdin.isatty():
                    choice = input("  输入 q 结束（其他键继续）: ").strip().lower()
                    if choice == 'q':
                        logger.warning(f"用户选择结束，已处理 {idx}/{total} 个模块")
                        break
            except (EOFError, KeyboardInterrupt):
                break

    # --- Final summary ---
    total_ok = len(all_items)
    warn_items = [it for it in all_items if it.warnings]
    logger.info(f"Total COSMIC items generated: {total_ok}")
    logger.info(f"Token usage: ↑{total_input_tokens} 输入 / ↓{total_output_tokens} 输出（单次上限 {max_tokens}）")
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


def _save_ai_response(l3: str, l2: str, l1: str, text: str) -> None:
    """Save raw AI response text to log/ai_responses/ for review."""
    import os
    from datetime import datetime

    log_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 'log', 'ai_responses'
    )
    os.makedirs(log_dir, exist_ok=True)

    # Safe filename from module hierarchy
    parts = [p for p in [l1, l2, l3] if p]
    safe_name = '_'.join(parts).replace('/', '_').replace('\\', '_').strip()
    safe_name = safe_name[:100] if len(safe_name) > 100 else safe_name

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{timestamp}_{safe_name}.md"
    filepath = os.path.join(log_dir, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"# AI Response: {' > '.join(parts)}\n")
        f.write(f"# Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(text)

    logger.info(f"AI响应已保存: {filepath}")


def _get_examples() -> str:
    """Return few-shot examples from the existing spreadsheet."""
    return """参考以下COSMIC拆分示例的格式：

示例1：列表查询（3步：E→R→X）
- 功能过程：融合宽带订单列表
- 用户：发起者：操作员|接收者：地市后台
- 触发事件：用户触发
- 数据移动：
  [E] 点击进入页面获取列表 → 数据组：订单列表请求 → 数据属性：用户标识、分页参数
  [R] 读取融合宽带订单列表数据 → 数据组：融合宽带订单列表 → 数据属性：订单编号、客户号码、业务名称、业务编码、分销信息、订单状态、下单时间
  [X] 融合宽带订单列表展示 → 数据组：列表反映 → 数据属性：产品数据、字段排序、列表组合

示例2：保存数据（2步：E→W）
- 功能过程：保存活动
- 用户：发起者：操作员|接收者：地市后台
- 触发事件：用户触发
- 数据移动：
  [E] 点击提交完整页面配置数据 → 数据组：页面配置数据 → 数据属性：页面ID、组件列表、配置参数
  [W] 存储页面配置 → 数据组：页面配置表 → 数据属性：更新所有组件及配置

示例3：带读取的编辑（3步：E→R→X）
- 功能过程：小福包产品编辑页面
- 用户：发起者：操作员|接收者：地市后台
- 触发事件：用户触发
- 数据移动：
  [E] 点击小福包产品编辑标签进入编辑页面 → 数据组：编辑页面获取指令 → 数据属性：小福包产品ID、用户ID
  [R] 读取小福包产品数据 → 数据组：小福包产品表 → 数据属性：小福包名称、编码、业务描述、子商品信息
  [X] 渲染展示小福包编辑页面 → 数据组：小福包产品编辑表 → 数据属性：小福包名称、编码、业务描述、子商品信息

示例4：删除（2步：E→W）
- 功能过程：删除图片轮播组件
- 用户：发起者：操作员|接收者：地市后台
- 触发事件：用户触发
- 数据移动：
  [E] 点击删除轮播组件 → 数据组：删除指令 → 数据属性：组件ID、组件数据、用户ID
  [W] 删除轮播图组件数据 → 数据组：轮播组件列表 → 数据属性：组件ID、选择海报、自动轮播、轮播圆点、图片高度

示例5：定时同步（3步：E→R→W）
- 功能过程：小福包产品数据同步
- 用户：发起者：操作员|接收者：地市后台
- 触发事件：定时触发
- 数据移动：
  [E] 定时凌晨2点更新小福包产品列表数据 → 数据组：列表更新指令 → 数据属性：小福包名称、编码
  [R] 调用小福包产品列表查询接口获取产品列表数据 → 数据组：小福包产品表格 → 数据属性：ID、小福包标识、类型、名称、费用
  [W] 解析并对本地表执行新增/更新/删除 → 数据组：列表响应 → 数据属性：产品信息、字段排序、列表组合

示例6：简单表单（2步：E→X）
- 功能过程：获取装修管理基础配置页面
- 用户：发起者：操作员|接收者：地市后台
- 触发事件：用户触发
- 数据移动：
  [E] 点击获取基础配置页面数据 → 数据组：基础配置表单请求 → 数据属性：页面名称、背景颜色、分享设置
  [X] 返回展示基础配置页面 → 数据组：基础配置表单响应 → 数据属性：页面ID、页面名称、背景颜色、分享设置、主标题、副标题、缩略图
"""


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
