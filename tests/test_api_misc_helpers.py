from types import SimpleNamespace

from backend.helpers.misc_helpers import (
    dashboard_feature_enabled,
    is_max_iterations_output,
    request_field_set,
)


def test_request_field_set_prefers_model_fields_set():
    model = SimpleNamespace(model_fields_set={"panel_id", "model"})

    assert request_field_set(model) == {"panel_id", "model"}


def test_request_field_set_falls_back_to_fields_set():
    model = SimpleNamespace(__fields_set__={"panel_id", "provider"})

    assert request_field_set(model) == {"panel_id", "provider"}


def test_request_field_set_handles_empty_models():
    assert request_field_set(SimpleNamespace()) == set()


def test_is_max_iterations_output_matches_known_variants():
    assert is_max_iterations_output("Agent stopped due to max iterations") is True
    assert is_max_iterations_output("Agent stopped due to iteration limit") is True
    assert is_max_iterations_output("Agent stopped after many iteration cycles") is True


def test_is_max_iterations_output_rejects_normal_text():
    assert is_max_iterations_output("all good") is False


def test_dashboard_feature_enabled_defaults_to_enabled_for_missing_or_non_dict_template():
    assert dashboard_feature_enabled(None) is True
    assert dashboard_feature_enabled("not-a-template") is True
    assert dashboard_feature_enabled({}) is True


def test_dashboard_feature_enabled_only_disables_explicit_false():
    assert dashboard_feature_enabled({"enabled": False}) is False
    assert dashboard_feature_enabled({"enabled": 0}) is True
    assert dashboard_feature_enabled({"enabled": None}) is True
