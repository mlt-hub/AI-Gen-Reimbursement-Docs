"""Markdown handler for COSMIC decomposition — export, fill, and parse."""

import logging
import re
import os
from datetime import date
from typing import Optional

from cosmic_tool.constants import DEFAULT_MODEL, DEFAULT_INITIATOR, DEFAULT_RECEIVER
from cosmic_tool.models import CosmicItem, DataMovement
from cosmic_tool.docx_parser import FunctionModule, get_module_by_name

logger = logging.getLogger('cosmic_tool.md_handler')


HEADER_TEMPLATE = """# COSMIC 功能点拆分表

**项目名称**：{project_name}
**生成日期**：{date}
**说明**：每个 ### 行代表一个功能过程。请为每个功能过程填写 COSMIC 数据移动表格。
   - 移动类型：E=Entry, X=eXit, R=Read, W=Write
   - 首步必为 E，末步必为 W 或 X
   - 每个过程至少 2 步

"""


def export_empty_md(
    modules: list[FunctionModule],
    project_name: str,
    output_path: str
) -> None:
    """Generate an empty MD template with module tree and blank COSMIC tables."""
    l1_modules = [m for m in modules if m.level == 1]
    l3_modules = [m for m in modules if m.level == 3]

    lines = [HEADER_TEMPLATE.format(project_name=project_name, date=date.today())]

    for l1 in l1_modules:
        l2_modules = [m for m in modules if m.level == 2 and m.parent == l1.name]
        if not l2_modules:
            continue

        for l2 in l2_modules:
            l3s = [m for m in l3_modules if m.parent == l2.name]
            if not l3s:
                continue

            for l3 in l3s:
                lines.append(f"\n## {l1.name} > {l2.name} > {l3.name}\n")
                if l3.description:
                    lines.append(f"功能描述：{l3.description}\n")

                if not l3.children:
                    # No functional processes identified — leave a placeholder
                    lines.append("（该模块无明确功能过程）\n")
                    continue

                for child in l3.children:
                    lines.append(f"### {child}\n")
                    lines.append("发起者： | 接收者：\n")
                    lines.append("触发事件：\n")
                    lines.append("\n")
                    lines.append("| 序号 | 子过程描述 | 移动类型 | 数据组 | 数据属性 | 复用度 | CFP |\n")
                    lines.append("|------|-----------|---------|--------|---------|-------|-----|\n")
                    lines.append("| 1 | | | | | | |\n")
                    lines.append("| 2 | | | | | | |\n")
                    lines.append("\n")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    logger.info(f"模板MD已生成: {output_path}")


def export_filled_md(
    modules: list[FunctionModule],
    items: list[CosmicItem],
    project_name: str,
    output_path: str
) -> None:
    """Write MD with COSMIC items filled in."""
    lines = [HEADER_TEMPLATE.format(project_name=project_name, date=date.today())]

    # Group items by (l1, l2, l3) for section organization
    l3_modules = {m.name: m for m in modules if m.level == 3}
    item_groups: dict[tuple[str, str, str], list[CosmicItem]] = {}
    for item in items:
        key = (item.module_l1, item.module_l2, item.module_l3)
        item_groups.setdefault(key, []).append(item)

    l1_modules = [m for m in modules if m.level == 1]

    for l1 in l1_modules:
        l2_modules = [m for m in modules if m.level == 2 and m.parent == l1.name]
        if not l2_modules:
            continue

        for l2 in l2_modules:
            l3s = [m for m in modules if m.level == 3 and m.parent == l2.name]
            if not l3s:
                continue

            for l3 in l3s:
                key = (l1.name, l2.name, l3.name)
                proc_items = item_groups.get(key, [])
                desc = l3.description or ""

                lines.append(f"\n## {l1.name} > {l2.name} > {l3.name}\n")
                if desc:
                    lines.append(f"功能描述：{desc}\n")

                if not proc_items:
                    lines.append("（该模块无拆分数据）\n")
                    continue

                for item in proc_items:
                    lines.append(f"### {item.process}\n")
                    # Show warnings below process name
                    if item.warnings:
                        for w in item.warnings:
                            lines.append(f"> ⚠ {w}\n")
                    # item.user format: "发起者：操作员|接收者：地市后台"
                    user_line = item.user.replace("|", " | ")
                    lines.append(f"{user_line}\n")
                    lines.append(f"触发事件：{item.trigger}\n")
                    lines.append("\n")
                    lines.append("| 序号 | 子过程描述 | 移动类型 | 数据组 | 数据属性 | 复用度 | CFP |\n")
                    lines.append("|------|-----------|---------|--------|---------|-------|-----|\n")
                    for m in item.movements:
                        attrs = m.data_attrs or ""
                        mt = m.move_type
                        if m.move_type_flagged:
                            mt = f"~~{mt}~~"  # strikethrough to indicate fuzzy match
                        lines.append(f"| {m.order} | {m.sub_process} | {mt} | {m.data_group} | {attrs} | {m.reuse} | |\n")
                    lines.append("\n")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    logger.info(f"已填充MD生成: {output_path}")


def _extract_project_name_from_md_lines(text: str, lines: list[str]) -> str:
    """从 Markdown 文本中提取项目名称。"""
    for line in lines:
        m = re.match(r'\*\*项目名称\*\*\s*[：:]\s*(.+)', line)
        if m:
            return m.group(1).strip()
    m2 = re.match(r'项目名称[：:]\s*(.+)', text)
    if m2:
        return m2.group(1).strip()
    return ""


class _ParseState:
    """parse_md_to_items 的解析上下文 —— 封装可变状态和 flush 逻辑。"""
    def __init__(self, project_name: str):
        self.project_name = project_name
        self.items: list[CosmicItem] = []
        self.l1 = self.l2 = self.l3 = ""
        self.process = ""
        self.user = ""
        self.trigger = ""
        self.movements: list[DataMovement] = []
        self.in_table = False

    def flush(self):
        if self.process and self.movements:
            self.items.append(CosmicItem(
                project=self.project_name,
                module_l1=self.l1,
                module_l2=self.l2,
                module_l3=self.l3,
                user=self.user,
                trigger=self.trigger,
                process=self.process,
                movements=list(self.movements),
            ))
        self.process = ""
        self.user = ""
        self.trigger = ""
        self.movements = []
        self.in_table = False


def parse_md_to_items(md_path: str) -> list[CosmicItem]:
    """Parse a (possibly edited) MD file back to CosmicItem list."""
    with open(md_path, 'r', encoding='utf-8') as f:
        text = f.read()

    lines = text.split('\n')
    project_name = _extract_project_name_from_md_lines(text, lines)
    ctx = _ParseState(project_name)

    for line in lines:
        stripped = line.strip()

        # Detect L3 module section: ## L1 > L2 > L3
        m_l3 = re.match(r'^##\s+(.+?)\s*>\s*(.+?)\s*>\s*(.+?)\s*$', stripped)
        if m_l3:
            ctx.flush()
            ctx.l1 = m_l3.group(1).strip()
            ctx.l2 = m_l3.group(2).strip()
            ctx.l3 = m_l3.group(3).strip()
            continue

        # Detect functional process: ### name
        m_proc = re.match(r'^###\s+(.+)$', stripped)
        if m_proc:
            ctx.flush()
            ctx.process = m_proc.group(1).strip()
            continue

        # Detect user line
        if '发起者' in stripped and '|' in stripped:
            m_user = re.match(r'发起者[：:]\s*(.*?)\s*[|]\s*接收者[：:]\s*(.*)', stripped)
            if m_user:
                ctx.user = f"发起者：{m_user.group(1).strip()}|接收者：{m_user.group(2).strip()}"
            continue

        # Detect trigger event
        if '触发事件' in stripped or '触发' in stripped:
            m_trig = re.match(r'触发事件[：:]\s*(.*)', stripped)
            if m_trig:
                ctx.trigger = m_trig.group(1).strip()
                continue
            m_trig2 = re.match(r'触发[：:]\s*(.*)', stripped)
            if m_trig2:
                ctx.trigger = m_trig2.group(1).strip()
                continue

        # Detect table row
        if stripped.startswith('|') and stripped.endswith('|'):
            cells = [c.strip() for c in stripped.split('|')]
            cells = [c for c in cells if c != '']
            if len(cells) >= 5:
                if all(c.replace('-', '').strip() == '' for c in cells[1:4]):
                    continue
                if cells[0].strip() == '序号' or cells[0].strip() == '序号' in cells[0]:
                    ctx.in_table = True
                    continue

                if ctx.in_table and ctx.process:
                    order_str = cells[0].strip() if len(cells) > 0 else ""
                    sub_process = cells[1].strip() if len(cells) > 1 else ""
                    move_type = cells[2].strip().upper() if len(cells) > 2 else "E"
                    data_group = cells[3].strip() if len(cells) > 3 else ""
                    data_attrs = cells[4].strip() if len(cells) > 4 else ""
                    reuse = cells[5].strip() if len(cells) > 5 else "新增"

                    if not sub_process and not move_type:
                        continue

                    if move_type not in ('E', 'X', 'R', 'W'):
                        move_type = 'E'

                    try:
                        order = int(order_str) if order_str else len(ctx.movements) + 1
                    except ValueError:
                        order = len(ctx.movements) + 1

                    ctx.movements.append(DataMovement(
                        order=order, sub_process=sub_process, move_type=move_type,
                        data_group=data_group, data_attrs=data_attrs, reuse=reuse,
                    ))

    ctx.flush()

    if ctx.items:
        logger.info(f"从MD解析到 {len(ctx.items)} 个已有功能过程（将被保留）")
    return ctx.items


def fill_md_with_ai(
    md_path: str,
    modules: list[FunctionModule],
    project_name: str,
    api_key: str,
    model: str = DEFAULT_MODEL,
    base_url: Optional[str] = None,
    user_default_initiator: str = DEFAULT_INITIATOR,
    user_default_receiver: str = DEFAULT_RECEIVER,
    user_initiator_rules: list[tuple[str, str]] | None = None,
    user_receiver_rules: list[tuple[str, str]] | None = None,
) -> None:
    """Read MD, call AI to fill empty tables, write back."""
    from cosmic_tool.cosmic_llm import generate_cosmic_items

    # Parse existing items from MD (if any were manually filled)
    existing_items = parse_md_to_items(md_path)

    # Build a set of already-filled processes to skip
    filled_keys = set()
    for item in existing_items:
        filled_keys.add((item.module_l1, item.module_l2, item.module_l3, item.process))

    # Get L3 modules
    l3_modules = [m for m in modules if m.level == 3]
    total = len(l3_modules)

    logger.info(f"正在AI填充 {total} 个模块的COSMIC数据...")

    # Generate all items (existing LLM logic, skips nothing — generates fresh)
    all_items = generate_cosmic_items(
        modules=modules,
        project_name=project_name,
        api_key=api_key,
        model=model,
        base_url=base_url,
        user_default_initiator=user_default_initiator,
        user_default_receiver=user_default_receiver,
        user_initiator_rules=user_initiator_rules,
        user_receiver_rules=user_receiver_rules,
    )

    # Merge: AI items are the base; existing items with real content override
    item_map = {}
    for item in all_items:
        key = (item.module_l1, item.module_l2, item.module_l3, item.process)
        item_map[key] = item

    for item in existing_items:
        key = (item.module_l1, item.module_l2, item.module_l3, item.process)
        if item.movements:
            # Existing item has real content — override AI
            item_map[key] = item

    merged = list(item_map.values())

    # Write filled MD
    export_filled_md(modules, merged, project_name, md_path)
    logger.info(f"MD已更新: {md_path}")


def get_project_name_from_md(md_path: str) -> str:
    """从 Markdown 中提取项目名称（首个含'需求'的标题）。"""
    try:
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return ""

    for m in re.finditer(r'^#{1,6}\s+(.+)$', content, re.MULTILINE):
        text = m.group(1).strip()
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        if '需' in text and '求' in text:
            return text
    for m in re.finditer(r'^#{1,2}\s+(.+)$', content, re.MULTILINE):
        text = m.group(1).strip()
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        if text:
            return text
    return ""


def build_modules_from_md(md_path: str) -> list[FunctionModule]:
    """从 Markdown 标题层级解析功能模块树（L1/L2/L3/功能过程）。"""
    with open(md_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    headings: list[tuple[int, str, int]] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        m = re.match(r'^(#{1,6})\s+(.+)$', stripped)
        if m:
            level = len(m.group(1))
            text = re.sub(r'\*\*(.+?)\*\*', r'\1', m.group(2)).strip()
            headings.append((level, text, i))

    if not headings:
        logger.warning(f"Markdown文件中未找到标题: {md_path}")
        return []

    level_counts: dict[int, int] = {}
    for h_level, _, _ in headings:
        level_counts[h_level] = level_counts.get(h_level, 0) + 1

    sorted_levels = sorted(level_counts.keys())
    if len(sorted_levels) < 3:
        logger.warning(f"Markdown中标题层级不足（{len(sorted_levels)}级），结果可能不完整")

    lvl_map: dict[int, int] = {}
    for i, lvl in enumerate(sorted_levels[:3], 1):
        lvl_map[lvl] = i

    modules: list[FunctionModule] = []
    current_l1: str | None = None
    current_l2: str | None = None
    l3_processes: dict[str, list[str]] = {}
    l3_descriptions: dict[str, list[str]] = {}
    seen_names: dict[int, set[str]] = {1: set(), 2: set(), 3: set()}

    for h_level, text, line_idx in headings:
        mapped = lvl_map.get(h_level)
        if mapped is None:
            # 超过3级的作为功能过程
            if current_l3:
                l3_processes.setdefault(current_l3, []).append(text)
            continue

        if mapped == 1:
            current_l1 = text
            current_l2 = None
            current_l3 = None
            if text not in seen_names[1]:
                seen_names[1].add(text)
                modules.append(FunctionModule(name=text, level=1))
        elif mapped == 2:
            current_l2 = text
            current_l3 = None
            if text not in seen_names[2]:
                seen_names[2].add(text)
                modules.append(FunctionModule(name=text, level=2, parent=current_l1))
        elif mapped == 3:
            current_l3 = text
            if text not in seen_names[3]:
                seen_names[3].add(text)
                modules.append(FunctionModule(name=text, level=3, parent=current_l2))
            l3_processes.setdefault(current_l3, [])

        # 收集 L3 描述（标题与下一个标题之间的文本）
        if current_l3:
            desc_parts: list[str] = []
            for j in range(line_idx + 1, len(lines)):
                nxt = lines[j].strip()
                if nxt.startswith('#'):
                    break
                if nxt and not nxt.startswith('>') and not nxt.startswith('|'):
                    desc_parts.append(nxt)
            desc = ' '.join(desc_parts)[:500]
            l3_descriptions.setdefault(current_l3, [])
            l3_descriptions[current_l3].append(desc)

    for m in modules:
        if m.level == 3:
            desc_list = l3_descriptions.get(m.name, [])
            if desc_list:
                m.description = '\n'.join(filter(None, desc_list))
            m.children = l3_processes.get(m.name, [])

    logger.info(f"从Markdown解析到模块层级: "
                f"{len([m for m in modules if m.level==1])}个L1, "
                f"{len([m for m in modules if m.level==2])}个L2, "
                f"{len([m for m in modules if m.level==3])}个L3")
    return modules
