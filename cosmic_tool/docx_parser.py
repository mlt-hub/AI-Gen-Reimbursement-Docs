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
        num_id = None
        if pPr is not None:
            numPr = pPr.find('w:numPr', NS)
            if numPr is not None:
                ilvl_elem = numPr.find('w:ilvl', NS)
                if ilvl_elem is not None:
                    ilvl = int(ilvl_elem.get(
                        '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val', 0
                    ))
                num_id_elem = numPr.find('w:numId', NS)
                if num_id_elem is not None:
                    num_id = int(num_id_elem.get(
                        '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val', 0
                    ))

        if full_text:
            style_name = (style_names or {}).get(style, '')
            paragraphs.append({
                'style': style, 'style_name': style_name,
                'text': full_text, 'ilvl': ilvl, 'num_id': num_id,
            })
    return paragraphs


def _clean_name(raw: str) -> str:
    """Clean module name: remove leading numbering, trailing page numbers, and ### markers."""
    name = re.sub(r'^[\d.]+\s+', '', raw).strip()
    name = re.sub(r'\d+$', '', name).strip()
    cleaned = re.sub(r'###.*?###', '', name).strip()
    return cleaned if cleaned else name
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

def _build_modules_from_marks(paras: list[dict]) -> list[FunctionModule] | None:
    """Build module tree from ### markers with strategies.

    Marker format:  ###level:strategy###
      level: 一级模块 / 二级模块 / 三级模块 / 功能过程
      strategy: 标题样式 / 多级列表格式 / 编号格式

    Strategy rules:
      标题样式     → match all paragraphs with the same style_id
      多级列表格式  → match all paragraphs with the same (num_id, ilvl)
      编号格式     → match all paragraphs with the same num_id

    ###文档开始### / ###文档结束### → chapter boundaries (no strategy).
    """
    import re
    pattern = re.compile(r'###(.+?):(.+?)###')
    MARKER_LEVELS = {
        '一级模块': 1, '二级模块': 2, '三级模块': 3, '功能过程': 'process',
    }

    # ── Parse markers ──
    rules = {}  # level -> (strategy, signature)
    doc_start = -1
    doc_end = len(paras)

    for i, p in enumerate(paras):
        text = p.get('text', '')
        if '###文档开始###' in text and ':' not in text:
            doc_start = i
            continue
        if '###文档结束###' in text and ':' not in text:
            doc_end = i
            continue
        m = pattern.search(text)
        if not m:
            continue
        level_name, strategy = m.group(1), m.group(2)
        level = MARKER_LEVELS.get(level_name)
        if level is None:
            continue
        # Extract signature from the marker paragraph
        if strategy == '标题样式':
            sig = ('style', p.get('style', ''))
        elif strategy == '多级列表格式':
            sig = ('ilvl', p.get('num_id'), p.get('ilvl'))
        elif strategy == '编号格式':
            sig = ('numbered', p.get('style', ''))
        else:
            continue
        if sig is None or sig == ('style', '') or sig == ('ilvl', None, None) or sig == ('numbered', ''):
            continue
        if level not in rules:
            rules[level] = []
        rules[level].append((strategy, sig))

    if not rules:
        return None

    # Log rules
    rule_desc = []
    for level_num, rule_list in rules.items():
        for strategy, sig in rule_list:
            label = {1: 'L1', 2: 'L2', 3: 'L3', 'process': 'proc'}.get(level_num, level_num)
            rule_desc.append(f'{label}:{strategy}={sig}')
    logger.info(f"格式A（标记法）: {'; '.join(rule_desc)}")

    # ── Set chapter boundaries ──
    if doc_start < 0:
        for i, p in enumerate(paras):
            if '功能需求' in p.get('text', ''):
                doc_start = i
                break
    if doc_start < 0:
        doc_start = 0

    # ── Walk paragraphs in chapter range, matching rules ──
    modules: list[FunctionModule] = []
    l1_registry: set[str] = set()
    l2_registry: set[str] = set()
    l3_registry: set[str] = set()
    l3_processes: dict[str, list[str]] = {}
    current_l1: str | None = None
    current_l2: str | None = None
    current_l3: str | None = None

    for pi in range(doc_start, min(doc_end, len(paras))):
        p = paras[pi]
        text = p.get('text', '').strip()
        if not text:
            continue
        if '###文档开始###' in text or '###文档结束###' in text:
            continue

        # Clean marker suffixes
        clean_text = re.sub(r'###.+?:.+?###', '', text).strip()
        clean_text = re.sub(r'###[^#]+###', '', clean_text).strip()
        if not clean_text:
            continue

        # Rule matching
        matched_level = None
        for level, rule_list in rules.items():
            for strategy, sig in rule_list:
                if strategy == '标题样式' and sig[0] == 'style':
                    if p.get('style', '') == sig[1]:
                        matched_level = level
                elif strategy == '多级列表格式' and sig[0] == 'ilvl':
                    if (p.get('num_id'), p.get('ilvl')) == (sig[1], sig[2]):
                        matched_level = level
                elif strategy == '编号格式' and sig[0] == 'numbered':
                    if p.get('style', '') == sig[1]:
                        nid = p.get('num_id')
                        if nid is not None and nid != 0:
                            matched_level = level
                if matched_level is not None:
                    break
            if matched_level is not None:
                break

        if matched_level is None:
            continue

        if matched_level == 1:
            current_l1, current_l2, current_l3 = clean_text, None, None
            if clean_text not in l1_registry:
                modules.append(FunctionModule(name=clean_text, level=1))
                l1_registry.add(clean_text)
        elif matched_level == 2:
            current_l2, current_l3 = clean_text, None
            if clean_text not in l2_registry:
                modules.append(FunctionModule(name=clean_text, level=2, parent=current_l1))
                l2_registry.add(clean_text)
        elif matched_level == 3:
            current_l3 = clean_text
            l3_processes[clean_text] = []
            if clean_text not in l3_registry:
                modules.append(FunctionModule(name=clean_text, level=3, parent=current_l2))
                l3_registry.add(clean_text)
        elif matched_level == 'process' and current_l3:
            if clean_text not in l3_processes.get(current_l3, []):
                l3_processes.setdefault(current_l3, []).append(clean_text)

    for m in modules:
        if m.level == 3:
            m.children = l3_processes.get(m.name, [])

    logger.info(
        f"标记策略: "
        f"{len([m for m in modules if m.level==1])}L1 "
        f"{len([m for m in modules if m.level==2])}L2 "
        f"{len([m for m in modules if m.level==3])}L3"
    )
    return modules


_TEMPLATE_SCHEME_CACHE: dict | None = None


def analyze_docx_template(template_path: str) -> dict:
    """Read word_template.docx, detect Heading 1~4 and 正文（缩进） style IDs."""
    from docx import Document
    doc = Document(template_path)

    heading_styles = {}
    process_style = ''

    for p in doc.paragraphs:
        sid = p.style.style_id if p.style else ''
        sname = p.style.name if p.style else ''
        text = p.text.strip()
        if not sid or not text:
            continue
        if 'heading' in sname.lower():
            for level in range(1, 5):
                if sname.lower() == f'heading {level}':
                    heading_styles[level] = sid
        if '正文' in sname and '缩进' in sname and not process_style:
            process_style = sid

    h1 = heading_styles.get(1, '12')
    h2 = heading_styles.get(2, '5')
    h3 = heading_styles.get(3, '7')
    h4 = heading_styles.get(4, '8')

    # End keyword: first Heading 1 after "功能需求"
    end_keyword = ''
    found_func = False
    for p in doc.paragraphs:
        text = p.text.strip()
        sid = p.style.style_id if p.style else ''
        if not found_func:
            if '功能需求' in text:
                found_func = True
            continue
        if sid == h1 and text:
            for suffix in ('说明', '介绍', '概述', '：'):
                if text.endswith(suffix):
                    text = text[:-len(suffix)]
                    break
            end_keyword = text.strip()
            break

    logger.info(
        f"模板样式: H1={h1} H2={h2} H3={h3} H4={h4} "
        f"process={process_style} end_keyword={end_keyword}"
    )

    return {
        'toc': {
            'section_style': h1, 'section_number': '4',
            'section_keyword': '功能需求',
            'l1_style': h2, 'l2_style': h3,
        },
        'detail': {
            'start_style': h2,
            'l2_style': h3, 'l3_style': h4,
            'process_style': process_style,
            'end_style': h1, 'end_keyword': end_keyword,
        },
    }


def _get_template_scheme() -> dict | None:
    """Cached template analysis result."""
    global _TEMPLATE_SCHEME_CACHE
    if _TEMPLATE_SCHEME_CACHE is not None:
        return _TEMPLATE_SCHEME_CACHE
    candidates = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'word_template.docx'),
        os.path.join(os.getcwd(), 'data', 'word_template.docx'),
    ]
    for p in candidates:
        if os.path.exists(p):
            _TEMPLATE_SCHEME_CACHE = analyze_docx_template(p)
            return _TEMPLATE_SCHEME_CACHE
    logger.debug("未找到 word_template.docx，使用硬编码默认方案")
    return None


def _parse_section_hierarchy(paras: list[dict],
                              scheme: dict | None = None) -> dict[str, dict]:
    """Parse the TOC-style section headings to build the L1/L2 hierarchy."""
    s = scheme or {}
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
            if section_keyword in text:
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
    s = scheme or {}
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
    """Build module tree — priority: template-style → markers → hardcoded-defaults."""
    root = _read_docx_xml(docx_path)
    style_names = _load_style_names(docx_path)
    paras = _get_paragraphs(root, style_names)

    # Load scheme if not provided
    s = scheme
    if s is None:
        s = _get_template_scheme()

    from cosmic_tool.config_utils import load_business_config
    biz_cfg = load_business_config()
    parse_by_style = biz_cfg.get('docx_parse_by_template_style', True)
    parse_by_marker = biz_cfg.get('docx_parse_by_marker', True)

    # Priority 1: template-style (Format B)
    if s and parse_by_style:
        toc = s.get('toc') or {}
        detail = s.get('detail') or {}
        logger.info(
            f"格式B（样式法）: "
            f"section={toc.get('section_style')} L1={toc.get('l1_style')} L2={toc.get('l2_style')} "
            f"L3={detail.get('l3_style')} process={detail.get('process_style')}"
        )
        hierarchy = _parse_section_hierarchy(paras, toc)
        l3_mods, procs = _parse_detail_section(paras, detail)
        result = _build_result(hierarchy, l3_mods, procs)
        l1s = [m for m in result if m.level == 1]
        l3s = [m for m in result if m.level == 3]
        has_marker_names = any('###' in m.name for m in result)
        if l1s and l3s and not has_marker_names:
            return result

    # Priority 2: marker-based (Format A)
    if parse_by_marker:
        marked = _build_modules_from_marks(paras)
        if marked is not None:
            return marked

    logger.warning("无法解析模块层级：样式法和标记法均未产生有效结果")
    return []


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
