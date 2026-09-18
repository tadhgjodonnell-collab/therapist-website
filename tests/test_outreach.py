import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from iacp_leads import outreach as O

SENDER = O.Sender(name="Tadhg O'Donnell", email="t@example.ie",
                  phone="087 000 0000", price="€450")


def row(**kw):
    base = {"name": "Aoife Brennan", "town": "Ennis", "county": "Clare",
            "email": "aoife@example.ie", "phone": "0871234567",
            "verdict": "no_web_presence", "website": "", "social": "",
            "directories": ""}
    base.update(kw)
    return base


class TestDraft(unittest.TestCase):
    def test_uses_their_first_name_and_town(self):
        d = O.draft_for(row(), SENDER, "https://d.ie/aoife/")
        self.assertIn("Hi Aoife,", d.body)
        self.assertIn("Ennis", d.body)

    def test_titles_are_stripped_from_the_greeting(self):
        d = O.draft_for(row(name="Dr Niamh Kelly"), SENDER)
        self.assertIn("Hi Niamh,", d.body)

    def test_opening_differs_by_what_is_actually_missing(self):
        no_site = O.draft_for(row(), SENDER).body
        social = O.draft_for(row(verdict="social_only",
                                 social="https://facebook.com/x"), SENDER).body
        dead = O.draft_for(row(verdict="dead_website",
                               website="https://janedoe.ie"), SENDER)
        self.assertIn("no website on it", no_site)
        self.assertIn("Facebook page", social)
        self.assertIn("janedoe.ie", dead.body)
        self.assertIn("janedoe.ie", dead.subject)
        self.assertNotEqual(no_site, social)

    def test_every_draft_demands_a_line_of_your_own(self):
        for verdict in ("no_web_presence", "social_only", "directory_only",
                        "booking_only", "dead_website", "builder_website"):
            d = O.draft_for(row(verdict=verdict, website="https://x.wixsite.com/a"),
                            SENDER)
            self.assertTrue(d.unfinished, f"{verdict} draft has no [[ ]] slot")

    def test_it_says_where_the_details_came_from_and_how_to_opt_out(self):
        body = O.draft_for(row(), SENDER).body
        self.assertIn("iacp.ie", body)
        self.assertIn("no thanks", body)

    def test_the_demo_link_is_used_when_there_is_one(self):
        with_link = O.draft_for(row(), SENDER, "https://d.ie/aoife/").body
        without = O.draft_for(row(), SENDER).body
        self.assertIn("https://d.ie/aoife/", with_link)
        self.assertNotIn("https://d.ie/aoife/", without)
        self.assertIn("no charge", without)

    def test_no_email_becomes_a_phone_script_not_an_email(self):
        d = O.draft_for(row(email=""), SENDER)
        self.assertEqual(d.channel, "phone")
        self.assertIn("0871234567", d.body)
        self.assertIn("Don't ring twice", d.body)

    def test_price_and_one_off_framing_appear_once(self):
        body = O.draft_for(row(), SENDER).body
        self.assertIn("€450", body)
        self.assertIn("no monthly anything", body)


class TestWriteDrafts(unittest.TestCase):
    def test_writes_a_file_per_lead_plus_an_index(self):
        rows = [row(), row(name="Declan Moore", verdict="social_only",
                           social="https://facebook.com/d")]
        with tempfile.TemporaryDirectory() as tmp:
            drafts = O.write_drafts(rows, SENDER, tmp)
            files = sorted(p.name for p in pathlib.Path(tmp).iterdir())
            index = (pathlib.Path(tmp) / "index.md").read_text(encoding="utf-8")
        self.assertEqual(len(drafts), 2)
        self.assertEqual(files, ["001-aoife-brennan.md", "002-declan-moore.md",
                                 "index.md"])
        self.assertIn("Declan Moore", index)

    def test_each_file_carries_what_their_listing_says(self):
        rows = [row(specialisms="Anxiety and panic; Anger",
                    blurb="I have worked with adults for twelve years.",
                    profile_url="https://www.iacp.ie/therapists/a")]
        with tempfile.TemporaryDirectory() as tmp:
            O.write_drafts(rows, SENDER, tmp)
            text = (pathlib.Path(tmp) / "001-aoife-brennan.md").read_text(encoding="utf-8")
        self.assertIn("Their listing says", text)
        self.assertIn("Anxiety and panic", text)
        self.assertIn("twelve years", text)
        self.assertIn("https://www.iacp.ie/therapists/a", text)


if __name__ == "__main__":
    unittest.main()
