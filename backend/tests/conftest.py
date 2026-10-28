import os
import tempfile

# The API reads settings at import time: point it at a throwaway database first.
_tmp = tempfile.mkdtemp(prefix="pathtopro-test-")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp}/test.db")
os.environ.setdefault("PATHTOPRO_SCHEDULER", "off")
os.environ.setdefault("PATHTOPRO_LLM", "off")
os.environ.setdefault("PATHTOPRO_MAIL", "memory")  # emails land in api.services.notify.SENT
os.environ.setdefault("PATHTOPRO_LLM_CACHE", f"{_tmp}/llm_cache")
