import os
import tempfile

os.environ["OPS_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")
# Empty (not unset) so api/.env can't inject real credentials: tests never call paid APIs.
for var in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "OPENAI_API_KEY"):
    os.environ[var] = ""
os.environ["PRIVATE_LLM_BASE_URL"] = "http://127.0.0.1:9/v1"
