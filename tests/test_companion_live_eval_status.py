from tools.companion_live_eval import model_run_status


def test_fallback_is_not_successful_model_validation():
    assert model_run_status([{"fallback": "provider_error"}], []) == "not_run"
    assert model_run_status([{"error": "http_401"}], []) == "not_run"
    assert model_run_status([{"fallback": "provider_error"}], [{"usage": {}}]) == "failed"


def test_model_output_and_local_operations_are_reported_separately():
    assert model_run_status([{"reply": ["已忘记"], "fallback": None}], []) == "not_run"
    assert model_run_status([{"reply": ["好"], "fallback": None}], [{"usage": {}}]) == "completed"
