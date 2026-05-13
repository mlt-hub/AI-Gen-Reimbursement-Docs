"""Markdown 处理单元测试 —— parse_md_to_items, get_project_name_from_md。"""
import tempfile
import os
from pathlib import Path

import pytest
from cosmic_tool.md_handler import parse_md_to_items, get_project_name_from_md


def _write_temp_md(content: str) -> str:
    """将内容写入临时 MD 文件并返回路径。"""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", encoding="utf-8", delete=False
    )
    tmp.write(content)
    tmp.close()
    return tmp.name


SAMPLE_FULL_MD = """**项目名称**：智慧城市管理平台

## 系统管理 > 用户管理 > 用户注册

### 用户注册

发起者：操作员 | 接收者：后台管理员
触发事件：用户点击注册按钮

| 序号 | 子过程 | 数据移动类型 | 数据组 | 数据属性 | 复用 | 备注 |
|------|--------|-------------|--------|----------|------|------|
| 1 | 接收注册请求 | E | 注册信息 | 用户名,密码,手机号 | 新增 | |
| 2 | 校验用户信息 | R | 用户数据 | 用户名 | 复用 | |
| 3 | 写入用户记录 | W | 用户记录 | 用户名,密码,手机号,注册时间 | 新增 | |
| 4 | 返回注册结果 | X | 注册结果 | 成功标志,用户ID | 新增 | |
"""

SAMPLE_MULTI_PROCESS = """**项目名称**：测试系统

## 业务模块 > 订单模块 > 创建订单

### 创建订单

发起者：操作员 | 接收者：系统
触发事件：用户点击提交订单

| 序号 | 子过程 | 数据移动类型 | 数据组 | 数据属性 | 复用 | 备注 |
|------|--------|-------------|--------|----------|------|------|
| 1 | 接收订单数据 | E | 订单数据 | 商品,数量,金额 | 新增 | |
| 2 | 保存订单 | W | 订单记录 | 订单ID,商品,金额 | 新增 | |

## 业务模块 > 订单模块 > 查询订单

### 查询订单

发起者：操作员 | 接收者：系统
触发事件：用户输入查询条件

| 序号 | 子过程 | 数据移动类型 | 数据组 | 数据属性 | 复用 | 备注 |
|------|--------|-------------|--------|----------|------|------|
| 1 | 接收查询条件 | E | 查询条件 | 订单号,日期范围 | 新增 | |
| 2 | 返回查询结果 | X | 订单列表 | 订单ID,状态,金额 | 新增 | |
"""


class TestParseMdToItems:
    def test_parse_basic(self):
        path = _write_temp_md(SAMPLE_FULL_MD)
        try:
            items = parse_md_to_items(path)
            assert len(items) == 1
            item = items[0]
            assert item.module_l1 == "系统管理"
            assert item.module_l2 == "用户管理"
            assert item.module_l3 == "用户注册"
            assert item.process == "用户注册"
            assert "操作员" in item.user
            assert "后台管理员" in item.user
            assert item.trigger == "用户点击注册按钮"
            assert item.total_cfp() == 4
            assert item.movements[0].sub_process == "接收注册请求"
            assert item.movements[0].move_type == "E"
        finally:
            os.unlink(path)

    def test_parse_multiple_processes(self):
        path = _write_temp_md(SAMPLE_MULTI_PROCESS)
        try:
            items = parse_md_to_items(path)
            assert len(items) == 2
            assert items[0].process == "创建订单"
            assert items[1].process == "查询订单"
            assert items[0].total_cfp() == 2
            assert items[1].total_cfp() == 2
        finally:
            os.unlink(path)

    def test_parse_empty_md(self):
        path = _write_temp_md("# 空文件\n\n无数据\n")
        try:
            items = parse_md_to_items(path)
            assert items == []
        finally:
            os.unlink(path)

    def test_project_name_from_marker(self):
        path = _write_temp_md("**项目名称**：测试项目\n\n### 1、模块\n")
        try:
            items = parse_md_to_items(path)
            # 无数据但有项目名
            assert len(items) == 0
        finally:
            os.unlink(path)

    def test_move_types_preserved(self):
        path = _write_temp_md(SAMPLE_FULL_MD)
        try:
            items = parse_md_to_items(path)
            types = [m.move_type for m in items[0].movements]
            assert types == ["E", "R", "W", "X"]
        finally:
            os.unlink(path)

    def test_data_attrs_multivalue(self):
        path = _write_temp_md(SAMPLE_FULL_MD)
        try:
            items = parse_md_to_items(path)
            assert items[0].movements[0].data_attrs == "用户名,密码,手机号"
        finally:
            os.unlink(path)


class TestGetProjectNameFromMd:
    def test_extract_from_heading_with_demand(self):
        path = _write_temp_md(
            "# 关于构建垂直行业场景化营销的需求\n\n## 概述\n"
        )
        try:
            name = get_project_name_from_md(path)
            assert "垂直行业" in name
        finally:
            os.unlink(path)

    def test_extract_from_bold_heading(self):
        path = _write_temp_md(
            "# **智慧城市管理平台需求说明书**\n\n## 背景\n"
        )
        try:
            name = get_project_name_from_md(path)
            assert "智慧城市" in name
        finally:
            os.unlink(path)

    def test_fallback_to_first_heading(self):
        path = _write_temp_md(
            "# 项目概述\n\n无需求关键字\n"
        )
        try:
            name = get_project_name_from_md(path)
            assert name == "项目概述"
        finally:
            os.unlink(path)

    def test_empty_file(self):
        path = _write_temp_md("")
        try:
            name = get_project_name_from_md(path)
            assert name == ""
        finally:
            os.unlink(path)

    def test_missing_file(self):
        name = get_project_name_from_md("/nonexistent/path/test.md")
        assert name == ""
