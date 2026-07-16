from __future__ import annotations

import json
import sys
from pathlib import Path


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
if str(EXPERIMENT_ROOT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_ROOT))

from src.advisory import parse_advisory_response


def test_parse_valid_new_schema() -> None:
    payload = {
        "diagnosis_id": "d1",
        "round": 1,
        "advisor_name": "judge",
        "score": 0.7,
        "diagnosed_errors": [
            {
                "type": "missing_constraint",
                "severity": "high",
                "description": "capacity missing",
                "evidence": "no capacity row",
                "suggested_fix": "add capacity constraint",
            }
        ],
        "repair_instructions": ["add capacity constraint"],
        "confidence": 0.8,
        "reject_reasons": ["capacity missing"],
        "should_execute": False,
    }

    diagnosis = parse_advisory_response(json.dumps(payload), round_index=1, advisor_name="judge")

    assert diagnosis.status == "ok"
    assert diagnosis.should_execute is False
    assert diagnosis.diagnosed_errors[0].type == "missing_constraint"
    assert diagnosis.repair_instructions == ["add capacity constraint"]


def test_parse_old_schema() -> None:
    payload = {
        "score": 0.4,
        "should_execute": False,
        "missing_constraints": ["flow balance"],
        "wrong_objective": True,
        "variable_issues": ["x domain"],
        "feedback": "Fix flow and objective.",
    }

    diagnosis = parse_advisory_response(json.dumps(payload))
    types = [item.type for item in diagnosis.diagnosed_errors]

    assert "missing_constraint" in types
    assert "wrong_objective" in types
    assert "variable_issue" in types
    assert "Fix flow and objective." in diagnosis.repair_instructions


def test_parse_fenced_json() -> None:
    diagnosis = parse_advisory_response(
        "```json\n{\"score\": 0.9, \"should_execute\": true}\n```",
    )

    assert diagnosis.status == "ok"
    assert diagnosis.score == 0.9
    assert diagnosis.should_execute is True


def test_parse_recovers_overescaped_json_fragments() -> None:
    raw = (
        '{"score":0.62,"should_execute":true,"confidence":0.62,'
        '"diagnosed_errors":[{"type":"missing_constraint","severity":"high",'
        '"description":"premium sales balance missing","suggested_fix":"add sold_premium variables"},'
        '{\\"type\\":\\"wrong_objective\\",\\"severity\\":\\"medium\\",'
        '\\"description\\":\\"premium revenue is counted on production instead of sales\\",'
        '\\"suggested_fix\\":\\"use sold_premium variables in the objective\\"}],'
        '\\"repair_instructions\\":[\\"add sold_premium variables\\",'
        '\\"use sold_premium in objective\\"],\\"reject_reasons\\":[]}'
    )

    diagnosis = parse_advisory_response(raw)
    types = [item.type for item in diagnosis.diagnosed_errors]

    assert diagnosis.parse_success is True
    assert diagnosis.status == "ok"
    assert types == ["missing_constraint", "wrong_objective"]
    assert "use sold_premium in objective" in diagnosis.repair_instructions


def test_parse_recovers_overescaped_long_instruction_fragment() -> None:
    raw = (
        '{"score":0.0,"should_execute":true,"confidence":0.74,'
        '"diagnosed_errors":[{"type":"missing_constraint","severity":"high",'
        '"description":"depot arcs are missing","suggested_fix":"add depot-customer arcs"},'
        '{\\"type\\":\\"variable_issue\\",\\"severity\\":\\"high\\",'
        '\\"description\\":\\"x is indexed by center not vehicle\\",'
        '\\"suggested_fix\\":\\"index x by vehicle such as vehicles = [(\'A\',k), (\'B\',k)]\\"}],'
        '\\"repair_instructions\\":[\\"Reformulate as a multi-vehicle VRP with depot nodes and vehicle-indexed arcs.\\"],'
        '\\"reject_reasons\\":[]}'
    )

    diagnosis = parse_advisory_response(raw)

    assert diagnosis.parse_success is True
    assert [item.type for item in diagnosis.diagnosed_errors] == ["missing_constraint", "variable_issue"]
    assert diagnosis.repair_instructions == [
        "Reformulate as a multi-vehicle VRP with depot nodes and vehicle-indexed arcs."
    ]


def test_parse_recovers_missing_repair_instruction_array_closure() -> None:
    raw = (
        '{"score":0.0,"should_execute":true,"confidence":0.74,'
        '"diagnosed_errors":[{"type":"missing_constraint","severity":"high",'
        '"description":"depot arcs are missing","suggested_fix":"add depot-customer arcs"}],'
        '"repair_instructions":["Reformulate as a multi-vehicle VRP with depot nodes and vehicle-indexed arcs.",'
        '"reject_reasons":[]}'
    )

    diagnosis = parse_advisory_response(raw)

    assert diagnosis.parse_success is True
    assert diagnosis.diagnosed_errors[0].type == "missing_constraint"
    assert diagnosis.repair_instructions == [
        "Reformulate as a multi-vehicle VRP with depot nodes and vehicle-indexed arcs."
    ]
    assert diagnosis.reject_reasons == []


def test_parse_still_rejects_genuinely_invalid_json() -> None:
    diagnosis = parse_advisory_response('{"score":0.5,"diagnosed_errors":[not valid json]}')

    assert diagnosis.parse_success is False
    assert diagnosis.parse_failure_type == "invalid_json"
    assert diagnosis.should_execute is True


def test_parse_malformed_non_json_fallback() -> None:
    diagnosis = parse_advisory_response("not json at all", round_index=2)

    assert diagnosis.status == "invalid_json"
    assert diagnosis.should_execute is True
    assert diagnosis.confidence == 0.0
    assert diagnosis.diagnosed_errors[0].type == "parse_failed"
    assert diagnosis.parse_success is False
    assert diagnosis.parse_failure_type == "invalid_json"


def test_empty_response_is_distinct_parse_failure() -> None:
    diagnosis = parse_advisory_response("   ")

    assert diagnosis.status == "empty_response"
    assert diagnosis.should_execute is True
    assert diagnosis.empty_response is True
    assert diagnosis.parse_success is False
    assert diagnosis.parse_failure_type == "empty_response"
    assert diagnosis.diagnosed_errors[0].type == "empty_response"


def test_parse_missing_fields_defaults() -> None:
    diagnosis = parse_advisory_response("{}")

    assert diagnosis.status == "schema_missing_fields"
    assert diagnosis.should_execute is True
    assert diagnosis.score == 0.0
    assert diagnosis.parse_success is False
    assert diagnosis.parse_failure_type == "schema_missing_fields"
    assert diagnosis.diagnosed_errors[0].type == "parse_failed"
