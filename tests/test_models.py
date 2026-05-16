"""数据模型单元测试 —— FunctionModule, DataMovement, CosmicItem。"""
import pytest
from ai_gen_reimbursement_docs.models import FunctionModule
from ai_gen_reimbursement_docs.cosmic_models import DataMovement, CosmicItem


class TestFunctionModule:
    def test_create_l1_module(self):
        m = FunctionModule(name="系统管理", level=1, description="系统配置维护")
        assert m.name == "系统管理"
        assert m.level == 1
        assert m.description == "系统配置维护"
        assert m.parent is None
        assert m.children == []

    def test_create_with_parent(self):
        m = FunctionModule(name="用户管理", level=2, parent="系统管理")
        assert m.parent == "系统管理"

    def test_children_are_mutable(self):
        parent = FunctionModule(name="系统管理", level=1)
        child = FunctionModule(name="用户管理", level=2, parent="系统管理")
        parent.children.append("用户管理")
        assert parent.children == ["用户管理"]
        assert child.parent == "系统管理"

    def test_default_values(self):
        m = FunctionModule(name="测试", level=3)
        assert m.description == ""
        assert m.parent is None
        assert m.children == []


class TestDataMovement:
    def test_basic_creation(self):
        dm = DataMovement(order=1, sub_process="接收请求", move_type="E",
                          data_group="请求数据", data_attrs="用户名,密码")
        assert dm.order == 1
        assert dm.sub_process == "接收请求"
        assert dm.move_type == "E"
        assert dm.data_group == "请求数据"
        assert dm.data_attrs == "用户名,密码"
        assert dm.reuse == "新增"
        assert dm.move_type_flagged is False

    def test_flagged_move_type(self):
        dm = DataMovement(1, "步骤", "xxxx", "数据组", "属性", "新增", True)
        assert dm.move_type_flagged is True

    def test_custom_reuse(self):
        dm = DataMovement(1, "步骤", "R", "数据组", "属性", reuse="复用")
        assert dm.reuse == "复用"


class TestCosmicItem:
    def _make_item(self, movements=None, warnings=None, user="操作员",
                    trigger="点击注册按钮", process="注册新用户"):
        return CosmicItem(
            project="测试项目",
            module_l1="系统管理", module_l2="用户管理", module_l3="用户注册",
            user=user, trigger=trigger, process=process,
            movements=movements or [],
            warnings=warnings or [],
        )

    def _make_movement(self, order=1, sub="步骤", mt="E", dg="数据组", da="属性"):
        return DataMovement(order, sub, mt, dg, da)

    # ---- total_cfp ----
    def test_total_cfp_zero_when_empty(self):
        item = self._make_item()
        assert item.total_cfp() == 0

    def test_total_cfp_counts_movements(self):
        item = self._make_item(movements=[
            self._make_movement(1), self._make_movement(2), self._make_movement(3),
        ])
        assert item.total_cfp() == 3

    # ---- to_rows ----
    def test_to_rows_empty_movements(self):
        """无 movements 时返回一行，显示 L1/L2/L3/功能过程信息。"""
        item = self._make_item()
        rows = item.to_rows()
        assert len(rows) == 1
        assert rows[0]["module_l1"] == "系统管理"
        assert rows[0]["sub_process"] == ""
        assert rows[0]["move_type"] == ""

    def test_to_rows_basic(self):
        item = self._make_item(movements=[
            DataMovement(1, "接收请求", "E", "请求数据", "用户名,密码"),
        ])
        rows = item.to_rows()
        assert len(rows) == 1
        row = rows[0]
        assert row["project"] == "测试项目"
        assert row["module_l1"] == "系统管理"
        assert row["module_l2"] == "用户管理"
        assert row["module_l3"] == "用户注册"
        assert row["sub_process"] == "接收请求"
        assert row["move_type"] == "E"
        assert row["data_group"] == "请求数据"
        assert row["data_attrs"] == "用户名,密码"
        assert row["reuse"] == "新增"
        assert row["cfp"] == ""
        assert row["move_type_flagged"] is False

    def test_to_rows_user_pipe_replaced(self):
        item = self._make_item(
            user="发起者：操作员|接收者：后台管理员",
            movements=[self._make_movement()],
        )
        row = item.to_rows()[0]
        assert row["user"] == "发起者：操作员\n接收者：后台管理员"

    def test_to_rows_warnings_only_on_first_row(self):
        item = self._make_item(
            movements=[self._make_movement(1), self._make_movement(2)],
            warnings=["数据组重复", "属性缺失"],
        )
        rows = item.to_rows()
        assert len(rows) == 2
        assert rows[0]["warnings"] == ["数据组重复", "属性缺失"]
        assert rows[1]["warnings"] == []

    def test_to_rows_no_warnings(self):
        item = self._make_item(movements=[self._make_movement()])
        row = item.to_rows()[0]
        assert row["warnings"] == []

    def test_to_rows_multiple_movements(self):
        item = self._make_item(movements=[
            DataMovement(1, "步骤1", "E", "数据组1", "属性1", "新增", False),
            DataMovement(2, "步骤2", "R", "数据组2", "属性2", "复用", False),
            DataMovement(3, "步骤3", "X", "数据组3", "属性3", "新增", False),
        ])
        rows = item.to_rows()
        assert len(rows) == 3
        assert rows[0]["sub_process"] == "步骤1"
        assert rows[1]["sub_process"] == "步骤2"
        assert rows[2]["sub_process"] == "步骤3"
        # process 在所有行中相同
        assert rows[0]["process"] == rows[1]["process"] == rows[2]["process"]
