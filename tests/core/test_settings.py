from src.core.settings import AppSettings


def test_settings_default_to_bge_without_gemini_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("EMBEDDING_OUTPUT_DIMENSIONALITY", raising=False)

    settings = AppSettings.from_env()

    assert not hasattr(settings, "gemini_api_key")
    assert settings.embedding_model == "BAAI/bge-small-en-v1.5"
    assert settings.embedding_output_dimensionality == 384
