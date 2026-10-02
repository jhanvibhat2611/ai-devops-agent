import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from workflow.safety import precheck, validate_tests
from workflow.test_agent import test_implementation as generate_tests
from workflow.test_errors import TestValidationError as ValidationError, UnsafeCodeError

REQUEST = "Create a Python function multiply_by_three(number) that returns the number multiplied by 3."
SOURCE = "def multiply_by_three(number):\n    return number * 3"
TESTS = '''from generated_feature import multiply_by_three
def test_multiply_by_three_positive():
    assert multiply_by_three(5) == 15
def test_multiply_by_three_zero():
    assert multiply_by_three(0) == 0
def test_multiply_by_three_negative():
    assert multiply_by_three(-4) == -12
'''


def state(source=SOURCE):
    return {"user_request": REQUEST, "analysis": "Return the input multiplied by 3.", "generated_code": source}


def model(*outputs):
    return Mock(invoke=Mock(side_effect=[SimpleNamespace(content=code) for code in outputs]))


@pytest.mark.parametrize("footer", ["", '\nif __name__ == "__main__":\n    pytest.main()\n'])
def test_exact_multiply_request_accepts_normal_pytest_and_script_guard(footer):
    code = "import pytest\n" + TESTS + footer
    validate_tests(SOURCE, code)
    llm = model(code)
    result = generate_tests(state(), llm)
    assert result["test_passed"]
    assert result["test_result"] == "Pytest passed (3 tests)."
    llm.invoke.assert_called_once()
    assert REQUEST in llm.invoke.call_args.args[0]


@pytest.mark.parametrize("code,rule", [
    ("def test_value(): assert True", "missing_generated_feature_import"),
    ("import subprocess\n" + TESTS, "unsafe_test_import"),
    ("import hypothesis\n" + TESTS, "unsupported_test_dependency"),
    ("from generated_feature import multiply_by_three", "no_test_functions"),
    (TESTS + "\n".join(f"def test_extra_{i}(): assert multiply_by_three(1) == 3" for i in range(3)), "too_many_tests"),
    ("from generated_feature import multiply_by_three\ndef test_value(): multiply_by_three(1)", "missing_assertion"),
    ("from generated_feature import multiply_by_three\ndef test_value(): assert True", "missing_implementation_call"),
    (TESTS.replace("== 15", "== multiply_by_three(5)"), "self_oracle"),
    (TESTS.replace("    assert multiply_by_three(5) == 15", "    expected = multiply_by_three(5)\n    assert multiply_by_three(5) == expected"), "self_oracle"),
    (TESTS + "\ndef multiply_by_three(number): return number * 3", "source_reimplementation"),
    ("print(__name__)\n" + TESTS, "unsafe_test_name"),
    ("value = (1).__class__\n" + TESTS, "unsafe_test_attribute"),
])
def test_specific_validation_codes_survive_bounded_repairs(code, rule, caplog):
    with pytest.raises(ValidationError) as rejection:
        validate_tests(SOURCE, code)
    assert rejection.value.code == rule
    llm = model(code, code, code)
    result = generate_tests(state(), llm)
    assert result["test_passed"] is False
    assert result["test_failure"]["error_code"] == rule
    assert result["test_failure"]["stage"] == "test_validation"
    assert llm.invoke.call_count == 3
    assert rule in llm.invoke.call_args_list[1].args[0]
    assert f"rule={rule}" in caplog.text
    assert caplog.text.count("Generated test code (redacted structure") == 3


def test_invalid_tests_regenerate_using_exact_rule_and_then_run():
    llm = model("import subprocess\n" + TESTS, TESTS)
    result = generate_tests(state(), llm)
    assert result["test_passed"]
    assert llm.invoke.call_count == 2
    assert "unsafe_test_import" in llm.invoke.call_args.args[0]


def test_live_reproduction_copied_implementation_gets_actionable_repair(caplog):
    # Same structure as the observed live response: pytest import, copied source
    # at line 3, then tests, with no generated_feature import.
    copied = "import pytest\n\n" + SOURCE + "\n\n" + TESTS.split("\n", 1)[1]
    llm = model(copied, TESTS)
    result = generate_tests(state(), llm)
    assert result["test_passed"]
    assert llm.invoke.call_count == 2
    assert "rule=source_reimplementation line=3 ast=FunctionDef" in caplog.text
    repair = llm.invoke.call_args.args[0]
    assert "Delete copied implementation definitions entirely" in repair
    assert "Available implementation function names: multiply_by_three" in repair


def test_wrong_multiply_implementation_fails_without_rewriting_tests():
    llm = model(TESTS)
    result = generate_tests(state(SOURCE.replace("* 3", "* 2")), llm)
    assert not result["test_passed"]
    assert result["test_failure"]["error_category"] == "implementation_failure"
    llm.invoke.assert_called_once()


def test_diagnostics_show_rejected_name_without_model_secrets(monkeypatch, caplog):
    secret = "unlabelled_fixture_credential_938275"
    monkeypatch.setenv("PRIVATE_SETTING", secret)
    code = f'# {secret}\n{secret} = "{secret}"\nnumber_secret = 938275\n' + TESTS + '\nprint(__name__)'
    result = generate_tests(state(), model(code, code, code))
    assert "ast=Name rejected_name=__name__" in caplog.text
    assert "line=12" in caplog.text
    assert "<literal redacted>" in caplog.text
    assert "from generated_feature import symbol_" in caplog.text
    assert "Traceback" in caplog.text
    assert secret not in caplog.text + json.dumps(result)
    assert "938275" not in caplog.text + json.dumps(result)


@pytest.mark.parametrize("prefix", [
    "value = __name__", "__name__ = 'changed'", "value = __builtins__",
    "if __name__ != '__main__':\n    print('unsafe guard')",
    "if __name__ == '__main__':\n    eval('1')",
    "if __name__ == '__main__':\n    pass\nelse:\n    print('not a script footer')",
])
def test_main_guard_exception_does_not_allow_general_dunder_access(prefix):
    with pytest.raises(ValidationError):
        validate_tests(SOURCE, prefix + "\n" + TESTS)
    with pytest.raises(UnsafeCodeError):
        precheck(prefix)
