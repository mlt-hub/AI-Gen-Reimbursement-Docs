"""Extract function module tree from .docx requirements document."""

import re
import zipfile
import xml.etree.ElementTree as ET
from typing import Optional

from .models import FunctionModule

NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}


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
