import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from iacp_leads import discover as D
from iacp_leads.config import Config

CFG = Config()
FIX = pathlib.Path(__file__).parent / "fixtures"
LISTING_URL = "https://www.iacp.ie/therapists"


class TestDiscover(unittest.TestCase):
    def setUp(self):
        self.html = (FIX / "listing.html").read_text(encoding="utf-8")
        self.links = D._page_links(self.html, LISTING_URL, CFG)

    def test_only_same_site_links_are_collected(self):
        self.assertTrue(all("iacp.ie" in l for l in self.links))
        self.assertNotIn("https://www.facebook.com/IACPdot.ie", self.links)

    def test_configured_patterns_find_the_profiles(self):
        matched = [l for l in self.links if D._matches_any(l, CFG.profile_url_patterns)]
        self.assertEqual(len(matched), 6)
        self.assertIn("https://www.iacp.ie/therapists/aoife-brennan", matched)

    def test_pagination_link_is_recognised_and_not_a_profile(self):
        nxt = "https://www.iacp.ie/therapists?page=2"
        self.assertIn(nxt, self.links)
        self.assertTrue(D._matches_any(nxt, CFG.pagination_url_patterns))
        self.assertFalse(D._matches_any(nxt, CFG.profile_url_patterns))

    def test_autodetect_works_when_patterns_are_wrong(self):
        """The fallback is what makes this survive a site redesign."""
        shape, members = D.autodetect_shape(self.links)
        self.assertEqual(shape, "/therapists/*")
        self.assertEqual(len(members), 6)

    def test_autodetect_ignores_section_pages(self):
        urls = ["https://www.iacp.ie/about", "https://www.iacp.ie/news",
                "https://www.iacp.ie/privacy"]
        self.assertEqual(D.autodetect_shape(urls), (None, []))

    def test_autodetect_handles_query_string_profiles(self):
        urls = [f"https://www.iacp.ie/profile.aspx?id={i}" for i in range(8)]
        shape, members = D.autodetect_shape(urls)
        self.assertEqual(shape, "/profile.aspx?id=*")
        self.assertEqual(len(members), 8)

    def test_assets_are_skipped(self):
        links = D._page_links(
            '<a href="/x/a.pdf">pdf</a><a href="/therapists/jane-doe">j</a>',
            LISTING_URL, CFG)
        self.assertEqual(links, ["https://www.iacp.ie/therapists/jane-doe"])


if __name__ == "__main__":
    unittest.main()
