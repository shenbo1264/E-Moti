import guanghe_companion.ai_expressor as ai_expressor_module
import guanghe_companion.expression_request as expression_request_module
from guanghe_companion.ai_expressor import ExpressionRequest


def test_ai_expressor_reexports_expression_request_from_dedicated_module():
    assert expression_request_module.ExpressionRequest is ExpressionRequest
    assert ai_expressor_module.ExpressionRequest is expression_request_module.ExpressionRequest


def test_expression_request_module_exports_request_sanitizers():
    assert hasattr(expression_request_module, "ensure_expression_request")
