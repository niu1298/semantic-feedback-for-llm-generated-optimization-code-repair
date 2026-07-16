from __future__ import annotations

import sys
from pathlib import Path


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
if str(EXPERIMENT_ROOT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_ROOT))

from src.config import load_config


def test_final_direct_advisory_config_loads_standalone_path() -> None:
    config = load_config("configs/final/advisory_diagnosis_only_gpt5_short.yaml")

    assert config.problem_source == "orthought"
    assert config.dataset_name == "logior"
    assert config.problem_limit == 92
    assert config.strategy == "semantic_advisory_execution"
    assert config.llm_provider == "openai"
    assert config.llm_model == "gpt-4o-mini"
    assert config.semantic_provider == "openai"
    assert config.semantic_model == "gpt-5-mini"
    assert config.max_rounds == 2
    assert config.mask_expected_objective is True
    assert config.advisory_mode == "diagnosis_only"
    assert config.output_dir == EXPERIMENT_ROOT / "outputs" / "final" / "raw_runs"


def test_all_final_configs_load() -> None:
    expected = {
        "advisory_diagnosis_only_gpt5_short_adaptive_compressed.yaml",
        "baseline_exec_only.yaml",
        "advisory_diagnosis_only_gpt5_short.yaml",
        "spec_then_code.yaml",
    }
    paths = sorted((EXPERIMENT_ROOT / "configs" / "final").glob("*.yaml"))

    assert {path.name for path in paths} == expected
    for path in paths:
        config = load_config(path)
        assert config.problem_source == "orthought"
        assert config.dataset_name == "logior"
        assert config.problem_limit == 92
        assert config.output_dir == EXPERIMENT_ROOT / "outputs" / "final" / "raw_runs"
        assert config.mask_expected_objective is True


def test_smoke_config_is_offline_and_synthetic() -> None:
    config = load_config("configs/smoke/offline_synthetic.yaml")

    assert config.problem_source == "synthetic"
    assert config.dataset_name == "synthetic"
    assert config.problem_ids == ["synthetic_capacity", "synthetic_flow"]
    assert config.llm_provider == "offline"
    assert config.output_dir == EXPERIMENT_ROOT / "outputs" / "smoke"


def test_dataset_root_config_field_resolves_relative_path() -> None:
    config_path = EXPERIMENT_ROOT / "configs" / "smoke" / "offline_synthetic.yaml"
    text = config_path.read_text(encoding="utf-8").rstrip() + "\ndataset_root: data/raw/logior\n"
    temp_path = EXPERIMENT_ROOT / "configs" / "smoke" / "_tmp_dataset_root_test.yaml"
    try:
        temp_path.write_text(text, encoding="utf-8")
        config = load_config(temp_path)
        assert config.dataset_root == EXPERIMENT_ROOT / "data" / "raw" / "logior"
    finally:
        temp_path.unlink(missing_ok=True)