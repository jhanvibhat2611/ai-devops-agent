import os

# Never use developer credentials or their database in automated tests.
os.environ["JWT_SECRET_KEY"] = "isolated-test-signing-key-32-bytes-minimum"
os.environ["OLLAMA_AI_MODEL"] = "test-model"
os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
