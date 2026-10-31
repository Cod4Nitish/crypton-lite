import os
import tempfile

import pytest

# Point the app at a throwaway DB + vector store before backend modules are imported.
_tmp = tempfile.mkdtemp()
os.environ["CRYPTON_DB"] = os.path.join(_tmp, "test.db")
os.environ["CRYPTON_CHROMA"] = os.path.join(_tmp, "chroma")

from backend import db, store  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    db.init_db()
    store.init_store()
    with db._conn() as c:
        for t in ("tasks", "runs", "pending_actions", "notes", "documents"):
            c.execute(f"DELETE FROM {t}")
    try:
        from backend import rag
        col = rag.collection()
        ids = col.get()["ids"]
        if ids:
            col.delete(ids=ids)
    except Exception:
        pass
    yield
