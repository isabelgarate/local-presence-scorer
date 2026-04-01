"""Unit tests for the Instagram resolver."""

import pytest
import respx
import httpx

from local_scorer.resolvers.instagram_resolver import InstagramResolver


@pytest.fixture
def resolver() -> InstagramResolver:
    return InstagramResolver()


class TestTier1GoogleData:
    def test_finds_instagram_url(self, resolver):
        data = {"websiteUri": "https://instagram.com/mycafe"}
        handle, conf = resolver._from_google_data(data), 1.0
        assert handle == "mycafe"

    def test_finds_in_social_links(self, resolver):
        data = {
            "socialMediaLinks": [
                {"uri": "https://www.instagram.com/mycafe_madrid/"}
            ]
        }
        handle = resolver._from_google_data(data)
        assert handle == "mycafe_madrid"

    def test_ignores_non_instagram_urls(self, resolver):
        data = {"websiteUri": "https://www.facebook.com/mycafe"}
        handle = resolver._from_google_data(data)
        assert handle is None


class TestTier2WebsiteScrape:
    def test_extracts_from_anchor_tag(self, resolver):
        html = '<html><body><a href="https://instagram.com/elrestaurante">Follow us</a></body></html>'
        handle = resolver._extract_from_html(html)
        assert handle == "elrestaurante"

    def test_extracts_from_json_ld(self, resolver):
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Restaurant", "sameAs": ["https://instagram.com/elrestaurante_madrid"]}
        </script>
        </head></html>
        """
        handle = resolver._extract_from_html(html)
        assert handle == "elrestaurante_madrid"

    def test_rejects_non_handle_paths(self, resolver):
        html = '<a href="https://instagram.com/explore/tags/food">Food</a>'
        handle = resolver._extract_from_html(html)
        # "explore" should be rejected
        assert handle is None

    def test_no_instagram_link(self, resolver):
        html = "<html><body><p>No social links here</p></body></html>"
        handle = resolver._extract_from_html(html)
        assert handle is None


class TestTier3Heuristic:
    def test_simple_name(self, resolver):
        handle = resolver._from_name("El Restaurante")
        assert handle == "el.restaurante"

    def test_name_with_special_chars(self, resolver):
        handle = resolver._from_name("Café Gijón")
        # Accents stripped, normalized
        assert handle is not None
        assert len(handle) >= 3

    def test_short_name_skipped(self, resolver):
        handle = resolver._from_name("Yo")
        assert handle is None


class TestCleanHandle:
    def test_strips_trailing_slash(self, resolver):
        assert resolver._clean_handle("mycafe/") == "mycafe"

    def test_strips_query_params(self, resolver):
        assert resolver._clean_handle("mycafe?ref=bio") == "mycafe"

    def test_rejects_known_paths(self, resolver):
        assert resolver._clean_handle("explore") is None
        assert resolver._clean_handle("reel") is None
        assert resolver._clean_handle("p") is None
