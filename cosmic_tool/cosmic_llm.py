"""Generate COSMIC decompositions using Claude API."""

import json
import logging
import os
from typing import Optional

from .models import CosmicItem, DataMovement
from .docx_parser import FunctionModule, get_module_by_name

logger = logging.getLogger('cosmic_tool.cosmic_llm')

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
    {"sub_process": "子过程描述", "move_type": "E", "data_group": "数据组名", "data_attrs": "属性1、属性2、属性3"},
    ...
  ]
}
"""


def _build_user(module: FunctionModule, modules: list[FunctionModule]) -> str:
    """Determine the user for a module based on its parent context."""
    parent = get_module_by_name(modules, module.parent) if module.parent else None
    if parent and parent.parent:
        grandparent = get_module_by_name(modules, parent.parent)
        if grandparent and '用户' in grandparent.name:
            return "发起者：操作员|接收者：用户前台"
    if parent and '用户' in parent.name:
        return "发起者：操作员|接收者：用户前台"
    if '用户' in module.name:
        return "发起者：操作员|接收者：用户前台"
    return "发起者：操作员|接收者：地市后台"


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
        for i, m in enumerate(proc.get('movements', []), 1):
            # Validate move_type
            move_type = m.get('move_type', 'E').upper()
            if move_type not in ('E', 'X', 'R', 'W'):
                move_type = 'E'

            data_attrs = m.get('data_attrs', '')
            data_group = m.get('data_group', '')

            movements.append(DataMovement(
                order=i,
                sub_process=m.get('sub_process', ''),
                move_type=move_type,
                data_group=data_group,
                data_attrs=data_attrs
            ))

        items.append(CosmicItem(
            project=project_name,
            module_l1=l1_name or module_name,
            module_l2=l2_name or module_name,
            module_l3=module_name,
            user=proc.get('user', user),
            trigger=proc.get('trigger', trigger),
            process=proc.get('process', ''),
            movements=movements
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

    all_items = []
    total = len(l3_modules)

    logger.info(f"Generating COSMIC decompositions for {total} modules...")

    for idx, l3 in enumerate(l3_modules, 1):
        l2_name = l3.parent or ""
        l1_name = ""
        if l2_name:
            l2 = get_module_by_name(modules, l2_name)
            if l2 and l2.parent:
                l1_name = l2.parent

        user = _build_user(l3, modules)
        trigger = _build_trigger(l3)

        prompt = _build_module_prompt(l3, modules)

        logger.info(f"  [{idx}/{total}] {l1_name} > {l2_name} > {l3.name}...")

        if interactive:
            input("Press Enter to continue (Ctrl+C to skip)...")

        try:
            response = client.messages.create(
                model=model,
                max_tokens=2000,
                temperature=0.1,
                system=SYSTEM_PROMPT + "\n\n## 现有参照示例\n" + _get_examples(),
                messages=[{"role": "user", "content": prompt}]
            )

            resp_text = _extract_text(response.content)
            if not resp_text:
                raise ValueError("No text content in response")
            items = _parse_llm_response(l3.name, user, trigger, resp_text,
                                        project_name, l1_name, l2_name)
            all_items.extend(items)
            logger.info(f"  [{idx}/{total}] → {len(items)} processes")

        except Exception as e:
            logger.warning(f"  [{idx}/{total}] → ERROR: {e}")

    logger.info(f"Total COSMIC items generated: {len(all_items)}")
    return all_items


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
