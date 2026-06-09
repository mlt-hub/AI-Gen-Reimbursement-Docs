import os
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from ai_gen_reimbursement_docs.cosmic_confirmation import (
    apply_cosmic_confirmation_export_policy,
)
from ai_gen_reimbursement_docs.cosmic_models import CosmicItem, DataMovement
from ai_gen_reimbursement_docs.cosmic_validator import (
    CosmicIssue,
    CosmicValidationReport,
    CosmicValidationResult,
    cosmic_report_to_dict,
    global_cosmic_issue,
    validate_cosmic_items,
)
from ai_gen_reimbursement_docs.cosmic_writer import write_cosmic_xlsx
from ai_gen_reimbursement_docs.config_utils import (
    load_gen_cosmic_cfp_policy,
    load_gen_cosmic_governance_config,
)
from ai_gen_reimbursement_docs.excel_source import write_cfp_sum
from ai_gen_reimbursement_docs.pipeline import (
    _read_cfp_formula_from_meta_md,
    _resolve_templates,
)
from web_app.dependencies import require_auth, require_local
from web_app.services.artifact_service import find_log_dir
from web_app.services.run_history_service import append_done_file_to_history
from web_app.services.session_access import require_session_access
from web_app.services.session_manager import SessionManager


def _strip_suffix(name: str, suffix: str) -> str:
    return name[:-len(suffix)] if name.endswith(suffix) else name


def _section(text: str, heading: str) -> str:
    pattern = re.compile(rf"^## {re.escape(heading)}\s*$", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return ""
    rest = text[match.end():]
    next_heading = re.search(r"^## .*$", rest, re.MULTILINE)
    return rest[:next_heading.start()].strip() if next_heading else rest.strip()


def _title_module(text: str) -> str:
    first_line = text.splitlines()[0].strip() if text.splitlines() else ""
    for prefix in ("# FPA 预览调试:", "# FPA 预览响应:"):
        if first_line.startswith(prefix):
            return first_line[len(prefix):].strip()
    return ""


def _safe_json(text: str, default):
    if not text:
        return default
    try:
        return json.loads(text)
    except Exception:
        return default


def _read_text(path: Path | None) -> str:
    if path and path.exists() and path.is_file():
        return path.read_text(encoding="utf-8")
    return ""


def _cosmic_confirmation_path(session_manager: SessionManager, session_id: str) -> Path:
    state = session_manager.get(session_id)
    root = state.work_dir if state else None
    if root is None:
        raise HTTPException(404, "未知会话")
    root.mkdir(parents=True, exist_ok=True)
    return root / "cosmic-confirmation.json"


def _session_output_dir(session_manager: SessionManager, session_id: str) -> Path | None:
    state = session_manager.get(session_id)
    if state is None:
        return None
    if state.output_dir is not None:
        return state.output_dir
    if state.work_dir is not None:
        return state.work_dir / "output"
    return None


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _cosmic_draft_json_path(session_manager: SessionManager, session_id: str) -> Path | None:
    state = session_manager.get(session_id)
    if state is None:
        return None

    output_dir = _session_output_dir(session_manager, session_id)
    roots = [
        root
        for root in (state.output_dir, output_dir)
        if root is not None and root.exists()
    ]
    standard_name = "3.3.gen-cosmic-AI填充-COSMIC.json"
    cosmic_step = state.progress_steps.get("cosmic", {})
    for artifact in cosmic_step.get("artifacts", []):
        if not isinstance(artifact, dict):
            continue
        label = str(artifact.get("label") or "")
        name = str(artifact.get("name") or "")
        if label != "COSMIC JSON 草稿" and name != standard_name:
            continue
        candidate = Path(str(artifact.get("path") or ""))
        if candidate.name != standard_name or not candidate.exists() or not candidate.is_file():
            continue
        if any(_is_under(candidate, root) for root in roots):
            return candidate

    if output_dir is None or not output_dir.exists():
        return None
    matches = sorted(path for path in output_dir.rglob(standard_name) if path.is_file())
    return matches[0] if matches else None


def _cosmic_template_path(session_manager: SessionManager, session_id: str) -> Path | None:
    state = session_manager.get(session_id)
    if state is None:
        return None
    custom_roots = [
        root / "custom_templates"
        for root in (state.output_dir, state.work_dir)
        if root is not None
    ]
    for root in custom_roots:
        candidate = root / "项目功能点拆分表-输出模板.xlsx"
        if candidate.exists() and candidate.is_file():
            return candidate
    default = _resolve_templates("", None).get("cosmic", "")
    return Path(default) if default and Path(default).exists() else None


def _cosmic_md_dir_from_draft(path: Path) -> Path:
    return path.parent


def _cosmic_doc_dir_from_draft(path: Path) -> Path:
    return _cosmic_md_dir_from_draft(path).parent / "cosmic文档"


def _cosmic_meta_md_path(md_dir: Path) -> Path:
    filled = md_dir / "0.4.gen-basedata-AI填充-录入文档元数据.md"
    if filled.exists():
        return filled
    return md_dir / "0.2.gen-basedata-录入文档元数据-模板.md"


def _issue_from_dict(data: dict) -> CosmicIssue:
    return CosmicIssue(
        severity=str(data.get("severity") or "info"),
        code=str(data.get("code") or ""),
        message=str(data.get("message") or ""),
        field=str(data.get("field") or ""),
        module_path=str(data.get("module_path") or ""),
        process=str(data.get("process") or ""),
        movement_order=data.get("movement_order") if isinstance(data.get("movement_order"), int) else None,
        scope=str(data.get("scope") or "item"),
        details=data.get("details") if isinstance(data.get("details"), dict) else {},
    )


def _review_actions(payload: dict) -> list[dict]:
    actions = payload.get("review_actions")
    if not isinstance(actions, list):
        return []
    return [action for action in actions if isinstance(action, dict)]


def _function_user_role_map(payload: dict) -> dict[str, str]:
    values: dict[str, str] = {}
    governance = load_gen_cosmic_governance_config()
    configured = governance.get("function_user_role_map")
    if isinstance(configured, dict):
        for key, value in configured.items():
            module_name = str(key or "").strip()
            user_value = str(value or "").strip()
            if module_name and user_value:
                values[module_name] = user_value
    role_map = payload.get("function_user_role_map")
    if isinstance(role_map, dict):
        for key, value in role_map.items():
            module_name = str(key or "").strip()
            user_value = str(value or "").strip()
            if module_name and user_value:
                values[module_name] = user_value
    return values


def _role_mapped_user(item: dict, role_map: dict[str, str]) -> str:
    for key in ("module_l3", "module_l2", "module_l1"):
        module_name = str(item.get(key) or "").strip()
        if module_name and module_name in role_map:
            return role_map[module_name]
    return ""


def _movement_action_matches(raw_movement: dict, action: dict, movement_index: int) -> bool:
    if not isinstance(raw_movement, dict):
        return False
    if isinstance(action.get("movement_index"), int):
        return action["movement_index"] == movement_index
    if isinstance(action.get("movement_order"), int):
        return int(raw_movement.get("order") or movement_index + 1) == action["movement_order"]
    return False


def _apply_review_actions(payload: dict) -> dict:
    data = json.loads(json.dumps(payload, ensure_ascii=False))
    items = data.get("items")
    if not isinstance(items, list):
        return data
    role_map = _function_user_role_map(data)
    for action in _review_actions(data):
        action_type = str(action.get("action") or "")
        item_index = action.get("item_index")
        if not isinstance(item_index, int) or item_index < 0 or item_index >= len(items):
            continue
        item = items[item_index]
        if not isinstance(item, dict):
            continue
        if action_type == "apply_function_user":
            suggested_user = str(
                action.get("suggested_user")
                or action.get("value")
                or _role_mapped_user(item, role_map)
                or ""
            ).strip()
            if suggested_user:
                item["user"] = suggested_user
            continue
        if action_type == "exclude_process":
            item["excluded_from_cfp"] = True
            item["review_action"] = action_type
            movements = item.get("movements")
            if isinstance(movements, list):
                for raw_movement in movements:
                    if isinstance(raw_movement, dict):
                        raw_movement["excluded_from_cfp"] = True
                        raw_movement["review_action"] = action_type
            continue
        if action_type not in {"exclude_movement", "merge_movement"}:
            continue
        movements = item.get("movements")
        if not isinstance(movements, list):
            continue
        for movement_index, raw_movement in enumerate(movements):
            if not _movement_action_matches(raw_movement, action, movement_index):
                continue
            if isinstance(raw_movement, dict):
                raw_movement["excluded_from_cfp"] = True
                raw_movement["review_action"] = action_type
                if action_type == "merge_movement":
                    raw_movement["merged_into_order"] = action.get("merged_into_order") or max(1, int(raw_movement.get("order") or 1) - 1)
            break
    return data


def _apply_auto_review_actions(payload: dict) -> dict:
    governance = load_gen_cosmic_governance_config()
    if governance.get("auto_apply_review_actions") is not True:
        return payload
    allowed_codes = {
        str(code).strip()
        for code in governance.get("auto_apply_issue_codes", [])
        if str(code or "").strip()
    }
    if not allowed_codes:
        return payload
    review_items = payload.get("review_items")
    if not isinstance(review_items, list):
        return payload
    actions = payload.setdefault("review_actions", [])
    if not isinstance(actions, list):
        actions = []
        payload["review_actions"] = actions
    existing_keys = {_review_action_key(action) for action in actions if isinstance(action, dict)}
    for review_item in review_items:
        if not isinstance(review_item, dict):
            continue
        code = str(review_item.get("code") or "")
        if code not in allowed_codes:
            continue
        details = review_item.get("details")
        if not isinstance(details, dict):
            continue
        suggested_actions = details.get("suggested_actions")
        if not isinstance(suggested_actions, list) or not suggested_actions:
            continue
        suggested = next((item for item in suggested_actions if isinstance(item, dict)), None)
        if not suggested:
            continue
        action = {
            **suggested,
            "item_index": review_item.get("item_index"),
            "movement_order": review_item.get("movement_order", suggested.get("movement_order")),
            "review_id": review_item.get("review_id"),
            "source": "auto_governance",
            "reason": suggested.get("reason") or details.get("basis_description") or "自动应用 COSMIC 治理建议",
        }
        key = _review_action_key(action)
        if key not in existing_keys:
            actions.append(action)
            existing_keys.add(key)
    return payload


def _cosmic_items_from_payload(payload: dict, *, include_excluded: bool) -> list[CosmicItem]:
    items = payload.get("items")
    if not isinstance(items, list):
        raise HTTPException(400, "COSMIC JSON 缺少 items")

    cosmic_items: list[CosmicItem] = []
    for raw_item in items:
        if not isinstance(raw_item, dict):
            continue
        if not include_excluded and raw_item.get("excluded_from_cfp") is True:
            continue
        movements: list[DataMovement] = []
        for movement_index, raw_movement in enumerate(raw_item.get("movements") or []):
            if not isinstance(raw_movement, dict):
                continue
            if not include_excluded and raw_movement.get("excluded_from_cfp") is True:
                continue
            movements.append(DataMovement(
                order=int(raw_movement.get("order") or movement_index + 1),
                sub_process=str(raw_movement.get("sub_process") or ""),
                move_type=str(raw_movement.get("move_type") or ""),
                data_group=str(raw_movement.get("data_group") or ""),
                data_attrs=str(raw_movement.get("data_attrs") or ""),
                reuse=str(raw_movement.get("reuse") or "新增"),
            ))
        cosmic_items.append(CosmicItem(
            project=str(raw_item.get("project") or payload.get("project") or ""),
            module_l1=str(raw_item.get("module_l1") or ""),
            module_l2=str(raw_item.get("module_l2") or ""),
            module_l3=str(raw_item.get("module_l3") or ""),
            user=str(raw_item.get("user") or ""),
            trigger=str(raw_item.get("trigger") or ""),
            process=str(raw_item.get("process") or ""),
            movements=movements,
        ))
    return cosmic_items


def _confirmation_by_review_id(payload: dict) -> dict[str, dict]:
    values: dict[str, dict] = {}
    review_items = payload.get("review_items")
    if not isinstance(review_items, list):
        return values
    for item in review_items:
        if not isinstance(item, dict):
            continue
        review_id = str(item.get("review_id") or "")
        confirmation = item.get("confirmation")
        if review_id and isinstance(confirmation, dict):
            values[review_id] = confirmation
    return values


def _merge_review_confirmations(payload: dict, confirmations: dict[str, dict]) -> None:
    review_items = payload.get("review_items")
    if not isinstance(review_items, list):
        return
    for item in review_items:
        if not isinstance(item, dict):
            continue
        confirmation = confirmations.get(str(item.get("review_id") or ""))
        if confirmation:
            item["confirmation"] = {
                **(item.get("confirmation") if isinstance(item.get("confirmation"), dict) else {}),
                **confirmation,
            }


def _restore_raw_review_fields(payload: dict, source: dict) -> None:
    for key in (
        "review_actions",
        "review_audit",
        "review_audit_hash_chain",
        "cfp_policy",
        "function_user_role_map",
    ):
        value = source.get(key)
        if value is not None:
            payload[key] = value


def _audit_hash(record: dict, previous_hash: str = "") -> str:
    material = {
        key: value
        for key, value in record.items()
        if key not in {"audit_hash", "previous_audit_hash"}
    }
    material["previous_audit_hash"] = previous_hash
    text = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _verify_audit_hash_chain(records: list[dict]) -> dict[str, object]:
    previous_hash = ""
    checked = 0
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            continue
        audit_hash = str(record.get("audit_hash") or "")
        if not audit_hash:
            continue
        checked += 1
        expected_previous = str(record.get("previous_audit_hash") or "")
        if expected_previous != previous_hash:
            return {
                "algorithm": "sha256-json-v1",
                "valid": False,
                "checked_record_count": checked,
                "failed_index": index,
                "reason": "previous_audit_hash 不匹配",
            }
        expected_hash = _audit_hash(record, previous_hash)
        if audit_hash != expected_hash:
            return {
                "algorithm": "sha256-json-v1",
                "valid": False,
                "checked_record_count": checked,
                "failed_index": index,
                "reason": "audit_hash 不匹配",
            }
        previous_hash = audit_hash
    return {
        "algorithm": "sha256-json-v1",
        "valid": True,
        "checked_record_count": checked,
        "failed_index": None,
        "reason": "",
    }


def _stamp_review_audit(payload: dict, *, reviewer: str = "") -> None:
    actions = payload.get("review_actions")
    if not isinstance(actions, list):
        actions = []
    audit = payload.get("review_audit")
    if not isinstance(audit, list):
        audit = []
    keyed: dict[tuple, dict] = {}
    for raw_record in audit:
        if isinstance(raw_record, dict):
            keyed[_review_action_key(raw_record)] = raw_record
    for raw_action in actions:
        if not isinstance(raw_action, dict):
            continue
        record = dict(raw_action)
        if reviewer and not record.get("confirmed_by"):
            record["confirmed_by"] = reviewer
        if reviewer and not record.get("applied_by"):
            record["applied_by"] = reviewer
        if not record.get("applied_at"):
            record["applied_at"] = record.get("created_at") or datetime.now(timezone.utc).isoformat()
        keyed[_review_action_key(record)] = record
    records = list(keyed.values())
    governance = load_gen_cosmic_governance_config()
    if governance.get("audit_hash_chain") is not False:
        payload["review_audit_hash_chain"] = _verify_audit_hash_chain(records)
        previous_hash = ""
        for record in records:
            record["previous_audit_hash"] = previous_hash
            record["audit_hash"] = _audit_hash(record, previous_hash)
            previous_hash = str(record["audit_hash"])
        payload["review_audit_hash_chain"].update({
            "record_count": len(records),
            "final_audit_hash": previous_hash,
        })
    payload["review_audit"] = records


def _review_action_key(action: dict) -> tuple:
    return (
        str(action.get("action") or ""),
        action.get("item_index"),
        action.get("movement_order"),
        str(action.get("review_id") or ""),
    )


def _revalidate_cosmic_payload(payload: dict, *, cfp_formula: str = "", reviewer: str = "") -> dict:
    if not isinstance(payload.get("items"), list):
        return apply_cosmic_confirmation_export_policy(payload)
    governance = load_gen_cosmic_governance_config()
    payload = _apply_auto_review_actions(payload)
    acted = _apply_review_actions(payload)
    _stamp_review_audit(acted, reviewer=reviewer)
    confirmations = _confirmation_by_review_id(acted)
    effective_cfp_policy = _cfp_policy_from_payload(acted)
    formula = cfp_formula or _cfp_formula_from_payload(acted)
    report = validate_cosmic_items(
        _cosmic_items_from_payload(acted, include_excluded=False),
        project_name=str(acted.get("project") or ""),
        cfp_formula=formula,
        global_issues=_cfp_policy_formula_issues(formula, effective_cfp_policy),
        governance_config=governance,
    )
    data = cosmic_report_to_dict(report)
    raw_items = acted.get("items")
    report_items = data.get("items")
    if isinstance(raw_items, list) and isinstance(report_items, list):
        for index, raw_item in enumerate(raw_items):
            if not isinstance(raw_item, dict) or index >= len(report_items):
                continue
            report_item = report_items[index]
            if not isinstance(report_item, dict):
                continue
            for key in ("status", "issues", "basis"):
                if key in report_item:
                    raw_item[key] = report_item[key]
        data["items"] = raw_items
    else:
        data["items"] = report_items if isinstance(report_items, list) else []
    _merge_review_confirmations(data, confirmations)
    data["cfp_policy_effective"] = effective_cfp_policy
    data["governance_effective"] = _cosmic_governance_effective(governance)
    _restore_raw_review_fields(data, acted)
    return apply_cosmic_confirmation_export_policy(data)


def _cosmic_report_from_payload(payload: dict) -> CosmicValidationReport:
    acted = _apply_review_actions(payload)
    items = _cosmic_items_from_payload(acted, include_excluded=False)

    review_items = payload.get("review_items")
    if not isinstance(review_items, list):
        review_items = []
    issues_by_item: dict[int, list[CosmicIssue]] = {}
    global_issues: list[CosmicIssue] = []
    for raw_issue in review_items:
        if not isinstance(raw_issue, dict):
            continue
        issue = _issue_from_dict(raw_issue)
        item_index = raw_issue.get("item_index")
        if isinstance(item_index, int):
            issues_by_item.setdefault(item_index, []).append(issue)
        else:
            global_issues.append(issue)

    results: list[CosmicValidationResult] = []
    raw_items = acted.get("items")
    for index, item in enumerate(items):
        status = "passed"
        if isinstance(raw_items, list) and index < len(raw_items) and isinstance(raw_items[index], dict):
            status = str(raw_items[index].get("status") or status)
        results.append(CosmicValidationResult(
            item=item,
            status=status,
            issues=issues_by_item.get(index, []),
            basis={},
        ))

    return CosmicValidationReport(
        project=str(payload.get("project") or ""),
        status=str(payload.get("status") or ""),
        results=results,
        summary=payload.get("summary") if isinstance(payload.get("summary"), dict) else {},
        issue_codes=payload.get("issue_codes") if isinstance(payload.get("issue_codes"), dict) else {},
        cfp_basis=payload.get("cfp_basis") if isinstance(payload.get("cfp_basis"), dict) else {},
        issues=global_issues,
    )


def _cfp_formula_from_payload(payload: dict) -> str:
    cfp_basis = payload.get("cfp_basis")
    if not isinstance(cfp_basis, dict):
        return ""
    formula = cfp_basis.get("formula")
    return str(formula or "")


def _cfp_policy_from_payload(payload: dict) -> dict[str, float]:
    policy = {
        "新增": 1.0,
        "修改": 1.0,
        "复用": 1.0 / 3.0,
        "利旧": 0.0,
        "优化未改": 0.0,
    }
    for raw_policy in (load_gen_cosmic_cfp_policy(), payload.get("cfp_policy")):
        if not isinstance(raw_policy, dict):
            continue
        for key, value in raw_policy.items():
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            if number >= 0:
                policy[str(key)] = number
    return policy


def _cfp_policy_formula_issues(cfp_formula: str, policy: dict[str, float]) -> list[CosmicIssue]:
    governance = load_gen_cosmic_governance_config()
    if governance.get("cfp_formula_consistency_check") is not True:
        return []
    formula = str(cfp_formula or "")
    if not formula:
        return []
    missing_terms: list[str] = []
    mismatched_terms: list[str] = []
    parsed_formula_policy = _parse_cfp_policy_from_formula(formula, policy.keys())
    for reuse, value in policy.items():
        if reuse not in formula:
            continue
        parsed_value = parsed_formula_policy.get(reuse)
        if parsed_value is not None:
            if abs(parsed_value - value) > 0.000001:
                mismatched_terms.append(
                    f"{reuse}=policy:{_policy_value_text(value)},formula:{_policy_value_text(parsed_value)}"
                )
            continue
        value_text = _policy_value_text(value)
        if value_text and value_text not in formula:
            missing_terms.append(f"{reuse}={value_text}")
    if not missing_terms and not mismatched_terms:
        return []
    issue = global_cosmic_issue(
        "warning",
        "CFP_POLICY_FORMULA_MISMATCH",
        "确认后 CFP policy 与 Excel 公式疑似不一致，需确认模板公式和 Python 汇总口径",
        "cfp_policy_effective",
    )
    issue.details = {
        "policy": policy,
        "formula": formula,
        "parsed_formula_policy": parsed_formula_policy,
        "missing_policy_terms": missing_terms,
        "mismatched_policy_terms": mismatched_terms,
        "basis_description": "开启一致性校验后，公式中出现的复用度应能对应有效 CFP policy 数值",
    }
    return [issue]


def _parse_cfp_policy_from_formula(formula: str, reuse_names) -> dict[str, float]:
    parsed: dict[str, float] = {}
    for reuse in reuse_names:
        name = str(reuse or "").strip()
        if not name:
            continue
        pattern = re.compile(
            rf"{re.escape(name)}[\s\S]{{0,80}}?([-+]?\d+(?:\.\d+)?\s*/\s*[-+]?\d+(?:\.\d+)?|[-+]?\d+(?:\.\d+)?)"
        )
        match = pattern.search(formula)
        if not match:
            continue
        value = _parse_formula_number(match.group(1))
        if value is not None:
            parsed[name] = value
    return parsed


def _parse_formula_number(text: str) -> float | None:
    value = str(text or "").replace(" ", "")
    if not value:
        return None
    if "/" in value:
        left, right = value.split("/", 1)
        try:
            denominator = float(right)
            if denominator == 0:
                return None
            return float(left) / denominator
        except ValueError:
            return None
    try:
        return float(value)
    except ValueError:
        return None


def _policy_value_text(value: float) -> str:
    text = f"{float(value):.12g}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _cosmic_governance_effective(governance: dict[str, object]) -> dict[str, object]:
    rule_matrix = governance.get("rule_matrix")
    return {
        "auto_apply_review_actions": bool(governance.get("auto_apply_review_actions")),
        "auto_apply_issue_codes": list(governance.get("auto_apply_issue_codes", [])),
        "require_unique_function_user": bool(governance.get("require_unique_function_user")),
        "cfp_formula_consistency_check": bool(governance.get("cfp_formula_consistency_check")),
        "audit_hash_chain": governance.get("audit_hash_chain") is not False,
        "rule_matrix_codes": [
            str(rule.get("code"))
            for rule in rule_matrix
            if isinstance(rule, dict) and str(rule.get("code") or "")
        ] if isinstance(rule_matrix, list) else [],
        "function_user_role_map_keys": sorted(
            str(key)
            for key in (governance.get("function_user_role_map") or {})
            if str(key or "")
        ) if isinstance(governance.get("function_user_role_map"), dict) else [],
    }


def _calculate_review_cfp_total(payload: dict) -> float:
    policy = _cfp_policy_from_payload(payload)
    total = 0.0
    for item in _cosmic_items_from_payload(_apply_review_actions(payload), include_excluded=False):
        for movement in item.movements:
            total += policy.get(movement.reuse, 1.0)
    return round(total, 6)


def _record_function_points(record: dict) -> list[str]:
    values: list[str] = []
    for key in ("final_rows", "parsed_rows"):
        rows = record.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or row.get("function_point") or "").strip()
            if name and name not in values:
                values.append(name)
    return values


def _build_structured_fpa_debug_records(log_dir: Path) -> list[dict]:
    prompts_dir = log_dir / "ai_prompts"
    responses_dir = log_dir / "ai_responses"
    records_dir = log_dir / "debug_records"
    records: list[dict] = []
    seen_ids: set[str] = set()

    if records_dir.is_dir():
        for path in sorted(records_dir.glob("*.json")):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(record, dict):
                continue
            record_id = str(record.get("id") or path.stem)
            prompt_file = str(record.get("prompt_file") or f"{record_id}_prompt.txt")
            response_file = str(record.get("response_file") or f"{record_id}_response.txt")
            prompt_content = _read_text(prompts_dir / prompt_file)
            response_content = _read_text(responses_dir / response_file)
            item = {
                "id": record_id,
                "source": str(record.get("source") or "fpa_preview"),
                "module": str(record.get("module") or _title_module(prompt_content) or _title_module(response_content)),
                "model": str(record.get("model") or ""),
                "reason": str(record.get("reason") or ""),
                "ai_called": bool(record.get("ai_called")),
                "prompt_file": prompt_file,
                "response_file": response_file,
                "prompt": prompt_content,
                "response": response_content,
                "parsed_rows": record.get("parsed_rows") if isinstance(record.get("parsed_rows"), list) else [],
                "final_rows": record.get("final_rows") if isinstance(record.get("final_rows"), list) else [],
                "quality_review": record.get("quality_review") if isinstance(record.get("quality_review"), dict) else {},
                "error": str(record.get("error") or ""),
            }
            item["function_points"] = _record_function_points(item)
            records.append(item)
            seen_ids.add(record_id)

    if prompts_dir.is_dir():
        for prompt_path in sorted(prompts_dir.glob("*_prompt.txt")):
            record_id = _strip_suffix(prompt_path.name, "_prompt.txt")
            if record_id in seen_ids:
                continue
            response_path = responses_dir / f"{record_id}_response.txt"
            prompt_content = _read_text(prompt_path)
            response_content = _read_text(response_path)
            item = {
                "id": record_id,
                "source": "fpa_preview" if record_id.startswith("fpa_preview_") else "ai_log",
                "module": _title_module(prompt_content) or _title_module(response_content),
                "model": "",
                "reason": "",
                "ai_called": bool(response_content),
                "prompt_file": prompt_path.name,
                "response_file": response_path.name if response_path.exists() else "",
                "prompt": prompt_content,
                "response": response_content,
                "parsed_rows": _safe_json(_section(response_content, "Parsed Rows"), []),
                "final_rows": [],
                "quality_review": _safe_json(_section(response_content, "Quality Review"), {}),
                "error": "",
            }
            item["function_points"] = _record_function_points(item)
            records.append(item)

    return records


def create_router(session_manager: SessionManager, *, base_dir: Path | None = None) -> APIRouter:
    router = APIRouter()

    @router.get("/api/download/{session_id}")
    async def download(
        session_id: str,
        request: Request,
        user: str = Depends(require_auth),
    ):
        """远程服务模式：下载交付物 ZIP。"""
        require_session_access(session_manager, session_id, request, user)
        state = session_manager.get(session_id)
        zip_path = state.zip_path if state else None
        if zip_path is None:
            if state is not None:
                raise HTTPException(409, "任务仍在运行，交付物尚未生成")
            raise HTTPException(404, "交付物不存在或会话已过期")
        if not zip_path.exists():
            raise HTTPException(404, "交付物文件已被清理")

        return FileResponse(
            zip_path,
            filename=f"交付物_{datetime.now():%Y%m%d_%H%M%S}.zip",
            media_type="application/zip",
        )

    @router.get("/api/open-folder")
    async def open_folder(session: str, _local: None = Depends(require_local)):
        """本机模式：在资源管理器中打开交付物目录。"""
        state = session_manager.get(session)
        out_dir = state.output_dir if state else None
        if out_dir is None:
            raise HTTPException(404, "未知会话")
        if not out_dir.exists():
            raise HTTPException(404, "交付物目录不存在")
        os.startfile(str(out_dir))
        return {"ok": True}

    @router.get("/api/ai-log/{session_id}")
    async def get_ai_log(
        session_id: str,
        request: Request,
        user: str = Depends(require_auth),
    ):
        """返回 AI 对话日志内容。"""
        require_session_access(session_manager, session_id, request, user)
        log_dir = find_log_dir(session_manager, session_id)
        if log_dir is None:
            raise HTTPException(404, "未找到日志目录")

        combined = log_dir / "ai_对话日志.md"
        if not combined.exists():
            raise HTTPException(404, "AI 对话日志尚未生成")

        content = combined.read_text(encoding="utf-8")
        return {"content": content, "filename": combined.name}

    @router.get("/api/ai-interactions/{session_id}")
    async def list_ai_interactions(
        session_id: str,
        request: Request,
        user: str = Depends(require_auth),
    ):
        """列出 AI prompts 和 responses 文件清单及内容。"""
        require_session_access(session_manager, session_id, request, user)
        log_dir = find_log_dir(session_manager, session_id)
        if log_dir is None:
            raise HTTPException(404, "未找到日志目录")

        prompts_dir = log_dir / "ai_prompts"
        responses_dir = log_dir / "ai_responses"

        files: list[dict] = []

        if prompts_dir.is_dir():
            for fname in sorted(os.listdir(prompts_dir)):
                if fname.endswith(".txt"):
                    path = prompts_dir / fname
                    files.append({
                        "name": fname,
                        "type": "prompt",
                        "content": path.read_text(encoding="utf-8"),
                    })

        if responses_dir.is_dir():
            for fname in sorted(os.listdir(responses_dir)):
                if fname.endswith(".txt"):
                    path = responses_dir / fname
                    files.append({
                        "name": fname,
                        "type": "response",
                        "content": path.read_text(encoding="utf-8"),
                    })

        return {"interactions": files, "count": len(files)}

    @router.get("/api/sessions/{session_id}/fpa/debug-records")
    async def list_fpa_debug_records(
        session_id: str,
        request: Request,
        user: str = Depends(require_auth),
    ):
        """返回结构化 FPA AI 调试记录。"""
        require_session_access(session_manager, session_id, request, user)
        log_dir = find_log_dir(session_manager, session_id)
        if log_dir is None:
            raise HTTPException(404, "未找到日志目录")
        records = _build_structured_fpa_debug_records(log_dir)
        return {
            "session_id": session_id,
            "records": records,
            "count": len(records),
            "filters": {
                "models": sorted({record["model"] for record in records if record.get("model")}),
                "modules": sorted({record["module"] for record in records if record.get("module")}),
                "function_points": sorted({
                    name
                    for record in records
                    for name in record.get("function_points", [])
                    if name
                }),
            },
        }

    @router.get("/api/sessions/{session_id}/cosmic/confirmation")
    async def get_cosmic_confirmation(
        session_id: str,
        request: Request,
        user: str = Depends(require_auth),
    ):
        """读取 COSMIC 预览人工确认 JSON。"""
        require_session_access(session_manager, session_id, request, user)
        path = _cosmic_confirmation_path(session_manager, session_id)
        if not path.exists():
            raise HTTPException(404, "COSMIC 确认 JSON 尚未保存")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise HTTPException(500, "COSMIC 确认 JSON 损坏") from exc
        payload = apply_cosmic_confirmation_export_policy(payload)
        return {
            "session_id": session_id,
            "filename": path.name,
            "payload": payload,
        }

    @router.get("/api/sessions/{session_id}/cosmic/draft")
    async def get_cosmic_draft(
        session_id: str,
        request: Request,
        user: str = Depends(require_auth),
    ):
        """读取生成任务产出的 COSMIC JSON 草稿。"""
        require_session_access(session_manager, session_id, request, user)
        path = _cosmic_draft_json_path(session_manager, session_id)
        if path is None:
            raise HTTPException(404, "COSMIC JSON 草稿尚未生成")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise HTTPException(500, "COSMIC JSON 草稿损坏") from exc
        return {
            "session_id": session_id,
            "filename": path.name,
            "payload": payload,
        }

    @router.put("/api/sessions/{session_id}/cosmic/confirmation")
    async def save_cosmic_confirmation(
        session_id: str,
        payload: dict,
        request: Request,
        user: str = Depends(require_auth),
    ):
        """保存 COSMIC 预览人工确认 JSON。"""
        require_session_access(session_manager, session_id, request, user)
        if not isinstance(payload, dict):
            raise HTTPException(400, "COSMIC 确认 JSON 必须是对象")
        draft_path = _cosmic_draft_json_path(session_manager, session_id)
        cfp_formula = ""
        if draft_path is not None:
            cfp_formula = _read_cfp_formula_from_meta_md(str(_cosmic_meta_md_path(_cosmic_md_dir_from_draft(draft_path))))
        if not cfp_formula:
            from ai_gen_reimbursement_docs.config_utils import load_cfp_formula
            cfp_formula = load_cfp_formula()
        payload = _revalidate_cosmic_payload(payload, cfp_formula=cfp_formula, reviewer=user)
        path = _cosmic_confirmation_path(session_manager, session_id)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return {
            "ok": True,
            "session_id": session_id,
            "filename": path.name,
            "payload": payload,
        }

    @router.post("/api/sessions/{session_id}/cosmic/export-confirmed")
    async def export_confirmed_cosmic_excel(
        session_id: str,
        request: Request,
        user: str = Depends(require_auth),
    ):
        """按已确认 COSMIC JSON 再导出 Excel，不覆盖原生成产物。"""
        require_session_access(session_manager, session_id, request, user)
        draft_path = _cosmic_draft_json_path(session_manager, session_id)
        if draft_path is None:
            raise HTTPException(404, "COSMIC JSON 草稿尚未生成")

        confirmation_path = _cosmic_confirmation_path(session_manager, session_id)
        source_path = confirmation_path if confirmation_path.exists() else draft_path
        try:
            payload = json.loads(source_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise HTTPException(500, "COSMIC 确认 JSON 损坏") from exc
        md_dir = _cosmic_md_dir_from_draft(draft_path)
        cfp_formula = _read_cfp_formula_from_meta_md(str(_cosmic_meta_md_path(md_dir)))
        if not cfp_formula:
            from ai_gen_reimbursement_docs.config_utils import load_cfp_formula
            cfp_formula = load_cfp_formula()
        payload = apply_cosmic_confirmation_export_policy(_apply_review_actions(payload))
        formal_policy = payload.get("export_policy", {}).get("formal_excel", {})
        formal_status = str(formal_policy.get("status") or "")
        if formal_status not in {"allowed", "allowed_after_confirmation"}:
            raise HTTPException(409, str(formal_policy.get("reason") or "COSMIC 确认状态不允许导出正式 Excel"))

        template_path = _cosmic_template_path(session_manager, session_id)
        if template_path is None:
            raise HTTPException(404, "未找到 COSMIC Excel 输出模板")
        report = _cosmic_report_from_payload(payload)
        doc_dir = _cosmic_doc_dir_from_draft(draft_path)
        doc_dir.mkdir(parents=True, exist_ok=True)
        output_path = doc_dir / "项目功能点拆分表-确认后.xlsx"
        saved_path = Path(write_cosmic_xlsx(
            str(template_path),
            str(output_path),
            report,
            cfp_formula=cfp_formula,
        ))
        cfp_total = _calculate_review_cfp_total(payload)
        write_cfp_sum(str(md_dir), cfp_total)
        cfp_summary_path = md_dir / "3.5.gen-cosmic-CFP-总和.md"
        file_info = {
            "label": "项目功能点拆分表（确认后）",
            "path": str(saved_path),
            "size_kb": round(saved_path.stat().st_size / 1024),
            "is_temp": "_TEMP" in saved_path.name,
        }
        cfp_file_info = {
            "label": "COSMIC CFP 总和（确认后）",
            "path": str(cfp_summary_path),
            "size_kb": round(cfp_summary_path.stat().st_size / 1024),
            "is_temp": False,
        }
        state = session_manager.get(session_id)
        if state is not None:
            done_files = list(state.done_files)
            for item in (file_info, cfp_file_info):
                if not any(existing.get("path") == item["path"] for existing in done_files):
                    done_files.append(item)
            session_manager.set_done_files(session_id, done_files)
        if state is not None and state.mode == "remote" and state.zip_path is not None:
            output_dir = _session_output_dir(session_manager, session_id)
            if output_dir is not None and output_dir.exists():
                shutil.make_archive(str(state.zip_path.with_suffix("")), "zip", str(output_dir))
        if state is not None and base_dir is not None:
            for item in (file_info, cfp_file_info):
                append_done_file_to_history(
                    base_dir=base_dir,
                    session_id=session_id,
                    mode=state.mode,
                    done_file=item,
                    zip_path=str(state.zip_path) if state.zip_path else "",
                )
        return {
            "ok": True,
            "session_id": session_id,
            "filename": saved_path.name,
            "path": str(saved_path),
            "file": file_info,
            "files": [file_info, cfp_file_info],
            "cfp_total": cfp_total,
            "cfp_summary_file": cfp_file_info,
            "export_policy": payload.get("export_policy", {}),
        }

    return router
