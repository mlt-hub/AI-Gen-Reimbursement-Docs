"""Markdown handler for COSMIC decomposition — export, fill, and parse."""

import logging
import re
import os
from datetime import date
from typing import Optional

from ai_gen_reimbursement_docs.models import FunctionModule
from ai_gen_reimbursement_docs.cosmic_models import CosmicItem, DataMovement
from ai_gen_reimbursement_docs.module_utils import get_module_by_name

logger = logging.getLogger('ai_gen_reimbursement_docs.cosmic_md')


HEADER_TEMPLATE = """# 功能点拆分表

**项目名称**：{project_name}
**生成日期**：{date}
**说明**：每个 ### 行代表一个功能过程。请为每个功能过程填写数据移动表格。
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
            # L3.parent 为 "L1/L2" 格式，需用 L1+L2 路径匹配
            l2_path = f"{l1.name}/{l2.name}"
            l3s = [m for m in l3_modules if m.parent == l2_path or m.parent == l2.name]
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
            l2_path = f"{l1.name}/{l2.name}"
            l3s = [m for m in modules if m.level == 3 and (m.parent == l2_path or m.parent == l2.name)]
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

    logger.debug(f"已填充MD生成: {output_path}")


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
        if self.process:
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
        logger.info(f"从模板解析到 {len(ctx.items)} 个功能过程骨架")
    return ctx.items


def fill_md_with_ai(
    md_path: str,
    modules: list[FunctionModule],
    project_name: str,
    api_key: str,
    model: str = "",
    base_url: Optional[str] = None,
    user_default_initiator: str = "",
    user_default_receiver: str = "",
    user_initiator_rules: list[tuple[str, str]] | None = None,
    user_receiver_rules: list[tuple[str, str]] | None = None,
) -> None:
    """Read MD, call AI to fill empty tables, write back."""
    from ai_gen_reimbursement_docs.cosmic_ai import generate_cosmic_items

    # Get L3 modules
    l3_modules = [m for m in modules if m.level == 3]
    total = len(l3_modules)

    logger.debug(f"正在AI填充 {total} 个三级模块的COSMIC数据...")

    # Generate all items fresh
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

    # Write filled MD
    export_filled_md(modules, all_items, project_name, md_path)
    logger.debug(f"MD已更新: {md_path}")
