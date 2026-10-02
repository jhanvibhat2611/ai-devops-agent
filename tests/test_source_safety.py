import pytest

from workflow.safety import precheck, run_tests, UnsafeCodeError


@pytest.mark.parametrize("source", [
    "import os", 'import os\nKEY = os.getenv("KEY")',
    'import os\nKEY = os.environ.get("KEY", "fixture")',
    'import os as config\nKEY = config.getenv("KEY")',
    'from os import getenv as read\nKEY = read("KEY")',
    'from os import environ as config\nKEY = config.get("KEY")',
])
def test_configuration_reads_allowed(source):
    precheck(source)


@pytest.mark.parametrize("source", [
    "import os\nos.system('blocked')", "import os\nos.popen('blocked')",
    "import os\nos.spawnv(0, 'blocked', [])", "import os\nos.remove('file')",
    "import os\nos.open('file', 0)", "import os\nos.listdir('.')",
    "import os\nother = os", "import os\nother = os.environ",
    "import os\nother = os.getenv", "import os\nos.environ['KEY'] = 'value'",
    "import os\nos.environ.update({})", "from os import system as run",
    "import os.path", "from os import *",
    "import os\ngetattr(os, 'system')('blocked')",
    "import subprocess\nsubprocess.run(['blocked'])",
    "import socket\nsocket.socket()", "import requests\nrequests.get('https://example.invalid')",
    "import urllib.request", "import http.client", "import httpx",
    "open('file', 'w')", "import pathlib\npathlib.Path('file').read_text()",
    "eval('1')", "exec('pass')", "__import__('os')", "(1).__class__",
])
def test_dangerous_capabilities_blocked(source):
    with pytest.raises(UnsafeCodeError):
        precheck(source)


def test_allowed_config_reads_cannot_see_parent_secrets(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "fixture-parent-secret")
    source = '''import os
def configuration():
    return (os.getenv("JWT_SECRET_KEY"), os.environ.get("JWT_SECRET_KEY", "missing"))
'''
    tests = '''from generated_feature import configuration
def test_environment():
    assert configuration() == (None, "missing")
'''
    result = run_tests(source, tests, detailed=True)
    assert result.return_code == 0
    assert result.test_count == 1
