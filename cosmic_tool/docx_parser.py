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


def _get_paragraphs(root: ET.Element) -> list[dict]:
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

        if full_text:
            paragraphs.append({'style': style, 'text': full_text})
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
    all_paras = _get_paragraphs(root)
    heading_paras = _filter_heading_paragraphs(all_paras)

    if not heading_paras:
        logger.warning("未找到标题段落，回退到硬编码解析器")
        return build_module_tree(docx_path)

    prompt_lines = ["以下是需求文档中的段落（样式ID + 文本）：\n"]
    for i, p in enumerate(heading_paras, 1):
        prompt_lines.append(f"[{i}] [style:{p['style']}] {p['text']}")
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

        stop_reason = getattr(response, 'stop_reason', None) or ''
        if stop_reason == 'max_tokens':
            logger.warning("AI输出被截断，结果可能不完整")

        raw_modules = _parse_ai_heading_response(resp_text)

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


def _parse_section_hierarchy(paras: list[dict]) -> dict[str, dict]:
    """Parse the TOC-style section headings to build the L1/L2 hierarchy.

    Style mapping: 12=Heading1, 14=Heading2, 9=Heading3
    Only Section 4 (功能需求) is relevant.

    Returns dict: {name: {level, parent, children}}
    """
    hierarchy = {}
    current_l1 = None
    in_section_4 = False

    for p in paras:
        text = p['text']
        style = p['style']

        if style == '12':
            if text.startswith('4.') and '功能需求' in text:
                in_section_4 = True
            elif in_section_4:
                # Reached section 5 - stop
                break
            continue

        if not in_section_4:
            continue

        if style == '14':  # L1
            name = _clean_name(text)
            current_l1 = name
            hierarchy[name] = {'level': 1, 'parent': None, 'children': []}

        elif style == '9':  # L2
            name = _clean_name(text)
            hierarchy[name] = {'level': 2, 'parent': current_l1, 'children': []}
            if current_l1:
                hierarchy.setdefault(current_l1, {'level': 1, 'parent': None, 'children': []})
                hierarchy[current_l1]['children'].append(name)

    return hierarchy


def _parse_detail_section(paras: list[dict]) -> tuple[list[FunctionModule], dict[str, list[str]]]:
    """Parse the detailed function description section.

    Style mapping: 5=L1, 7=L2, 8=L3(leaf functions), 6=process names or descriptions.

    Returns (l3_modules, processes) where:
      - l3_modules: list of FunctionModule at level 3
      - processes: {l3_name: [process_names]}
    """
    l3_modules = []
    processes = {}
    current_l2 = None
    current_l3 = None
    in_detail = False

    for p in paras:
        text = p['text']
        style = p['style']

        # Detect detail section start
        if not in_detail and style in ('5', '7', '8', '6'):
            if style == '5':
                in_detail = True
            else:
                continue
        if not in_detail:
            continue
        if style == '4' and '功附加值调整因子' in text:
            break

        if style == '5':
            current_l2 = None
            current_l3 = None

        elif style == '7':
            current_l2 = text
            current_l3 = None

        elif style == '8':
            current_l3 = text
            l3_modules.append(FunctionModule(
                name=text, level=3, description="", parent=current_l2
            ))
            processes.setdefault(text, [])

        elif style == '6' and current_l3:
            if text.startswith('功能描述：'):
                desc = text[5:].strip()
                for m in reversed(l3_modules):
                    if m.name == current_l3:
                        m.description = desc
                        break
            else:
                # Functional process name
                if text not in processes.get(current_l3, []):
                    processes.setdefault(current_l3, []).append(text)

    return l3_modules, processes


def build_module_tree(docx_path: str) -> list[FunctionModule]:
    """Build a complete module tree from a docx requirements document.

    Returns a flat list of FunctionModules with parent pointers.
    """
    root = _read_docx_xml(docx_path)
    paras = _get_paragraphs(root)

    # Parse hierarchy from section headings
    hierarchy = _parse_section_hierarchy(paras)

    # Parse detailed function descriptions
    l3_modules, processes = _parse_detail_section(paras)

    # Build result: L1 + L2 from hierarchy, L3 from detail section
    result = []
    l1_names_added = set()
    l2_names_added = set()

    # Add L1 and L2 modules
    for name, info in hierarchy.items():
        if info['level'] == 1 and name not in l1_names_added:
            result.append(FunctionModule(name=name, level=1, parent=None))
            l1_names_added.add(name)
        elif info['level'] == 2 and name not in l2_names_added:
            result.append(FunctionModule(name=name, level=2, parent=info['parent']))
            l2_names_added.add(name)

    # Add L3 modules from detail section and attach functional processes
    for m in l3_modules:
        m.children = processes.get(m.name, [])
        result.append(m)

    return result


def get_project_name(docx_path: str) -> str:
    """Extract project name from the docx (first heading)."""
    root = _read_docx_xml(docx_path)
    paras = _get_paragraphs(root)
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
