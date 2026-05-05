"""Convert .docx to Markdown format and build module tree from Markdown."""

import logging
import os
import re
from typing import Optional

from docx import Document
from docx.enum.style import WD_STYLE_TYPE

from cosmic_tool.models import FunctionModule

logger = logging.getLogger('cosmic_tool.docx_to_md')


def _inline_formatting(run) -> str:
    """Convert a run's text with inline markdown formatting."""
    text = run.text
    if not text:
        return ""

    # Bold
    if run.bold:
        text = f"**{text}**"
    # Italic
    if run.italic:
        text = f"*{text}*"

    return text


def _heading_level(paragraph) -> Optional[int]:
    """Detect heading level from paragraph style."""
    style = paragraph.style
    if style is None:
        return None

    # Check by style name (e.g. 'Heading 1', 'Heading 2', ...)
    sname = style.name or ""
    for level in range(1, 7):
        if sname.lower() == f"heading {level}":
            return level

    # Check by built-in style type
    if style.builtin:
        from docx.enum.style import WD_STYLE_TYPE
        if style.type == WD_STYLE_TYPE.PARAGRAPH:
            for level in range(1, 7):
                if sname.lower() == f"heading {level}":
                    return level

    return None


def _is_list_item(paragraph) -> Optional[str]:
    """Check if paragraph is a list item. Returns '-' for unordered, '1.' for ordered, None otherwise."""
    style = paragraph.style
    if style is None or style.name is None:
        return None

    sname = style.name.lower()

    # Unordered list
    if sname in ('list bullet', 'list bullet 2', 'list bullet 3',
                 'unordered list', 'bullet', 'bulleted list'):
        indent = sname.count('2') + sname.count('3')  # rough indent level
        prefix = "  " * indent + "- "
        return prefix

    # Ordered list
    if sname in ('list number', 'list number 2', 'list number 3',
                 'ordered list', 'numbered list'):
        indent = sname.count('2') + sname.count('3')
        prefix = "  " * indent + "1. "
        return prefix

    return None


def _section_config() -> dict:
    """Return hardcoded chapter detection config."""
    return {'section_number': '4', 'section_keyword': '功能需求'}


def _find_chapter_boundaries(doc, section_config: dict) -> tuple[int, int]:
    """Find paragraph index range for the functional requirements chapter.

    Detection priority:
      1. ###文档开始### marker → use its style to find chapter boundaries
      2. Text match: "4." + "功能需求" for start, "5." for end
      3. Fallback: full document

    Returns (start_idx, end_idx) — start is inclusive, end is exclusive.
    """
    section_number = str(section_config.get('section_number', '4'))
    section_keyword = section_config.get('section_keyword', '功能需求')
    next_number = str(int(section_number) + 1)

    paragraphs = doc.paragraphs

    # ── 1. Style-based (Format B): template section_style + "功能需求" ──
    try:
        from cosmic_tool.docx_parser import _get_template_scheme
        ts = _get_template_scheme()
        if ts:
            section_style = ts.get('toc', {}).get('section_style', '')
            if section_style:
                for i, p in enumerate(paragraphs):
                    sid = p.style.style_id if p.style else ''
                    if sid == section_style and section_keyword in p.text:
                        for j in range(i + 1, len(paragraphs)):
                            p2 = paragraphs[j]
                            s2 = p2.style.style_id if p2.style else ''
                            if s2 == section_style and p2.text.strip():
                                logger.info(f"样式检测: chapter=[{i}..{j})")
                                return i, j
                        return i, len(paragraphs)
    except Exception:
        pass

    # ── 2. Marker-based detection (Format A: ###文档开始###) ──
    marker_start = -1
    for i, p in enumerate(paragraphs):
        if '###文档开始###' in p.text:
            marker_start = i
            break
    if marker_start >= 0:
        marker_end = len(paragraphs)
        for j in range(marker_start + 1, len(paragraphs)):
            text = re.sub(r'[\s]', '', paragraphs[j].text.strip()) if paragraphs[j].text else ""
            if text and (text.startswith(f'{next_number}.') or '附加值' in text):
                marker_end = j
                break
        logger.info(f"标记检测: chapter=[{marker_start}..{marker_end})")
        return marker_start, marker_end

    # ── Text-based detection ──
    start = -1
    end = len(paragraphs)

    for i, p in enumerate(paragraphs):
        text = re.sub(r'[\s]', '', p.text.strip()) if p.text else ""
        if not text:
            continue
        if start < 0:
            if text.startswith(f'{section_number}.') and section_keyword in text:
                start = i
        else:
            if text.startswith(f'{next_number}.'):
                end = i
                break

    if start < 0:
        logger.warning(
            f"未找到章节「{section_number}.{section_keyword}」，"
            f"将转换全文"
        )
        # 诊断：列出开头接近的段落，便于排查
        candidates = []
        for p in paragraphs:
            t = re.sub(r'[\s]', '', p.text.strip() or "")
            if not t:
                continue
            if f'{section_number}.' in t[:10] or section_keyword in t:
                candidates.append(p.text.strip()[:80])
        if candidates:
            logger.warning(f"  附近匹配段落: {candidates[:8]}")
        return 0, len(paragraphs)

    logger.info(f"定位到「第{section_number}章 {section_keyword}」: 段落[{start}..{end})")
    return start, end


def _flush_list_buffer(list_buffer: list, md_lines: list) -> None:
    """Flush accumulated list items into md_lines."""
    if list_buffer:
        md_lines.extend(list_buffer)
        md_lines.append("")
        list_buffer.clear()


def _process_paragraph(para, md_lines: list, list_buffer: list,
                       force_heading: int | None = None) -> None:
    """Convert a single paragraph to Markdown and append to md_lines.

    force_heading: if set, output as this heading level (bypasses style/marker detection).
    """
    raw_text = para.text.strip()
    text = re.sub(r'###[^#]+###', '', raw_text)

    if not text:
        if list_buffer:
            _flush_list_buffer(list_buffer, md_lines)
        elif md_lines and md_lines[-1] != "":
            md_lines.append("")
        return

    # Forced heading (e.g. functional processes in marker mode)
    if force_heading:
        _flush_list_buffer(list_buffer, md_lines)
        md_lines.append(f"\n{'#' * force_heading} {text}\n")
        return

    # Marker-defined heading
    marker_level = _detect_marker_level(raw_text)
    if marker_level:
        _flush_list_buffer(list_buffer, md_lines)
        md_lines.append(f"\n{'#' * marker_level} {text}\n")
        return

    # Word heading style heading
    hl = _heading_level(para)
    if hl is not None:
        _flush_list_buffer(list_buffer, md_lines)
        md_lines.append(f"\n{'#' * hl} {text}\n")
        return

    # Everything else: plain text (no bold/italic/list formatting)
    if list_buffer:
        _flush_list_buffer(list_buffer, md_lines)
    md_lines.append(text)
    md_lines.append("")


def _detect_marker_level(text: str) -> int | None:
    """Check if text contains a level marker and return corresponding markdown heading level.

    ###一级模块### → 2 (##)  → L1 in markdown
    ###二级模块### → 3 (###) → L2
    ###三级模块### → 4 (####) → L3
    ###文档开始### → 1 (#) → chapter
    """
    if '###一级模块###' in text:
        return 2
    if '###二级模块###' in text:
        return 3
    if '###三级模块###' in text:
        return 4
    if '###文档开始###' in text:
        return 1
    if '###功能过程###' in text:
        return 5
    return None


def convert_to_md(docx_path: str, output_path: Optional[str] = None) -> str:
    """Convert a .docx file to Markdown text.

    仅提取「第4章 功能需求」章节段落，不解析全文。
    未找到第4章时降级为转换全文。

    Args:
        docx_path: Path to the .docx file.
        output_path: If provided, write the markdown to this file.

    Returns:
        The markdown content as a string.
    """
    logger.info(f"正在转换Word文档为Markdown（仅第4章 功能需求）: {docx_path}")

    doc = Document(docx_path)
    chapter_start, chapter_end = _find_chapter_boundaries(doc, _section_config())

    md_lines: list[str] = []
    list_buffer: list[str] = []
    in_process_mode = False  # after ###功能过程###, Normal paragraphs → ##### headings

    from docx.oxml.ns import qn
    body = doc.element.body
    p_idx = 0

    for child in body:
        if child.tag == qn('w:p') and chapter_start <= p_idx < chapter_end:
            para = doc.paragraphs[p_idx]
            raw = para.text.strip()
            # Switch to process mode when hitting ###功能过程### marker
            if '###功能过程###' in raw:
                in_process_mode = True
            # In process mode: Normal(1) paragraphs without markers → #####
            sname = para.style.name if para.style else ''
            sid = para.style.style_id if para.style else ''
            is_normal = (sname == 'Normal' or sid == '1' or sname == '')
            has_marker = any(m in raw for m in ('###文档开始###', '###一级模块###',
                                                  '###二级模块###', '###三级模块###',
                                                  '###功能过程###'))
            if in_process_mode and is_normal and not has_marker:
                _process_paragraph(para, md_lines, list_buffer, force_heading=5)
            else:
                _process_paragraph(para, md_lines, list_buffer)
        p_idx += 1
        if p_idx >= chapter_end:
            break

    # Flush remaining list buffer
    _flush_list_buffer(list_buffer, md_lines)

    # Clean up: collapse 3+ consecutive newlines to 2
    md_text = "\n".join(md_lines)
    md_text = re.sub(r'\n{3,}', '\n\n', md_text).strip()

    if output_path:
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(md_text)
        logger.info(f"Markdown已保存: {output_path}")

    logger.info(f"Word转Markdown完成: {len(md_text)} 字符")
    return md_text


def get_project_name_from_md(md_path: str) -> str:
    """Extract project name from the first significant heading in Markdown."""
    try:
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return ""

    # First heading containing 需求
    for m in re.finditer(r'^#{1,6}\s+(.+)$', content, re.MULTILINE):
        text = m.group(1).strip()
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        if '需' in text and '求' in text:
            return text
    # Fallback: first h1 or h2
    for m in re.finditer(r'^#{1,2}\s+(.+)$', content, re.MULTILINE):
        text = m.group(1).strip()
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        if text:
            return text
    return ""


def build_modules_from_md(md_path: str) -> list[FunctionModule]:
    """Build FunctionModule tree from a raw Markdown document.

    Parses Markdown headings (#/##/###/etc.) to infer the
    L1/L2/L3 module hierarchy.  Text between an L3 heading and
    the next heading is used as the L3 description.  Headings
    deeper than L3 are treated as functional processes.
    """
    with open(md_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # ── Collect all headings ──
    headings: list[tuple[int, str, int]] = []  # (md_level, text, line_idx)
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

    # ── Auto-detect heading → module level mapping ──
    level_counts: dict[int, int] = {}
    for level, _, _ in headings:
        level_counts[level] = level_counts.get(level, 0) + 1

    used_levels = sorted(level_counts.keys())

    # Map heading levels → module levels
    # If topmost heading is a chapter title (contains 需求), skip it for level mapping
    start_idx = 0
    top_text = headings[0][1]
    if len(used_levels) > 1 and level_counts.get(used_levels[0], 0) == 1:
        # Skip the topmost heading if it's a chapter title, not module content
        is_chapter = '功能需求' in top_text or '需求' in top_text
        if is_chapter:
            start_idx = 1

    # Map remaining levels: first → L1(1), second → L2(2), third → L3(3)
    level_map: dict[int, int] = {}
    for i, md_level in enumerate(used_levels[start_idx:start_idx + 3]):
        level_map[md_level] = i + 1

    deeper_levels = set(used_levels[start_idx + 3:])  # functional process candidates

    # ── Walk content to build modules ──
    modules: list[FunctionModule] = []
    registered_l1: set[str] = set()
    registered_l2: set[str] = set()
    registered_l3: set[str] = set()
    current_l1: Optional[str] = None
    current_l2: Optional[str] = None
    current_l3: Optional[str] = None
    l3_descriptions: dict[str, list[str]] = {}
    l3_processes: dict[str, list[str]] = {}

    def _add_module(name: str, level: int, parent: Optional[str] = None) -> None:
        registry = {1: registered_l1, 2: registered_l2, 3: registered_l3}.get(level, set())
        if name not in registry:
            modules.append(FunctionModule(name=name, level=level, parent=parent))
            registry.add(name)

    for md_level, text, line_idx in headings:
        if md_level in level_map:
            mod_level = level_map[md_level]
            if mod_level == 1:
                current_l1 = text
                current_l2 = None
                current_l3 = None
                _add_module(text, 1)
            elif mod_level == 2:
                current_l2 = text
                current_l3 = None
                _add_module(text, 2, current_l1)
            elif mod_level == 3:
                current_l3 = text
                l3_descriptions.setdefault(text, [])
                l3_processes.setdefault(text, [])
                _add_module(text, 3, current_l2)
        elif md_level in deeper_levels and current_l3:
            # Functional process (heading deeper than L3)
            if text not in l3_processes.get(current_l3, []):
                l3_processes.setdefault(current_l3, []).append(text)

    # ── Extract L3 descriptions and processes (text between L3 heading and next heading) ──
    for i in range(len(headings)):
        md_level, text, line_idx = headings[i]
        if md_level not in level_map or level_map[md_level] != 3:
            continue
        l3_name = text
        next_line = headings[i + 1][2] if i + 1 < len(headings) else len(lines)

        desc_parts: list[str] = []
        for j in range(line_idx + 1, next_line):
            stripped = lines[j].strip()
            if not stripped or stripped.startswith('|') or stripped.startswith('---'):
                continue
            if stripped.startswith('#'):
                continue
            # "功能描述：" lines → description; all other lines → processes
            if stripped.startswith('功能描述：') or stripped.startswith('功能描述:'):
                desc_parts.append(stripped)
            elif len(stripped) <= 50:
                # Short line → process name
                if stripped not in l3_processes.get(l3_name, []):
                    l3_processes.setdefault(l3_name, []).append(stripped)
        if desc_parts:
            desc = ' '.join(desc_parts)[:500]
            l3_descriptions.setdefault(l3_name, [])
            l3_descriptions[l3_name].append(desc)

    # ── Attach descriptions and processes to L3 modules ──
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
