import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from iacp_leads import classify as C
from iacp_leads.config import Config
from iacp_leads.extract import extract_profile

FIX = pathlib.Path(__file__).parent / "fixtures"
CFG = Config()


def load(name, url="https://www.iacp.ie/therapists/x"):
    return extract_profile((FIX / name).read_text(encoding="utf-8"), url, CFG)


class TestExtract(unittest.TestCase):
    def test_name_county_and_phone(self):
        p = load("profile_no_website.html")
        self.assertEqual(p.name, "Aoife Brennan")
        self.assertEqual(p.county, "Clare")
        self.assertEqual(p.phone, "0871234567")
        self.assertEqual(p.email, "")

    def test_international_phone_is_normalised(self):
        p = load("profile_social_only.html")
        self.assertEqual(p.phone, "0667123456")
        self.assertEqual(p.email, "declan.moore@example.ie")

    def test_site_chrome_is_not_treated_as_the_therapists_links(self):
        """The IACP header/footer must never leak into a therapist's links."""
        p = load("profile_no_website.html")
        hosts = {l.host for l in p.links}
        self.assertNotIn("www.facebook.com", hosts)
        self.assertNotIn("www.hse.ie", hosts)
        self.assertEqual(p.links, [])

    def test_website_link_is_found(self):
        p = load("profile_has_website.html")
        sites = [l for l in p.links if l.kind == C.WEBSITE]
        self.assertEqual([l.host for l in sites], ["www.niamhkellytherapy.ie"])

    def test_website_written_as_plain_text_is_found(self):
        p = load("profile_text_domain.html")
        sites = [l for l in p.links if l.kind == C.WEBSITE]
        self.assertEqual(len(sites), 1)
        self.assertIn("seanoruairc-counselling.ie", sites[0].url)

    def test_obfuscated_email_is_recovered(self):
        p = load("profile_text_domain.html")
        self.assertEqual(p.email, "sean@seanoruairc-counselling.ie")

    def test_social_links_are_kept_and_labelled(self):
        p = load("profile_social_only.html")
        kinds = sorted(l.kind for l in p.links)
        self.assertEqual(kinds, [C.SOCIAL, C.SOCIAL])


if __name__ == "__main__":
    unittest.main()
