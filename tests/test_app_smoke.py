from pathlib import Path
from types import SimpleNamespace

import streamlit as st
from streamlit.testing.v1 import AppTest


class EmptyQuery:
    def select(self, *args, **kwargs):
        return self

    def order(self, *args, **kwargs):
        return self

    def range(self, *args, **kwargs):
        return self

    def execute(self):
        return SimpleNamespace(data=[])


class EmptyDatabase:
    def table(self, name):
        return EmptyQuery()


def test_app_renders_without_database_secrets_or_runtime_errors(monkeypatch):
    import supabase

    monkeypatch.setattr(
        supabase,
        "create_client",
        lambda url, key: EmptyDatabase(),
    )
    st.cache_resource.clear()

    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(str(app_path))
    app.secrets["SUPABASE_URL"] = "https://example.supabase.co"
    app.secrets["SUPABASE_KEY"] = "test-only-placeholder"

    app.run()

    assert not app.exception, [str(item.value) for item in app.exception]
    assert any("فراتر از شناخت" in item.value for item in app.title)
    rendered_text = " ".join(item.value for item in app.caption)
    assert "0.4.5" in rendered_text
    assert len(app.tabs) == 5
