import pytest

from configs import name_replacer
from configs.name_replacer import replace_name


def mock_substitutes(monkeypatch, mapping):
    monkeypatch.setattr(name_replacer, "_load_team_substitutes", lambda: mapping)


class TestReplaceName:
    def test_known_team_returns_canonical_name(self, monkeypatch):
        mock_substitutes(monkeypatch, {"Arsenal": ["arsenal", "AFC"]})

        assert replace_name("arsenal") == "Arsenal"

    def test_variant_name_returns_canonical_name(self, monkeypatch):
        mock_substitutes(monkeypatch, {"Bayern": ["FCB", "bayern"]})

        assert replace_name("FCB") == "Bayern"

    def test_unknown_team_raises_value_error(self, monkeypatch):
        mock_substitutes(monkeypatch, {"Arsenal": ["arsenal"]})

        with pytest.raises(ValueError):
            replace_name("Hamburg")

    def test_error_message_mentions_team(self, monkeypatch):
        mock_substitutes(monkeypatch, {"Arsenal": ["arsenal"]})

        with pytest.raises(ValueError, match="Hamburg"):
            replace_name("Hamburg")

    def test_empty_mapping_raises_value_error(self, monkeypatch):
        mock_substitutes(monkeypatch, {})

        with pytest.raises(ValueError):
            replace_name("Arsenal")
