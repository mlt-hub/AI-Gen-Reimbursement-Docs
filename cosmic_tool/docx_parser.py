"""Extract function module tree from .docx requirements document."""

import json
import logging
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import Optional

from cosmic_tool.models import FunctionModule

NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
logger = logging.getLogger('cosmic_tool.docx_parser')


def _read_docx_xml(path: str) -> ET.Element:
    """Read word/document.xml from a .docx (or macro-enabled) file."""
    with zipfile.ZipFile(path) as z:
        xml_content = z.read('word/document.xml')
    return ET.fromstring(xml_content)


def _load_style_names(docx_path: str) -> dict[str, str]:
    """Load word/styles.xml and map style ID → display name."""
    try:
        import zipfile
        with zipfile.ZipFile(docx_path) as z:
            if 'word/styles.xml' not in z.namelist():
                return {}
            xml_content = z.read('word/styles.xml')
            styles_root = ET.fromstring(xml_content)
            style_names = {}
            for style in styles_root.findall('.//w:style', NS):
                sid = style.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}styleId', '')
                name_elem = style.find('w:name', NS)
                if name_elem is not None:
                    sname = name_elem.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val', '')
                    if sid and sname:
                        style_names[sid] = sname
            return style_names
    except Exception:
        return {}


def _get_paragraphs(root: ET.Element, style_names: dict | None = None) -> list[dict]:
    """Extract paragraphs with style and text from XML."""
    paragraphs = []
    for p in root.findall('.//w:p', NS):
        pPr = p.find('w:pPr', NS)
        style = ""
        if pPr is not None:
            style_elem = pPr.find('w:pStyle', NS)
            if style_elem is not None:
                style = style_elem.get(
                    '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val',
                    ''
                )

        texts = []
        for t in p.findall('.//w:t', NS):
            if t.text:
                texts.append(t.text)
        full_text = ''.join(texts).strip()

        ilvl = None
        if pPr is not None:
            numPr = pPr.find('w:numPr', NS)
            if numPr is not None:
                ilvl_elem = numPr.find('w:ilvl', NS)
                if ilvl_elem is not None:
                    ilvl = int(ilvl_elem.get(
                        '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val', 0
                    ))

        if full_text:
            style_name = (style_names or {}).get(style, '')
            paragraphs.append({
                'style': style, 'style_name': style_name,
                'text': full_text, 'ilvl': ilvl,
            })
    return paragraphs


def _clean_name(raw: str) -> str:
    """Clean module name: remove leading numbering and trailing page numbers."""
    name = re.sub(r'^[\d.]+\s+', '', raw).strip()
    name = re.sub(r'\d+$', '', name).strip()
    return name


_AI_HEADING_SYSTEM_PROMPT = """你是软件需求文档结构分析专家。你需要从需求文档的段落中推断出功能模块的三级层次结构。

## 任务
给定一份软件需求说明书（.docx）中的所有段落（包含Word样式ID和文本内容），你需要推断出功能模块的三级层次：

- **L1（一级模块）**：大的功能领域
- **L2（二级模块）**：一级模块下的子模块
- **L3（三级模块）**：叶子功能点
- 每个L3可能有多个**功能过程**和一段**功能描述**

## 分析要点
1. 段落样式ID：相同样式ID的段落通常处于同一层级
2. 段落文本内容：标题文字通常简短且有层级含义
3. 编号规则：如"4.1"、"4.1.1"等编号暗示层级关系
4. 段落长度：标题段落通常较短（<100字符），内容段落通常较长

## 输出格式
返回严格符合以下结构的JSON（不要包含任何其他文字或markdown代码块标记）：

{
  "modules": [
    {"name": "模块名称", "level": 1, "parent": null, "description": "", "children": []},
    {"name": "模块名称", "level": 2, "parent": "父级L1名称", "description": "", "children": []},
    {"name": "模块名称", "level": 3, "parent": "父级L2名称", "description": "功能描述文字", "children": ["过程1", "过程2"]}
  ]
}

注意：
- modules 数组中是**扁平列表**，每个模块一个条目
- level 只能是 1、2 或 3
- L1模块的 parent 为 null
- L3模块的 description 从"功能描述："开头的段落提取
- L3模块的 children 是功能过程名称列表
- 只包含功能相关的模块（约第4章相关内容），排除背景说明、术语定义、附录等
"""


def _filter_heading_paragraphs(paras: list[dict], max_length: int = 500) -> list[dict]:
    """Filter paragraphs that are likely headings or structured content."""
    filtered = []
    for p in paras:
        text = p['text']
        style = p['style']
        if not style or len(text) > max_length or len(text) < 2:
            continue
        filtered.append(p)
    return filtered


def _extract_ai_text(content_blocks: list) -> str:
    """Extract text from AI response content blocks."""
    for block in content_blocks:
        block_type = getattr(block, 'type', None) or type(block).__name__
        if 'text' in block_type.lower() or block_type in ('text', 'TextBlock'):
            return block.text
    for block in content_blocks:
        if hasattr(block, 'text'):
            return block.text
    return ""


def _clean_json_from_heading(raw: str) -> str:
    """Clean malformed JSON from AI heading response."""
    text = raw.strip()
    text = re.sub(r',\s*([}\]])', r'\1', text)
    text = re.sub(r'//[^\n]*', '', text)
    return text.strip()


def _parse_ai_heading_response(response_text: str) -> list[dict]:
    """Parse AI JSON response into list of raw module dicts."""
    text = response_text.strip()

    if '```json' in text:
        text = text.split('```json')[1]
        if '```' in text:
            text = text.split('```')[0]
    elif '```' in text:
        text = text.split('```')[1]
        if '```' in text:
            text = text.split('```')[0]

    text = text.strip()
    start = text.find('{')
    end = text.rfind('}')
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in AI response")

    json_str = _clean_json_from_heading(text[start:end+1])
    data = json.loads(json_str)
    raw_modules = data.get('modules', [])

    if not raw_modules:
        raise ValueError("No modules found in AI response")

    for i, m in enumerate(raw_modules):
        if 'name' not in m or 'level' not in m:
            raise ValueError(f"Module at index {i} missing required fields (name, level)")

    return raw_modules


def ai_build_module_tree(
    docx_path: str,
    api_key: Optional[str] = None,
    model: str = "deepseek-v4-flash",
    base_url: Optional[str] = None,
) -> list[FunctionModule]:
    """Build module tree using AI to infer heading hierarchy from docx paragraphs.

    Falls back to hardcoded build_module_tree on failure.
    """
    import anthropic

    root = _read_docx_xml(docx_path)
    style_names = _load_style_names(docx_path)
    paras = _get_paragraphs(root, style_names)
    heading_paras = _filter_heading_paragraphs(paras)

    if not heading_paras:
        logger.warning("未找到标题段落，回退到硬编码解析器")
        return build_module_tree(docx_path)

    prompt_lines = ["以下是需求文档中的段落（样式ID + 文本）：\n"]
    for i, p in enumerate(heading_paras, 1):
        ilvl_info = f" ilvl:{p['ilvl']}" if p.get('ilvl') is not None else ""
        prompt_lines.append(f"[{i}] [style:{p['style']}{ilvl_info}] {p['text']}")
    prompt = "\n".join(prompt_lines)
    prompt += "\n\n请根据以上段落，推断功能模块的三级层次结构（L1/L2/L3），每个L3模块的功能过程（children）和功能描述（description）。按指定的JSON格式返回。"

    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY 未设置，回退到硬编码解析器")
        return build_module_tree(docx_path)

    base_url = base_url or os.environ.get("ANTHROPIC_BASE_URL", "")
    client_kwargs = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url

    client = anthropic.Anthropic(**client_kwargs)

    from cosmic_tool.config_utils import load_max_tokens
    max_tokens = load_max_tokens()

    logger.info("AI正在分析文档段落结构并推断模块层级...")

    try:
        _save_heading_prompt(docx_path, prompt)
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=0.1,
            system=_AI_HEADING_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )

        resp_text = _extract_ai_text(response.content)
        if not resp_text:
            raise ValueError("AI响应为空")

        # 提取AI推理过程
        reasoning = _extract_ai_thinking(response.content)

        stop_reason = getattr(response, 'stop_reason', None) or ''
        if stop_reason == 'max_tokens':
            logger.warning("AI输出被截断，结果可能不完整")

        raw_modules = _parse_ai_heading_response(resp_text)

        # 保存heading解析响应及推理过程
        _save_heading_response(docx_path, resp_text, reasoning)

        modules = []
        for rm in raw_modules:
            modules.append(FunctionModule(
                name=rm['name'],
                level=rm['level'],
                description=rm.get('description', ''),
                parent=rm.get('parent'),
                children=rm.get('children', []),
            ))

        logger.info(f"AI解析完成：{len([m for m in modules if m.level==1])}个L1, "
                    f"{len([m for m in modules if m.level==2])}个L2, "
                    f"{len([m for m in modules if m.level==3])}个L3")
        return modules

    except Exception as e:
        logger.warning(f"AI段落解析失败: {e}")
        logger.warning("正在回退到硬编码解析器...")
        return build_module_tree(docx_path)


def _save_heading_prompt(docx_path: str, prompt: str) -> None:
    """Save AI heading parsing prompt to log/ai_prompts/."""
    import os
    from datetime import datetime
    base_log = os.environ.get('COSMIC_LOG_DIR', '') or os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 'log'
    )
    log_dir = os.path.join(base_log, 'ai_prompts')
    os.makedirs(log_dir, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(docx_path))[0]
    safe_name = base_name.replace('/', '_').replace('\\', '_').strip()[:80]
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filepath = os.path.join(log_dir, f"{timestamp}_{safe_name}_parse_heading_prompt.txt")

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"# AI Heading Prompt: {base_name}\n")
        f.write(f"# Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(prompt)
    logger.info(f"AI解析提示词已保存: {filepath}")


def _extract_ai_thinking(content_blocks: list) -> str:
    """Extract thinking/reasoning from AI response content blocks."""
    parts = []
    for block in content_blocks:
        block_type = getattr(block, 'type', None) or type(block).__name__
        if 'thinking' in block_type.lower() or block_type == 'ThinkingBlock':
            text = getattr(block, 'thinking', None) or getattr(block, 'text', '')
            if text:
                parts.append(str(text))
    return "\n\n".join(parts) if parts else ""


def _save_heading_response(docx_path: str, text: str, reasoning: str = "") -> None:
    """Save AI heading parsing response to log/ai_responses/."""
    import os
    from datetime import datetime
    base_log = os.environ.get('COSMIC_LOG_DIR', '') or os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 'log'
    )
    log_dir = os.path.join(base_log, 'ai_responses')
    os.makedirs(log_dir, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(docx_path))[0]
    safe_name = base_name.replace('/', '_').replace('\\', '_').strip()[:80]
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filepath = os.path.join(log_dir, f"{timestamp}_{safe_name}_parse_heading_response.md")

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"# AI Heading Response: {base_name}\n")
        f.write(f"# Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        if reasoning:
            f.write("## AI 判断依据\n\n")
            f.write(reasoning)
            f.write("\n\n---\n\n")
        f.write("## 解析结果\n\n")
        f.write(text)
    logger.info(f"AI解析响应已保存: {filepath}")



def _style_matches(p: dict, style_val: str) -> bool:

    """Check if paragraph matches style, trying both ID and name."""

    return p["style"] == style_val or p.get("style_name", "") == style_val

DEFAULT_TOC_SCHEME = {
    'section_style': '12', 'section_number': '4',
    'section_keyword': '功能需求',
    'l1_style': '14', 'l2_style': '9',
}

DEFAULT_DETAIL_SCHEME = {
    'start_style': '5', 'end_style': '4', 'end_keyword': '功附加值调整因子',
    'l2_style': '7', 'l3_style': '8', 'process_style': '6',
}


def _parse_section_hierarchy(paras: list[dict],
                              scheme: dict | None = None) -> dict[str, dict]:
    """Parse the TOC-style section headings to build the L1/L2 hierarchy."""
    s = scheme or DEFAULT_TOC_SCHEME
    hierarchy = {}
    current_l1 = None
    in_section = False
    section_style = s.get('section_style', '12')
    section_number = s.get('section_number', '4')
    section_keyword = s.get('section_keyword', '功能需求')
    l1_style = s.get('l1_style', '14')
    l2_style = s.get('l2_style', '9')

    for p in paras:
        text = p['text']
        style = p['style']
        sname = p.get('style_name', '')

        if _style_matches(p, section_style):
            if text.startswith(f'{section_number}.') and section_keyword in text:
                in_section = True
                logger.debug(f"[TOC] section标记: style={style} name={sname} text={text[:40]}")
            elif in_section:
                logger.debug(f"[TOC] section结束: style={style} text={text[:40]}")
                break
            continue

        if not in_section:
            continue

        if _style_matches(p, l1_style):
            name = _clean_name(text)
            current_l1 = name
            hierarchy[name] = {'level': 1, 'parent': None, 'children': []}
            logger.debug(f"[TOC] L1: style={style} name={sname} → {name}")

        elif _style_matches(p, l2_style):
            name = _clean_name(text)
            hierarchy[name] = {'level': 2, 'parent': current_l1, 'children': []}
            if current_l1:
                hierarchy.setdefault(current_l1, {'level': 1, 'parent': None, 'children': []})
                hierarchy[current_l1]['children'].append(name)
            logger.debug(f"[TOC] L2: style={style} name={sname} → {name} parent={current_l1}")

    return hierarchy


def _parse_detail_section(paras: list[dict],
                           scheme: dict | None = None) -> tuple[list[FunctionModule], dict[str, list[str]]]:
    """Parse the detailed function description section."""
    s = scheme or DEFAULT_DETAIL_SCHEME
    l3_modules = []
    processes = {}
    current_l2 = None
    current_l3 = None
    in_detail = False

    start_styles = (s['start_style'], s['l2_style'], s['l3_style'], s['process_style'])
    end_style = s.get('end_style', '4')
    end_keyword = s.get('end_keyword', '功附加值调整因子')

    for p in paras:
        text = p['text']
        style = p['style']
        sname = p.get('style_name', '')
        ilvl = p.get('ilvl')

        if not in_detail:
            if _style_matches(p, s['start_style']):
                in_detail = True
                logger.debug(f"[DETAIL] 进入详情: style={style} name={sname} ilvl={ilvl} text={text[:40]}")
            else:
                continue
        if not in_detail:
            continue

        if _style_matches(p, s.get('end_style', '')) and end_keyword in text:
            logger.debug(f"[DETAIL] 详情结束标记: style={style} name={sname} text={text[:40]}，之后仅匹配ilvl功能过程")
            # 不再break，继续用ilvl匹配功能过程

        # 详情区内：按样式解析层级
        if not (_style_matches(p, s.get('end_style', '')) and end_keyword in text):
            if _style_matches(p, s['start_style']):
                current_l2 = None
                current_l3 = None

            if _style_matches(p, s['l2_style']):
                current_l2 = _clean_name(text)
                current_l3 = None
                logger.debug(f"[DETAIL] L2: style={style} name={sname} → {current_l2}")

            elif _style_matches(p, s['l3_style']):
                clean_l3 = _clean_name(text)
                current_l3 = clean_l3
                l3_modules.append(FunctionModule(
                    name=clean_l3, level=3, description="", parent=current_l2
                ))
                processes.setdefault(clean_l3, [])
                logger.debug(f"[DETAIL] L3: style={style} name={sname} → {clean_l3} parent={current_l2}")

        # 用ilvl跟踪当前L3（详情区外也能识别）
        process_ilvl = s.get('process_ilvl')
        if process_ilvl is not None and ilvl == process_ilvl - 1:
            # ilvl比功能过程低一级 → 这是L3标题（即使无样式）
            current_l3 = text.strip()
            # 如果这个L3还不在列表中则添加
            if not any(m.name == current_l3 for m in l3_modules):
                l3_modules.append(FunctionModule(
                    name=current_l3, level=3, description="", parent=current_l2
                ))
                processes.setdefault(current_l3, [])
                logger.debug(f"[DETAIL] L3(ilvl): ilvl={ilvl} → {current_l3}")

        # 匹配功能过程（ilvl匹配，不限是否在详情区内）
        if process_ilvl is not None and ilvl == process_ilvl and current_l3:
            if text not in processes.get(current_l3, []):
                processes.setdefault(current_l3, []).append(text)
                logger.debug(f"[DETAIL] 功能过程(ilvl): {text[:40]} → L3={current_l3}")

    return l3_modules, processes


def _build_result(hierarchy: dict, l3_modules: list, processes: dict) -> list[FunctionModule]:
    """Combine hierarchy + L3 modules into flat FunctionModule list."""
    result = []
    l1_added, l2_added = set(), set()

    for name, info in hierarchy.items():
        if info['level'] == 1 and name not in l1_added:
            result.append(FunctionModule(name=name, level=1, parent=None))
            l1_added.add(name)
        elif info['level'] == 2 and name not in l2_added:
            result.append(FunctionModule(name=name, level=2, parent=info['parent']))
            l2_added.add(name)

    for m in l3_modules:
        m.children = processes.get(m.name, [])
        result.append(m)
    return result


def _validate_tree(modules: list[FunctionModule]) -> bool:
    """Check if module tree has valid L1 and L3 structure."""
    l1 = [m for m in modules if m.level == 1]
    l3 = [m for m in modules if m.level == 3]
    l2 = [m for m in modules if m.level == 2]

    if not l1 or not l3:
        return False

    # All L3 parents must exist
    for m in l3:
        if m.parent and not any(p.name == m.parent for p in l2) and not any(p.name == m.parent for p in l1):
            return False
    return True


def build_module_tree(docx_path: str, scheme: dict | None = None) -> list[FunctionModule]:
    """Build module tree using a single style scheme (default scheme if None)."""
    root = _read_docx_xml(docx_path)
    style_names = _load_style_names(docx_path)
    paras = _get_paragraphs(root, style_names)

    toc_scheme = scheme['toc'] if scheme and 'toc' in scheme else DEFAULT_TOC_SCHEME
    detail_scheme = scheme['detail'] if scheme and 'detail' in scheme else DEFAULT_DETAIL_SCHEME

    hierarchy = _parse_section_hierarchy(paras, toc_scheme)
    l3_modules, processes = _parse_detail_section(paras, detail_scheme)
    return _build_result(hierarchy, l3_modules, processes)


def build_module_tree_with_schemes(docx_path: str, schemes: list[dict]) -> list[FunctionModule]:
    """Try each style scheme and return the first valid result."""
    root = _read_docx_xml(docx_path)
    style_names = _load_style_names(docx_path)
    paras = _get_paragraphs(root, style_names)

    for s in schemes:
        name = s.get('name', 'unnamed')
        logger.debug(f"尝试样式方案: {name}")

        hierarchy = _parse_section_hierarchy(paras, s.get('toc', {}))
        l3_modules, processes = _parse_detail_section(paras, s.get('detail', {}))
        result = _build_result(hierarchy, l3_modules, processes)

        l1c = len([m for m in result if m.level == 1])
        l2c = len([m for m in result if m.level == 2])
        l3c = len([m for m in result if m.level == 3])
        valid = _validate_tree(result)
        logger.debug(f"  方案「{name}」: L1={l1c} L2={l2c} L3={l3c} 有效={valid}")
        if valid:
            logger.info(f"样式方案「{name}」有效 (L1:{l1c} L2:{l2c} L3:{l3c})")
            return result

    logger.warning("所有样式方案均无效，使用默认方案")
    return build_module_tree(docx_path)


def get_project_name(docx_path: str) -> str:
    """Extract project name from the docx (first heading)."""
    root = _read_docx_xml(docx_path)
    style_names = _load_style_names(docx_path)
    paras = _get_paragraphs(root, style_names)
    for p in paras:
        if p['text'] and '需' in p['text'] and '求' in p['text']:
            return p['text']
    return ""


def get_module_by_name(modules: list[FunctionModule], name: str) -> Optional[FunctionModule]:
    """Find a module by name in the flat list."""
    for m in modules:
        if m.name == name:
            return m
    return None


def print_tree(modules: list[FunctionModule]) -> None:
    """Pretty-print the module tree."""
    for m in modules:
        indent = "  " * (m.level - 1)
        print(f"{indent}[L{m.level}] {m.name}")
        if m.description:
            desc = m.description[:80]
            print(f"{indent}    描述: {desc}...")
        if m.children:
            for child in m.children:
                print(f"{indent}     → {child}")
