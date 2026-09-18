import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from iacp_leads import classify as C
from iacp_leads.config import Config

CFG = Config()


def links(*pairs):
    return [C.classify_link(u, CFG) for u in pairs]


class TestClassifyLink(unittest.TestCase):
    def test_own_domain_is_a_website(self):
        self.assertEqual(C.classify_link("https://www.janedoe.ie", CFG).kind, C.WEBSITE)

    def test_builder_subdomain_is_a_site_but_the_vendor_is_not(self):
        self.assertEqual(C.classify_link("https://jane.wixsite.com/t", CFG).kind, C.BUILDER)
        self.assertEqual(C.classify_link("https://www.wix.com", CFG).kind, C.NOISE)
        # squarespace.com is noise, but a customer subdomain is a real site
        self.assertEqual(C.classify_link("https://jane.squarespace.com", CFG).kind, C.BUILDER)

    def test_known_categories(self):
        self.assertEqual(C.classify_link("https://facebook.com/x", CFG).kind, C.SOCIAL)
        self.assertEqual(C.classify_link("https://calendly.com/x", CFG).kind, C.BOOKING)
        self.assertEqual(C.classify_link("https://www.psychologytoday.com/ie/x", CFG).kind,
                         C.DIRECTORY)
        self.assertEqual(C.classify_link("https://www.iacp.ie/x", CFG).kind, C.SELF)

    def test_uk_style_domains_resolve_correctly(self):
        self.assertEqual(C.classify_link("https://www.counsellingdirectory.org.uk/a", CFG).kind,
                         C.DIRECTORY)


class TestVerdict(unittest.TestCase):
    def test_no_links_at_all_is_the_best_prospect(self):
        v = C.verdict_for([], "a@b.ie", "0871234567")
        self.assertEqual(v.verdict, C.NO_WEB_PRESENCE)
        self.assertEqual(v.score, 125)

    def test_uncontactable_prospect_is_demoted(self):
        v = C.verdict_for([], "", "")
        self.assertEqual(v.verdict, C.NO_WEB_PRESENCE)
        self.assertEqual(v.score, 70)
        self.assertIn("no contact details on profile", v.reasons)

    def test_social_only(self):
        v = C.verdict_for(links("https://facebook.com/x"), "a@b.ie", "")
        self.assertEqual(v.verdict, C.SOCIAL_ONLY)
        self.assertEqual(v.website, "")

    def test_booking_only_beats_directory_only_but_loses_to_social(self):
        booking = C.verdict_for(links("https://calendly.com/x"), "", "0871234567")
        directory = C.verdict_for(links("https://www.psychologytoday.com/ie/x"), "", "0871234567")
        self.assertEqual(booking.verdict, C.BOOKING_ONLY)
        self.assertEqual(directory.verdict, C.DIRECTORY_ONLY)
        self.assertGreater(booking.score, directory.score)

    def test_having_a_website_ends_the_pitch(self):
        v = C.verdict_for(links("https://www.janedoe.ie", "https://facebook.com/x"),
                          "a@b.ie", "0871234567")
        self.assertEqual(v.verdict, C.HAS_WEBSITE)
        self.assertEqual(v.score, 0)
        self.assertEqual(v.website, "https://www.janedoe.ie")

    def test_a_website_that_does_not_load_is_a_strong_prospect(self):
        site = "https://www.janedoe.ie"
        v = C.verdict_for(links(site), "a@b.ie", "", dead_websites={site})
        self.assertEqual(v.verdict, C.DEAD_WEBSITE)
        self.assertEqual(v.website, site)

    def test_builder_site_is_a_weaker_upgrade_prospect(self):
        v = C.verdict_for(links("https://jane.wixsite.com/t"), "a@b.ie", "")
        self.assertEqual(v.verdict, C.BUILDER_WEBSITE)
        self.assertIn(v.verdict, C.PROSPECT_VERDICTS)
        self.assertLess(v.score, C.verdict_for([], "a@b.ie", "").score)


if __name__ == "__main__":
    unittest.main()
