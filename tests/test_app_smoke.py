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


def test_app_requires_password_before_rendering_research_workspace(monkeypatch):
    import supabase

    monkeypatch.setattr(
        supabase,
        "create_client",
        lambda url, key: EmptyDatabase(),
    )
    st.cache_resource.clear()

    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(str(app_path))
    app.secrets["APP_PASSWORD"] = "test-password-only"
    app.secrets["SUPABASE_URL"] = "https://example.supabase.co"
    app.secrets["SUPABASE_KEY"] = "test-only-placeholder"

    app.run()
    assert not app.exception
    assert len(app.tabs) == 0
    assert len(app.text_input) == 1

    app.text_input[0].set_value("wrong-password")
    app.button[0].click().run()
    assert not app.exception
    assert len(app.tabs) == 0

    app.text_input[0].set_value("test-password-only")
    app.button[0].click().run()
    assert not app.exception, [str(item.value) for item in app.exception]
    assert len(app.tabs) == 5
    assert any("فراتر از شناخت" in item.value for item in app.title)
