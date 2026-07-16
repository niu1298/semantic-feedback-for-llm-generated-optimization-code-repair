from __future__ import annotations

import json
import sys
from pathlib import Path


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
if str(EXPERIMENT_ROOT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_ROOT))

from src.config import ExperimentConfig
from src.strategy_runner import StrategyRunner, _problem_band, _select_stratified_problems


class FakeClient:
    def __init__(self) -> None:
        self.responses = [
            "```python\ndef solve_model():\n    return 1.0\n```",
            "```python\ndef solve_model():\n    return 7.0\n```",
        ]
        self.calls = 0

    def chat(self, messages: list[dict]) -> str:
        del messages
        response = self.responses[self.calls]
        self.calls += 1
        return response


def semantic_code(value: float) -> str:
    return (
        "```python\n"
        "class M:\n"
        "    def setObjective(self, expr):\n"
        "        self.expr = expr\n\n"
        "def solve_model():\n"
        "    model = M()\n"
        "    model.setObjective(0)\n"
        f"    return {value}\n"
        "```"
    )


class RepeatingFakeClient:
    def __init__(self) -> None:
        self.calls = 0

    def chat(self, messages: list[dict]) -> str:
        del messages
        self.calls += 1
        return "```python\ndef solve_model():\n    return 1.0\n```"


def fake_executor(code, run_dir, timeout_seconds, expected_answer_metadata=None):
    del timeout_seconds, expected_answer_metadata
    Path(run_dir).mkdir(parents=True, exist_ok=True)
    objective = 7.0 if "return 7.0" in code else 1.0
    stdout_path = Path(run_dir) / "stdout.txt"
    stderr_path = Path(run_dir) / "stderr.txt"
    stdout_path.write_text(f"OBJECTIVE={objective}\n", encoding="utf-8")
    stderr_path.write_text("", encoding="utf-8")
    return {
        "executed": True,
        "returncode": 0,
        "stdout": f"OBJECTIVE={objective}\n",
        "stderr": "",
        "timeout": False,
        "objective": objective,
        "error_type": None,
        "run_dir": str(run_dir),
        "elapsed_seconds": 0.01,
        "generated_code_path": None,
        "runner_path": None,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
    }


def fake_rejecting_semantic_checker(**kwargs):
    assert kwargs["provider"] == "openai"
    return {
        "passed": False,
        "skipped": False,
        "status": "ok",
        "score": 0.2,
        "should_execute": False,
        "missing_constraints": ["capacity constraint"],
        "wrong_objective": False,
        "variable_issues": [],
        "gurobi_api_issues": [],
        "output_issues": [],
        "feedback": "Missing capacity constraint.",
    }


def fake_passing_semantic_checker(**kwargs):
    assert kwargs["threshold"] == 0.6
    return {
        "passed": True,
        "skipped": False,
        "status": "ok",
        "score": 0.9,
        "should_execute": True,
        "missing_constraints": [],
        "wrong_objective": False,
        "variable_issues": [],
        "gurobi_api_issues": [],
        "output_issues": [],
        "feedback": "Looks executable.",
    }


def fake_empty_response_semantic_checker(**kwargs):
    assert kwargs["provider"] == "openai"
    return {
        "passed": False,
        "skipped": False,
        "status": "empty_response",
        "score": 0.0,
        "should_execute": True,
        "missing_constraints": [],
        "wrong_objective": False,
        "variable_issues": [],
        "gurobi_api_issues": [],
        "output_issues": [],
        "feedback": "Semantic diagnosis unavailable; use execution feedback.",
        "raw_response": "",
        "advisory_diagnosis": {
            "diagnosis_id": "empty",
            "round": 0,
            "advisor_name": "openai:gpt-4o-mini",
            "score": 0.0,
            "diagnosed_errors": [
                {
                    "type": "empty_response",
                    "severity": "medium",
                    "description": "Semantic judge returned an empty response.",
                    "evidence": "",
                    "suggested_fix": "Use execution feedback.",
                }
            ],
            "repair_instructions": ["Semantic diagnosis unavailable; use execution feedback."],
            "confidence": 0.0,
            "reject_reasons": [],
            "should_execute": True,
            "raw_response": "",
            "status": "empty_response",
            "parse_success": False,
            "empty_response": True,
            "parse_failure_type": "empty_response",
            "parse_debug": {"finish_reason": "stop"},
        },
        "diagnosed_error_types": ["empty_response"],
        "repair_instructions": ["Semantic diagnosis unavailable; use execution feedback."],
        "confidence": 0.0,
        "reject_reasons": [],
        "parse_success": False,
        "empty_response": True,
        "parse_failure_type": "empty_response",
        "debug_metadata": {"finish_reason": "stop"},
    }


class SequenceSemanticChecker:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = responses
        self.calls: list[dict] = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses[len(self.calls) - 1]


def test_stratified_problem_selection_respects_max_per_band() -> None:
    problems = [
        {
            "problem_id": f"prob_{rank:03d}",
            "metadata": {"difficulty_rank": rank},
        }
        for rank in range(92)
    ]

    selected = _select_stratified_problems(
        problems,
        max_problems_per_band=2,
        random_seed=123,
    )
    counts: dict[str, int] = {}
    for problem in selected:
        band = _problem_band(problem)
        counts[band] = counts.get(band, 0) + 1
    selected_again = _select_stratified_problems(
        problems,
        max_problems_per_band=2,
        random_seed=123,
    )

    assert counts == {"band1": 2, "band2": 2, "band3": 2, "band4": 2}
    assert [problem["problem_id"] for problem in selected] == [
        problem["problem_id"] for problem in selected_again
    ]


def raising_executor(*args, **kwargs):
    raise AssertionError("executor should not be called")


def semantic_config(tmp_path: Path, max_rounds: int = 1) -> ExperimentConfig:
    return ExperimentConfig(
        problem_source="orthought",
        dataset_name="logior",
        problem_limit=1,
        strategy="semantic_execution",
        llm_provider="moonshot",
        llm_model="moonshot-v1-8k",
        semantic_provider="openai",
        semantic_model="gpt-4o-mini",
        request_timeout_seconds=45,
        max_retries=0,
        max_tokens=2048,
        temperature=0.0,
        thinking="default",
        output_dir=tmp_path,
        max_rounds=max_rounds,
        strategies=["semantic_execution"],
        semantic_threshold=0.6,
        solver_timeout_seconds=30,
    )


def semantic_advisory_config(tmp_path: Path, max_rounds: int = 1) -> ExperimentConfig:
    config = semantic_config(tmp_path, max_rounds=max_rounds)
    return ExperimentConfig(
        problem_source=config.problem_source,
        dataset_name=config.dataset_name,
        problem_limit=config.problem_limit,
        strategy="semantic_advisory_execution",
        llm_provider=config.llm_provider,
        llm_model=config.llm_model,
        semantic_provider=config.semantic_provider,
        semantic_model=config.semantic_model,
        request_timeout_seconds=config.request_timeout_seconds,
        max_retries=config.max_retries,
        max_tokens=config.max_tokens,
        temperature=config.temperature,
        thinking=config.thinking,
        output_dir=config.output_dir,
        max_rounds=config.max_rounds,
        strategies=["semantic_advisory_execution"],
        semantic_threshold=config.semantic_threshold,
        solver_timeout_seconds=config.solver_timeout_seconds,
    )


def semantic_cascade_config(tmp_path: Path) -> ExperimentConfig:
    config = semantic_config(tmp_path)
    return ExperimentConfig(
        problem_source=config.problem_source,
        dataset_name=config.dataset_name,
        problem_limit=config.problem_limit,
        strategy=config.strategy,
        llm_provider=config.llm_provider,
        llm_model=config.llm_model,
        semantic_provider=config.semantic_provider,
        semantic_model=config.semantic_model,
        request_timeout_seconds=config.request_timeout_seconds,
        max_retries=config.max_retries,
        max_tokens=config.max_tokens,
        temperature=config.temperature,
        thinking=config.thinking,
        output_dir=config.output_dir,
        max_rounds=config.max_rounds,
        strategies=config.strategies,
        semantic_threshold=0.5,
        semantic_fast_provider="openai",
        semantic_fast_model="gpt-4o-mini",
        semantic_strong_provider="openai",
        semantic_strong_model="gpt-4o-mini",
        semantic_cascade_enabled=True,
        semantic_low_threshold=0.4,
        semantic_high_threshold=0.75,
        solver_timeout_seconds=config.solver_timeout_seconds,
    )


def test_strategy_runner_represents_multiple_execution_only_rounds(tmp_path: Path) -> None:
    config = ExperimentConfig(
        problem_source="orthought",
        dataset_name="logior",
        problem_limit=1,
        strategy="execution_only",
        llm_provider="moonshot",
        llm_model="moonshot-v1-8k",
        semantic_provider=None,
        semantic_model=None,
        request_timeout_seconds=45,
        max_retries=0,
        max_tokens=2048,
        temperature=0.0,
        thinking="default",
        output_dir=tmp_path,
        max_rounds=3,
        strategies=["execution_only"],
        solver_timeout_seconds=30,
    )
    runner = StrategyRunner(config=config, llm_client=FakeClient(), executor_fn=fake_executor)
    problem = {
        "problem_id": "p1",
        "dataset_name": "logior",
        "problem_text": "Return the target objective.",
        "metadata": {"answer": {"obj": 7.0}},
    }

    result = runner._run_execution_only_problem(problem, runner.llm_client, tmp_path)

    assert len(result.rounds) == 2
    assert result.final_valid is True
    assert result.time_to_first_valid is not None
    assert result.rounds[0].error_type == "objective_mismatch"
    assert result.rounds[1].objective_match is True
    assert (tmp_path / "p1" / "round_00" / "prompt.txt").is_file()
    assert (tmp_path / "p1" / "round_01" / "extracted_code.py").is_file()
    assert (tmp_path / "p1" / "round_01" / "feedback.txt").is_file()


def test_strategy_runner_detects_repeated_code_hash(tmp_path: Path) -> None:
    config = ExperimentConfig(
        problem_source="orthought",
        dataset_name="logior",
        problem_limit=1,
        strategy="execution_only",
        llm_provider="moonshot",
        llm_model="moonshot-v1-8k",
        semantic_provider=None,
        semantic_model=None,
        request_timeout_seconds=45,
        max_retries=0,
        max_tokens=2048,
        temperature=0.0,
        thinking="default",
        output_dir=tmp_path,
        max_rounds=2,
        strategies=["execution_only"],
        solver_timeout_seconds=30,
    )
    runner = StrategyRunner(config=config, llm_client=RepeatingFakeClient(), executor_fn=fake_executor)
    problem = {
        "problem_id": "p_repeat",
        "dataset_name": "logior",
        "problem_text": "Return the target objective.",
        "metadata": {"answer": {"obj": 7.0}},
    }

    result = runner._run_execution_only_problem(problem, runner.llm_client, tmp_path)

    assert len(result.rounds) == 2
    assert result.rounds[1].previous_code_hash == result.rounds[0].code_hash
    assert result.rounds[1].code_changed_from_previous is False
    assert result.rounds[1].response_changed_from_previous is False


def test_mask_expected_objective_hides_answer_from_repair_prompt(tmp_path: Path) -> None:
    config = ExperimentConfig(
        problem_source="orthought",
        dataset_name="logior",
        problem_limit=1,
        strategy="execution_only",
        llm_provider="moonshot",
        llm_model="moonshot-v1-8k",
        semantic_provider=None,
        semantic_model=None,
        request_timeout_seconds=45,
        max_retries=0,
        max_tokens=2048,
        temperature=0.0,
        thinking="default",
        output_dir=tmp_path,
        max_rounds=2,
        strategies=["execution_only"],
        solver_timeout_seconds=30,
        mask_expected_objective=True,
    )
    runner = StrategyRunner(config=config, llm_client=FakeClient(), executor_fn=fake_executor)
    problem = {
        "problem_id": "p_masked",
        "dataset_name": "logior",
        "problem_text": "Return the target objective.",
        "metadata": {"answer": {"obj": 7.0}},
    }

    result = runner._run_execution_only_problem(problem, runner.llm_client, tmp_path)

    assert result.final_valid is True
    feedback_text = (tmp_path / "p_masked" / "round_01" / "feedback.txt").read_text(encoding="utf-8")
    assert "expected_objective:" not in feedback_text
    assert "objective_gap:" not in feedback_text
    metadata = json.loads((tmp_path / "p_masked" / "round_00" / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["expected_objective"] == 7.0
    assert metadata["objective_gap"] == 6.0


def test_semantic_execution_skips_execution_when_semantic_rejects(tmp_path: Path) -> None:
    client = FakeClient()
    client.responses = [semantic_code(1.0)]
    runner = StrategyRunner(
        config=semantic_config(tmp_path),
        llm_client=client,
        executor_fn=raising_executor,
        semantic_checker_fn=fake_rejecting_semantic_checker,
    )
    problem = {
        "problem_id": "p_semantic_reject",
        "dataset_name": "logior",
        "problem_text": "Return the target objective.",
        "metadata": {"answer": {"obj": 7.0}},
    }

    result = runner._run_execution_only_problem(problem, runner.llm_client, tmp_path)

    assert len(result.rounds) == 1
    round_result = result.rounds[0]
    assert round_result.error_type == "semantic_reject"
    assert round_result.semantic_calls == 1
    assert round_result.semantic_check_passed is False
    assert round_result.semantic_score == 0.2
    assert round_result.solver_calls == 0
    assert round_result.executed is False
    assert "capacity constraint" in round_result.semantic_missing_constraints
    assert (tmp_path / "p_semantic_reject" / "round_00" / "semantic_feedback.json").is_file()
    assert (tmp_path / "p_semantic_reject" / "round_00" / "semantic_prompt.txt").is_file()
    assert round_result.semantic_prompt_path is not None


def test_semantic_execution_executes_when_semantic_passes(tmp_path: Path) -> None:
    client = FakeClient()
    client.responses = [semantic_code(7.0)]
    runner = StrategyRunner(
        config=semantic_config(tmp_path),
        llm_client=client,
        executor_fn=fake_executor,
        semantic_checker_fn=fake_passing_semantic_checker,
    )
    problem = {
        "problem_id": "p_semantic_pass",
        "dataset_name": "logior",
        "problem_text": "Return the target objective.",
        "metadata": {"answer": {"obj": 7.0}},
    }

    result = runner._run_execution_only_problem(problem, runner.llm_client, tmp_path)

    assert result.final_valid is True
    assert result.rounds[0].semantic_calls == 1
    assert result.rounds[0].semantic_check_passed is True
    assert result.rounds[0].semantic_should_execute is True
    assert result.rounds[0].solver_calls == 1
    assert result.rounds[0].objective_match is True
    assert result.rounds[0].semantic_prompt_path is not None


def test_semantic_checker_uses_semantic_max_tokens(tmp_path: Path) -> None:
    client = FakeClient()
    client.responses = [semantic_code(7.0)]
    checker = SequenceSemanticChecker(
        [
            {
                "passed": True,
                "skipped": False,
                "status": "ok",
                "score": 0.9,
                "should_execute": True,
                "missing_constraints": [],
                "wrong_objective": False,
                "variable_issues": [],
                "gurobi_api_issues": [],
                "output_issues": [],
                "feedback": "Looks executable.",
            }
        ]
    )
    config = ExperimentConfig(
        problem_source="orthought",
        dataset_name="logior",
        problem_limit=1,
        strategy="semantic_execution",
        llm_provider="openai",
        llm_model="gpt-5-mini",
        semantic_provider="moonshot",
        semantic_model="kimi-k2.6",
        request_timeout_seconds=45,
        max_retries=0,
        max_tokens=2048,
        semantic_max_tokens=512,
        temperature=0.0,
        thinking="default",
        output_dir=tmp_path,
        max_rounds=1,
        strategies=["semantic_execution"],
        semantic_threshold=0.5,
        solver_timeout_seconds=30,
    )
    runner = StrategyRunner(
        config=config,
        llm_client=client,
        executor_fn=fake_executor,
        semantic_checker_fn=checker,
    )
    problem = {
        "problem_id": "p_semantic_tokens",
        "dataset_name": "logior",
        "problem_text": "Return the target objective.",
        "metadata": {"answer": {"obj": 7.0}},
    }

    runner._run_execution_only_problem(problem, runner.llm_client, tmp_path)

    assert checker.calls[0]["provider"] == "moonshot"
    assert checker.calls[0]["model"] == "kimi-k2.6"
    assert checker.calls[0]["max_tokens"] == 512


def test_client_factories_keep_generation_and_semantic_token_limits_separate(tmp_path: Path) -> None:
    config = ExperimentConfig(
        problem_source="orthought",
        dataset_name="logior",
        problem_limit=1,
        strategy="semantic_execution",
        llm_provider="openai",
        llm_model="gpt-4o-mini",
        semantic_provider="openai",
        semantic_model="gpt-5-mini",
        request_timeout_seconds=45,
        max_retries=0,
        max_tokens=2048,
        semantic_max_tokens=8192,
        temperature=0.0,
        thinking="default",
        output_dir=tmp_path,
        max_rounds=1,
        strategies=["semantic_execution"],
        semantic_threshold=0.5,
        solver_timeout_seconds=30,
    )
    runner = StrategyRunner(config=config)

    generation_client = runner._make_llm_client()
    semantic_client = runner._make_semantic_client()

    assert generation_client.max_tokens == 2048
    assert semantic_client.max_tokens == 8192


def test_semantic_advisory_executes_even_when_semantic_rejects(tmp_path: Path) -> None:
    client = FakeClient()
    client.responses = [semantic_code(7.0)]
    runner = StrategyRunner(
        config=semantic_advisory_config(tmp_path),
        llm_client=client,
        executor_fn=fake_executor,
        semantic_checker_fn=fake_rejecting_semantic_checker,
    )
    problem = {
        "problem_id": "p_advisory_reject",
        "dataset_name": "logior",
        "problem_text": "Return the target objective.",
        "metadata": {"answer": {"obj": 7.0}},
    }

    result = runner._run_execution_only_problem(problem, runner.llm_client, tmp_path)

    round_result = result.rounds[0]
    assert result.final_valid is True
    assert round_result.semantic_calls == 1
    assert round_result.semantic_check_passed is False
    assert round_result.semantic_advisory_used is True
    assert round_result.semantic_gate_stage == "advisory"
    assert round_result.solver_calls == 1
    assert round_result.executed is True
    assert round_result.objective_match is True
    assert (tmp_path / "p_advisory_reject" / "round_00" / "semantic_feedback.json").is_file()
    assert (tmp_path / "p_advisory_reject" / "round_00" / "semantic_prompt.txt").is_file()


def test_semantic_advisory_skips_judge_and_execution_on_compile_failure(tmp_path: Path) -> None:
    client = FakeClient()
    client.responses = ["```python\ndef solve_model(:\n    return 7.0\n```"]
    runner = StrategyRunner(
        config=semantic_advisory_config(tmp_path),
        llm_client=client,
        executor_fn=raising_executor,
        semantic_checker_fn=lambda **kwargs: (_ for _ in ()).throw(AssertionError("judge should not be called")),
    )
    problem = {
        "problem_id": "p_advisory_compile",
        "dataset_name": "logior",
        "problem_text": "Return the target objective.",
        "metadata": {"answer": {"obj": 7.0}},
    }

    result = runner._run_execution_only_problem(problem, runner.llm_client, tmp_path)

    round_result = result.rounds[0]
    assert round_result.error_type == "compile_failed"
    assert round_result.semantic_calls == 0
    assert round_result.semantic_advisory_used is False
    assert round_result.solver_calls == 0
    assert round_result.executed is False


def test_retrospective_gate_logs_false_rejection_and_convergence(tmp_path: Path) -> None:
    client = FakeClient()
    client.responses = [semantic_code(7.0)]
    config = semantic_advisory_config(tmp_path)
    config = ExperimentConfig(
        problem_source=config.problem_source,
        dataset_name=config.dataset_name,
        problem_limit=config.problem_limit,
        strategy="semantic_advisory_execution",
        llm_provider=config.llm_provider,
        llm_model=config.llm_model,
        semantic_provider=config.semantic_provider,
        semantic_model=config.semantic_model,
        request_timeout_seconds=config.request_timeout_seconds,
        max_retries=config.max_retries,
        max_tokens=config.max_tokens,
        temperature=config.temperature,
        thinking=config.thinking,
        output_dir=config.output_dir,
        max_rounds=config.max_rounds,
        strategies=config.strategies,
        semantic_threshold=config.semantic_threshold,
        solver_timeout_seconds=config.solver_timeout_seconds,
        advisory_mode="retrospective_gate",
    )
    runner = StrategyRunner(
        config=config,
        llm_client=client,
        executor_fn=fake_executor,
        semantic_checker_fn=fake_rejecting_semantic_checker,
    )
    problem = {
        "problem_id": "p_retrospective",
        "dataset_name": "logior",
        "problem_text": "Return the target objective.",
        "metadata": {"answer": {"obj": 7.0}, "difficulty_rank": 0},
    }

    result = runner._run_execution_only_problem(problem, runner.llm_client, tmp_path)

    round_result = result.rounds[0]
    assert result.final_valid is True
    assert round_result.executed is True
    assert round_result.retrospective_gate_would_skip is True
    assert round_result.retrospective_false_rejection is True
    round_log = tmp_path / "convergence_rounds.jsonl"
    problem_log = tmp_path / "convergence_problem_summary.jsonl"
    assert round_log.is_file()
    assert problem_log.is_file()
    record = json.loads(round_log.read_text(encoding="utf-8").splitlines()[0])
    assert record["advisory_mode"] == "retrospective_gate"
    assert record["retrospective_false_rejection"] is True
    assert record["solver_calls_cumulative"] == 1


def test_explicit_diagnosis_only_executes_compile_failed_candidate(tmp_path: Path) -> None:
    client = FakeClient()
    client.responses = ["```python\ndef solve_model(:\n    return 7.0\n```"]
    config = semantic_advisory_config(tmp_path)
    config = ExperimentConfig(
        problem_source=config.problem_source,
        dataset_name=config.dataset_name,
        problem_limit=config.problem_limit,
        strategy="semantic_advisory_execution",
        llm_provider=config.llm_provider,
        llm_model=config.llm_model,
        semantic_provider=config.semantic_provider,
        semantic_model=config.semantic_model,
        request_timeout_seconds=config.request_timeout_seconds,
        max_retries=config.max_retries,
        max_tokens=config.max_tokens,
        temperature=config.temperature,
        thinking=config.thinking,
        output_dir=config.output_dir,
        max_rounds=config.max_rounds,
        strategies=config.strategies,
        semantic_threshold=config.semantic_threshold,
        solver_timeout_seconds=config.solver_timeout_seconds,
        advisory_mode="diagnosis_only",
    )
    runner = StrategyRunner(
        config=config,
        llm_client=client,
        executor_fn=fake_executor,
        semantic_checker_fn=fake_rejecting_semantic_checker,
    )
    problem = {
        "problem_id": "p_diagnosis_compile",
        "dataset_name": "logior",
        "problem_text": "Return the target objective.",
        "metadata": {"answer": {"obj": 7.0}},
    }

    result = runner._run_execution_only_problem(problem, runner.llm_client, tmp_path)

    round_result = result.rounds[0]
    assert round_result.semantic_calls == 1
    assert round_result.executed is True
    assert round_result.solver_calls == 1
    assert round_result.semantic_should_execute is False


def test_empty_response_does_not_block_diagnosis_only_or_retrospective_gate(tmp_path: Path) -> None:
    problem = {
        "problem_id": "p_empty_advisory",
        "dataset_name": "logior",
        "problem_text": "Return the target objective.",
        "metadata": {"answer": {"obj": 7.0}, "difficulty_rank": 0},
    }
    for advisory_mode in ("diagnosis_only", "retrospective_gate"):
        run_path = tmp_path / advisory_mode
        client = FakeClient()
        client.responses = [semantic_code(7.0)]
        config = semantic_advisory_config(run_path)
        config = ExperimentConfig(
            problem_source=config.problem_source,
            dataset_name=config.dataset_name,
            problem_limit=config.problem_limit,
            strategy="semantic_advisory_execution",
            llm_provider=config.llm_provider,
            llm_model=config.llm_model,
            semantic_provider=config.semantic_provider,
            semantic_model=config.semantic_model,
            request_timeout_seconds=config.request_timeout_seconds,
            max_retries=config.max_retries,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            thinking=config.thinking,
            output_dir=config.output_dir,
            max_rounds=config.max_rounds,
            strategies=config.strategies,
            semantic_threshold=config.semantic_threshold,
            solver_timeout_seconds=config.solver_timeout_seconds,
            advisory_mode=advisory_mode,
        )
        runner = StrategyRunner(
            config=config,
            llm_client=client,
            executor_fn=fake_executor,
            semantic_checker_fn=fake_empty_response_semantic_checker,
        )

        result = runner._run_execution_only_problem(problem, runner.llm_client, run_path)

        round_result = result.rounds[0]
        assert result.final_valid is True
        assert round_result.executed is True
        assert round_result.solver_calls == 1
        assert round_result.semantic_parse_success is False
        assert round_result.semantic_empty_response is True
        assert round_result.semantic_parse_failure_type == "empty_response"
        record = json.loads((run_path / "convergence_rounds.jsonl").read_text(encoding="utf-8").splitlines()[0])
        assert record["semantic_parse_success"] is False
        assert record["semantic_empty_response"] is True
        if advisory_mode == "retrospective_gate":
            assert record["retrospective_gate_would_execute"] is True


def test_empty_response_does_not_block_hard_gate(tmp_path: Path) -> None:
    client = FakeClient()
    client.responses = [semantic_code(7.0)]
    config = semantic_config(tmp_path)
    runner = StrategyRunner(
        config=config,
        llm_client=client,
        executor_fn=fake_executor,
        semantic_checker_fn=fake_empty_response_semantic_checker,
    )
    problem = {
        "problem_id": "p_empty_hard_gate",
        "dataset_name": "logior",
        "problem_text": "Return the target objective.",
        "metadata": {"answer": {"obj": 7.0}, "difficulty_rank": 0},
    }

    result = runner._run_execution_only_problem(problem, runner.llm_client, tmp_path)

    round_result = result.rounds[0]
    assert result.final_valid is True
    assert round_result.executed is True
    assert round_result.solver_calls == 1
    assert round_result.semantic_should_execute is True
    assert round_result.semantic_parse_failure_type == "empty_response"


def test_selected_problems_manifest_is_written_for_problem_ids(tmp_path: Path) -> None:
    class FakeAdapter:
        def load_problems(self, limit=None, offset=0):
            del limit, offset
            return [
                {"problem_id": "prob_001", "metadata": {"difficulty_rank": 0}},
                {"problem_id": "prob_002", "metadata": {"difficulty_rank": 20}},
            ]

    config = ExperimentConfig(
        problem_source="orthought",
        dataset_name="logior",
        problem_limit=2,
        problem_ids=["prob_002", "prob_001"],
        strategy="execution_only",
        llm_provider="moonshot",
        llm_model="moonshot-v1-8k",
        semantic_provider=None,
        semantic_model=None,
        request_timeout_seconds=45,
        max_retries=0,
        max_tokens=2048,
        temperature=0.0,
        thinking="default",
        output_dir=tmp_path,
        max_rounds=1,
        strategies=["execution_only"],
        solver_timeout_seconds=30,
    )
    runner = StrategyRunner(config=config)

    selected = runner._load_selected_problems(FakeAdapter(), tmp_path)

    assert [problem["problem_id"] for problem in selected] == ["prob_002", "prob_001"]
    manifest = json.loads((tmp_path / "selected_problems.json").read_text(encoding="utf-8"))
    assert manifest["selection_method"] == "problem_ids"
    assert manifest["problem_ids"] == ["prob_002", "prob_001"]
    assert manifest["config_name"] == "execution_only"


def test_explicit_advisory_none_executes_compile_failed_candidate(tmp_path: Path) -> None:
    client = FakeClient()
    client.responses = ["```python\ndef solve_model(:\n    return 7.0\n```"]
    config = ExperimentConfig(
        problem_source="orthought",
        dataset_name="logior",
        problem_limit=1,
        strategy="execution_only",
        llm_provider="moonshot",
        llm_model="moonshot-v1-8k",
        semantic_provider=None,
        semantic_model=None,
        request_timeout_seconds=45,
        max_retries=0,
        max_tokens=2048,
        temperature=0.0,
        thinking="default",
        output_dir=tmp_path,
        max_rounds=1,
        strategies=["execution_only"],
        solver_timeout_seconds=30,
        advisory_mode="none",
    )
    runner = StrategyRunner(config=config, llm_client=client, executor_fn=fake_executor)
    problem = {
        "problem_id": "p_none_compile",
        "dataset_name": "logior",
        "problem_text": "Return the target objective.",
        "metadata": {"answer": {"obj": 7.0}},
    }

    result = runner._run_execution_only_problem(problem, runner.llm_client, tmp_path)

    round_result = result.rounds[0]
    assert round_result.executed is True
    assert round_result.solver_calls == 1


def test_semantic_rule_precheck_rejects_before_llm_judge(tmp_path: Path) -> None:
    client = FakeClient()
    client.responses = ["```python\ndef solve_model():\n    return 1.0\n```"]
    runner = StrategyRunner(
        config=semantic_config(tmp_path),
        llm_client=client,
        executor_fn=raising_executor,
        semantic_checker_fn=lambda **kwargs: (_ for _ in ()).throw(AssertionError("judge should not be called")),
    )
    problem = {
        "problem_id": "p_rule_reject",
        "dataset_name": "logior",
        "problem_text": "Return the target objective.",
        "metadata": {"answer": {"obj": 7.0}},
    }

    result = runner._run_execution_only_problem(problem, runner.llm_client, tmp_path)

    round_result = result.rounds[0]
    assert round_result.error_type == "rule_semantic_reject"
    assert round_result.semantic_calls == 0
    assert round_result.rule_semantic_reject is True
    assert "missing_setObjective" in round_result.rule_semantic_issues
    assert round_result.solver_calls == 0
    semantic_prompt = (tmp_path / "p_rule_reject" / "round_00" / "semantic_prompt.txt").read_text(encoding="utf-8")
    assert "not sent because the local rule precheck rejected first" in semantic_prompt


def test_semantic_cascade_fast_accept_executes_without_strong_call(tmp_path: Path) -> None:
    client = FakeClient()
    client.responses = [semantic_code(7.0)]
    checker = SequenceSemanticChecker(
        [
            {
                "passed": True,
                "score": 0.8,
                "should_execute": True,
                "missing_constraints": [],
                "wrong_objective": False,
                "variable_issues": [],
                "gurobi_api_issues": [],
                "output_issues": [],
                "feedback": "Fast pass.",
            }
        ]
    )
    runner = StrategyRunner(
        config=semantic_cascade_config(tmp_path),
        llm_client=client,
        executor_fn=fake_executor,
        semantic_checker_fn=checker,
    )
    problem = {
        "problem_id": "p_fast_accept",
        "dataset_name": "logior",
        "problem_text": "Return the target objective.",
        "metadata": {"answer": {"obj": 7.0}},
    }

    result = runner._run_execution_only_problem(problem, runner.llm_client, tmp_path)

    round_result = result.rounds[0]
    assert len(checker.calls) == 1
    assert round_result.fast_semantic_calls == 1
    assert round_result.strong_semantic_calls == 0
    assert round_result.cascade_fast_accept is True
    assert round_result.solver_calls == 1


def test_semantic_cascade_escalates_ambiguous_fast_score(tmp_path: Path) -> None:
    client = FakeClient()
    client.responses = [semantic_code(7.0)]
    checker = SequenceSemanticChecker(
        [
            {
                "passed": False,
                "score": 0.5,
                "should_execute": True,
                "missing_constraints": [],
                "wrong_objective": False,
                "variable_issues": [],
                "gurobi_api_issues": [],
                "output_issues": [],
                "feedback": "Ambiguous.",
            },
            {
                "passed": True,
                "score": 0.9,
                "should_execute": True,
                "missing_constraints": [],
                "wrong_objective": False,
                "variable_issues": [],
                "gurobi_api_issues": [],
                "output_issues": [],
                "feedback": "Strong pass.",
            },
        ]
    )
    runner = StrategyRunner(
        config=semantic_cascade_config(tmp_path),
        llm_client=client,
        executor_fn=fake_executor,
        semantic_checker_fn=checker,
    )
    problem = {
        "problem_id": "p_escalate",
        "dataset_name": "logior",
        "problem_text": "Return the target objective.",
        "metadata": {"answer": {"obj": 7.0}},
    }

    result = runner._run_execution_only_problem(problem, runner.llm_client, tmp_path)

    round_result = result.rounds[0]
    assert len(checker.calls) == 2
    assert round_result.semantic_calls == 2
    assert round_result.fast_semantic_calls == 1
    assert round_result.strong_semantic_calls == 1
    assert round_result.cascade_escalated is True
    assert round_result.fast_semantic_score == 0.5
    assert round_result.strong_semantic_score == 0.9
