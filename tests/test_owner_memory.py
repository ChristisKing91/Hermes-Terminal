"""Synthetic tests only; never contain real owner information."""
import os
import pytest
from hermes_terminal.owner_memory import MemoryError, OwnerMemoryStore


@pytest.fixture
def store(tmp_path):
    return OwnerMemoryStore(tmp_path / "private" / "owner-memory.sqlite")


def test_explicit_consent(store):
    with pytest.raises(MemoryError, match="consent"):
        store.remember(scope="devices", key="test_device", value="USB disk", provenance="owner", consent=False)
    assert store.list() == []


def test_store_reload_and_correction(store):
    one = store.remember(scope="devices", key="test_device", value="old", provenance="owner", consent=True)
    two = store.remember(scope="devices", key="test_device", value="corrected", provenance="owner", consent=True)
    assert one["revision"] == 1 and two["revision"] == 2
    reopened = OwnerMemoryStore(store.path)
    assert reopened.get(scope="devices", key="test_device")["value"] == "corrected"
    assert len(reopened.list()) == 1


def test_search_is_literal_and_scope_limited(store):
    store.remember(scope="projects", key="demo", value="one_percent% test", provenance="owner", consent=True)
    assert len(store.search("percent%")) == 1
    assert store.search("not_found") == []
    assert len(store.list(scope="projects")) == 1


def test_forget_erases_value_and_keeps_noncontent_event(store):
    store.remember(scope="preferences", key="test_pref", value="example", provenance="owner", consent=True)
    assert store.forget(scope="preferences", key="test_pref") is True
    assert store.get(scope="preferences", key="test_pref") is None
    assert store.forget(scope="preferences", key="test_pref") is False
    with store._connect() as db:
        rows = list(db.execute("SELECT * FROM change_log"))
    assert len(rows) == 2
    assert all("example" not in str(tuple(row)) for row in rows)


def test_reject_untrusted_keys_and_values(store):
    for key in ("../escape", "", "test/device", "UPPER"):
        with pytest.raises(MemoryError):
            store.remember(scope="owner", key=key, value="x", provenance="owner", consent=True)
    with pytest.raises(MemoryError):
        store.remember(scope="other_person", key="ok", value="x", provenance="owner", consent=True)
    with pytest.raises(MemoryError):
        store.remember(scope="owner", key="ok", value="", provenance="owner", consent=True)


def test_private_permissions(store):
    if os.name == "posix":
        assert store.path.stat().st_mode & 0o077 == 0
        assert store.path.parent.stat().st_mode & 0o077 == 0


def test_no_symlink_database(tmp_path):
    target = tmp_path / "real.sqlite"
    target.touch()
    link = tmp_path / "alias.sqlite"
    link.symlink_to(target)
    with pytest.raises(MemoryError):
        OwnerMemoryStore(link)
