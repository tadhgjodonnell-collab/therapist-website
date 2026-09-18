import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).parent / "fixtures"))

from _chrome import page

from iacp_leads import classify as C
from iacp_leads.config import Config
from iacp_leads.extract import extract_profile
from iacp_leads.pipeline import build_leads, find_boilerplate_hosts

CFG = Config()

# A link that sits INSIDE the profile body on every page - selector-based
# chrome stripping cannot catch this one, only frequency can.
SHARED_BODY_LINK = '<p><a href="https://www.iacp-ethics-partner.com/code">Our code of ethics</a></p>'


def make_profile(i: int, extra: str = "") -> object:
    html = page(f"Therapist {i}", f"""
    <article class="therapist">
      <h1>Therapist {i}</h1>
      <p class="location">Bray, Co. Wicklow</p>
      <p><a href="mailto:t{i}@example.ie">email</a></p>
      {SHARED_BODY_LINK}
      {extra}
    </article>""")
    return extract_profile(html, f"https://www.iacp.ie/therapists/t{i}", CFG)


class TestBoilerplate(unittest.TestCase):
    def test_a_link_repeated_across_profiles_is_treated_as_chrome(self):
        profiles = [make_profile(i) for i in range(12)]
        # Before subtraction it looks like every therapist has a website.
        self.assertTrue(all(any(l.kind == C.WEBSITE for l in p.links) for p in profiles))
        hosts = find_boilerplate_hosts(profiles)
        self.assertIn("www.iacp-ethics-partner.com", hosts)

        leads = build_leads(profiles, CFG, verbose=False)
        self.assertTrue(all(l.verdict.verdict == C.NO_WEB_PRESENCE for l in leads))
        self.assertTrue(all(l.dropped_boilerplate for l in leads))

    def test_a_genuine_site_on_one_profile_survives_subtraction(self):
        profiles = [make_profile(i) for i in range(12)]
        profiles.append(make_profile(99, '<a href="https://www.realtherapist.ie">my site</a>'))
        leads = build_leads(profiles, CFG, verbose=False)
        by_url = {l.profile.url: l for l in leads}
        special = by_url["https://www.iacp.ie/therapists/t99"]
        self.assertEqual(special.verdict.verdict, C.HAS_WEBSITE)
        self.assertEqual(special.verdict.website, "https://www.realtherapist.ie")

    def test_subtraction_is_off_for_small_samples(self):
        """With 5 profiles we cannot distinguish chrome from coincidence."""
        profiles = [make_profile(i) for i in range(5)]
        self.assertEqual(find_boilerplate_hosts(profiles), set())

    def test_leads_are_sorted_best_first(self):
        profiles = [make_profile(i) for i in range(12)]
        profiles.append(make_profile(99, '<a href="https://www.realtherapist.ie">site</a>'))
        leads = build_leads(profiles, CFG, verbose=False)
        scores = [l.verdict.score for l in leads]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual(leads[-1].verdict.verdict, C.HAS_WEBSITE)


if __name__ == "__main__":
    unittest.main()
