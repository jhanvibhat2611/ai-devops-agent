"""The JWT-login request must reach real pytest, not fail its source pre-check."""
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from workflow import test_agent
from workflow.safety import precheck, run_tests, UnsafeCodeError

REQUEST = "Create a login system using JWT."
ANALYSIS = """Expose login(username, password, users, signing_key, now).
users maps usernames to a salt and PBKDF2-HMAC-SHA256 digest (600000 iterations).
Invalid credentials return None. Valid credentials return an HS256 JWT with
sub equal to the username and exp equal to now plus 15 minutes (UTC timestamp).
The caller supplies the signing key and the clock; do not load application secrets."""
SOURCE = '''
import jwt
from datetime import timedelta
import hashlib
import hmac

def login(username, password, users, signing_key, now):
    record = users.get(username)
    if record is None:
        return None
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), record["salt"], 600000)
    if not hmac.compare_digest(digest, record["digest"]):
        return None
    return jwt.encode({"sub": username, "exp": int((now + timedelta(minutes=15)).timestamp())}, signing_key, algorithm="HS256")
'''
# Public, test-only fixtures; none are copied from a local account or environment.
KEY = "fixture-signing-key-32-bytes-not-a-real-secret"
DIGEST = hashlib.pbkdf2_hmac("sha256", b"fixture-password", b"fixture-salt", 600000)
TESTS = f'''
from generated_feature import login
from datetime import datetime, timezone
import jwt

def test_valid_credentials_issue_expected_claims():
    token = login("alice", "fixture-password", {{"alice": {{"salt": b"fixture-salt", "digest": {DIGEST!r}}}}}, {KEY!r}, datetime(2099, 1, 1, tzinfo=timezone.utc))
    claims = jwt.decode(token, {KEY!r}, algorithms=["HS256"])
    assert claims == {{"sub": "alice", "exp": 4070909700}}

def test_invalid_credentials_do_not_issue_token():
    assert login("alice", "incorrect", {{"alice": {{"salt": b"fixture-salt", "digest": {DIGEST!r}}}}}, {KEY!r}, datetime(2099, 1, 1, tzinfo=timezone.utc)) is None
'''


def model(content=TESTS):
    return Mock(invoke=Mock(return_value=SimpleNamespace(content=content)))


def state(source=SOURCE, analysis=ANALYSIS):
    return {"user_request": REQUEST, "analysis": analysis, "generated_code": source}


def test_exact_jwt_request_passes_local_signing_and_verification():
    llm = model()
    result = test_agent.test_implementation(state(), llm)
    assert result == {"test_passed": True, "test_result": "Pytest passed (2 tests).", "test_failure": None}
    llm.invoke.assert_called_once()
    prompt = llm.invoke.call_args.args[0]
    assert REQUEST in prompt and ANALYSIS in prompt and SOURCE in prompt
    assert prompt.index(REQUEST) < prompt.index(ANALYSIS) < prompt.index(SOURCE)


@pytest.mark.parametrize("bytes_decode_bug", [False, True])
def test_exact_jwt_request_environment_config_reaches_real_tests(bytes_decode_bug):
    source = 'import os\nJWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your_secret_key")\n' + SOURCE
    if bytes_decode_bug:
        source = source.replace('algorithm="HS256")', 'algorithm="HS256").decode("utf-8")')
    llm = model()
    original = state(source)
    result = test_agent.test_implementation(original, llm)
    assert result["test_passed"] is (not bytes_decode_bug)
    if bytes_decode_bug:
        assert result["test_failure"]["error_category"] == "implementation_failure"
    assert original["generated_code"] == source
    llm.invoke.assert_called_once()


def test_jwt_request_wrong_password_implementation_stays_failed(caplog):
    wrong = SOURCE.replace('if not hmac.compare_digest(digest, record["digest"]):', 'if False:')
    llm = model()
    result = test_agent.test_implementation(state(wrong), llm)
    assert not result["test_passed"]
    assert result["test_failure"]["error_category"] == "implementation_failure"
    assert result["test_failure"]["stage"] == "implementation_verification"
    llm.invoke.assert_called_once()  # Never rewrite correct expectations to go green.
    assert "UNIT TEST AGENT" in caplog.text
    assert KEY not in caplog.text + json.dumps(result)
    assert "fixture-password" not in caplog.text + json.dumps(result)


@pytest.mark.parametrize("source", [
    "import jwt\nx = jwt.PyJWKClient('https://example.invalid/keys')",
    "from jwt import PyJWKClient",
    "import jwt as j\nx = j.PyJWKClient('https://example.invalid')",
    "import jwt\nj = jwt\nx = j.PyJWKClient('https://example.invalid')",
    "import os\nos.system('blocked')", "import subprocess", "open('private-file')",
])
def test_new_jwt_profile_does_not_enable_network_or_secret_access(source):
    with pytest.raises(UnsafeCodeError):
        precheck(source)


def test_unreviewed_dependency_is_still_unsupported(caplog):
    llm = model()
    result = test_agent.test_implementation(state("import flask\ndef login(): pass"), llm)
    assert result["test_failure"]["error_category"] == "unsupported_generated_code"
    assert result["test_failure"]["stage"] == "source_precheck"
    llm.invoke.assert_not_called()
    assert "safety.py:" in caplog.text
    assert "precheck" in caplog.text


def test_unsafe_generated_code_is_a_different_category():
    result = test_agent.test_implementation(state("import os\ndef login(): os.system('blocked')"), model())
    assert result["test_failure"]["error_category"] == "unsafe_generated_code"


def test_model_valueerror_has_safe_diagnostics_without_payloads(monkeypatch, caplog):
    # Include unlabelled values as well: regex-based key redaction is insufficient.
    values = ["eyJhbGciOiJIUzI1NiJ9.credential.signature", "glpat-test-credential-do-not-log",
              "fixture-fernet-key-do-not-log", "private-password", "unlabelled-env-value"]
    for name, value in zip(("JWT_SECRET_KEY", "GITLAB_TOKEN", "FERNET_KEY", "PASSWORD", "OTHER_SETTING"), values):
        monkeypatch.setenv(name, value)
    llm = model()
    llm.invoke.side_effect = ValueError("model request failed: " + " ".join(values))
    result = test_agent.test_implementation(state(), llm)
    assert result["test_failure"]["error_category"] == "model_invocation_failure"
    assert result["test_failure"]["stage"] == "model_invocation"
    assert "ValueError" in caplog.text
    assert "sanitized_message=" in caplog.text
    assert "Traceback" in caplog.text and "invoke_model" in caplog.text
    for value in values:
        assert value not in caplog.text + json.dumps(result)


@pytest.mark.parametrize("content", [None, 42, "", "not valid Python ?", '{"status":"tests"}', [{"type":"image","data":"private"}]])
def test_malformed_model_output_is_bounded_and_classified(content):
    llm = model(content)
    result = test_agent.test_implementation(state(), llm)
    assert result["test_failure"]["error_category"] == "malformed_model_output"
    assert result["test_failure"]["stage"] == "model_output"
    assert llm.invoke.call_count == 3


def test_structural_errors_are_not_model_errors():
    llm = model("def test_no_implementation(): assert True")
    result = test_agent.test_implementation(state(), llm)
    assert result["test_failure"]["error_category"] == "structurally_invalid_tests"
    assert result["test_failure"]["stage"] == "test_validation"
    assert llm.invoke.call_count == 3


def test_ambiguous_jwt_request_does_not_invent_or_execute_tests(monkeypatch):
    llm = model('{"status":"clarification_required"}')
    runner = Mock()
    monkeypatch.setattr(test_agent, "run_tests", runner)
    result = test_agent.test_implementation(state(analysis=""), llm)
    assert result["test_failure"]["error_category"] == "ambiguous_specification"
    assert not result["test_passed"]
    assert "credential rules" in result["test_result"]
    runner.assert_not_called()
    llm.invoke.assert_called_once()


def test_pytest_setup_error_is_not_implementation_failure():
    result = test_agent.test_implementation(state(), model(TESTS.replace(
        "def test_valid_credentials_issue_expected_claims():", "def test_valid_credentials_issue_expected_claims(nonexistent_fixture):")))
    assert result["test_failure"]["error_category"] == "pytest_execution_failure"
    assert result["test_failure"]["stage"] == "pytest_execution"


def test_pytest_startup_error_logs_safe_internal_trace(monkeypatch, caplog):
    from workflow import safety
    monkeypatch.setattr(safety.subprocess, "Popen", Mock(side_effect=OSError("private-password")))
    result = test_agent.test_implementation(state(), model())
    assert result["test_failure"]["error_category"] == "pytest_execution_failure"
    assert "OSError" in caplog.text and "safety.py:" in caplog.text
    assert "private-password" not in caplog.text + json.dumps(result)


def test_malformed_source_diagnostics_do_not_include_source_line(caplog):
    result = test_agent.test_implementation(state('secret = "private-password" ???'), model())
    assert result["test_failure"]["error_code"] == "invalid_python_source"
    assert "SyntaxError" in caplog.text
    assert "private-password" not in caplog.text + json.dumps(result)


def test_repair_does_not_reintroduce_a_prohibited_import():
    llm = model()
    llm.invoke.side_effect = [SimpleNamespace(content="import subprocess\n" + TESTS), SimpleNamespace(content=TESTS)]
    result = test_agent.test_implementation(state(), llm)
    assert result["test_passed"]
    assert llm.invoke.call_count == 2


def test_run_result_distinguishes_call_setup_and_assertion_errors():
    source = "def f(x): return x*3"
    failed = run_tests(source, "from generated_feature import f\ndef test_behavior(): assert f(4) == 13", detailed=True)
    assert failed.failure_category == "implementation_failure"
    invalid = run_tests(source, "from generated_feature import f\ndef test_behavior(): assert f(undefined) == 12", detailed=True)
    assert invalid.failure_category == "pytest_execution_failure"


def test_timeout_has_its_own_safe_failure_code(monkeypatch):
    original_runner = test_agent.run_tests
    monkeypatch.setattr(test_agent, "run_tests", lambda source, tests, **kwargs: original_runner(source, tests, timeout=0.5, **kwargs))
    source = "def f(x):\n    while True:\n        pass"
    tests = "from generated_feature import f\ndef test_behavior(): assert f(4) == 12"
    result = test_agent.test_implementation(state(source), model(tests))
    assert result["test_failure"]["error_category"] == "pytest_execution_failure"
    assert result["test_failure"]["error_code"] == "pytest_timeout"


def test_langgraph_preserves_structured_jwt_failure(monkeypatch):
    import uuid
    from workflow.graph import graph
    from workflow import nodes
    wrong = SOURCE.replace('if not hmac.compare_digest(digest, record["digest"]):', 'if False:')
    llm = model()
    llm.invoke.side_effect = [SimpleNamespace(content=json.dumps({"analysis": ANALYSIS,
        "branch_name": "feature/jwt-login", "commit_message": "Add JWT login", "mr_title": "JWT login"})),
        SimpleNamespace(content=wrong)]
    monkeypatch.setattr(nodes, "llm1", llm)
    monkeypatch.setattr(nodes, "test_llm", model())
    monkeypatch.setattr(nodes, "search_merge_requests", lambda query, project: [])
    thread = str(uuid.uuid4())
    result = graph.invoke({"user_request": REQUEST, "username": "fixture-user", "gitlab_project_id": 11,
        "gitlab_default_branch": "main", "gitlab_clone_url": "https://gitlab.com/fixture/project.git",
        "thread_id": thread, "target_file": "generated_feature.py"}, config={"configurable": {"thread_id": thread}})
    assert not result["test_passed"]
    assert result["test_failure"]["stage"] == "implementation_verification"
    assert result["test_failure"]["error_category"] == "implementation_failure"
    assert not result.get("__interrupt__")  # Failing tests cannot reach approval or Git writes.


def test_skipped_tests_do_not_count_as_passing():
    tests = "from pytest import skip\nfrom generated_feature import f\ndef test_value():\n    skip('not verified')\n    assert f(1) == 3"
    result = run_tests("def f(x): return x*3", tests, detailed=True)
    assert result.return_code != 0
    assert result.failure_category == "pytest_execution_failure"
