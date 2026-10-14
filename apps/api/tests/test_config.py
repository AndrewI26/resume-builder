import pytest

from config import Settings


def make_settings(**overrides) -> Settings:
    required = {
        "node_env": "development",
        "postgres_user": "user",
        "postgres_password": "password",
        "postgres_db": "db",
        "postgres_port": 5432,
        "backend_port": 8000,
        "secret_key": "secret",
    }
    return Settings(_env_file=None, **{**required, **overrides})


class TestApiPathPrefix:
    def test_is_empty_when_the_api_is_reached_directly(self):
        assert make_settings().api_path_prefix == ""

    @pytest.mark.parametrize(
        "public_api_url", ["https://resume.example.com/api", "https://x.test/api/"]
    )
    def test_is_the_proxy_prefix_behind_a_reverse_proxy(self, public_api_url):
        settings = make_settings(public_api_url=public_api_url)

        assert settings.api_path_prefix == "/api"

    def test_is_empty_when_the_api_is_at_the_root_of_its_host(self):
        settings = make_settings(public_api_url="https://api.example.com")

        assert settings.api_path_prefix == ""
