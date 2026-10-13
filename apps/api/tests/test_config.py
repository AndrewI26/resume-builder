import pytest

from config import Settings


def local_settings(**overrides) -> Settings:
    # local mode needs nothing from the environment, so only the overrides count
    return Settings(mode="local", **overrides)


class TestApiPathPrefix:
    def test_is_empty_when_the_api_is_reached_directly(self):
        assert local_settings().api_path_prefix == ""

    @pytest.mark.parametrize(
        "public_api_url", ["https://resume.example.com/api", "https://x.test/api/"]
    )
    def test_is_the_proxy_prefix_behind_a_reverse_proxy(self, public_api_url):
        settings = local_settings(public_api_url=public_api_url)

        assert settings.api_path_prefix == "/api"

    def test_is_empty_when_the_api_is_at_the_root_of_its_host(self):
        settings = local_settings(public_api_url="https://api.example.com")

        assert settings.api_path_prefix == ""
