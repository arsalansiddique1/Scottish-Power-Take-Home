from review_agent.settings import get_settings


def test_settings_defaults() -> None:
    settings = get_settings()
    assert settings.llm_model
    assert settings.llm_base_url.startswith("http")
