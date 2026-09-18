import csv
import pathlib
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from iacp_leads.cli import main

FIX = pathlib.Path(__file__).parent / "fixtures"


class TestEndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.pages = self.tmp / "pages"
        self.pages.mkdir()
        for html in FIX.glob("profile_*.html"):
            shutil.copy(html, self.pages / html.name)
        self.out = self.tmp / "leads.csv"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, *extra):
        code = main(["parse-dir", str(self.pages), "--out", str(self.out), *extra])
        self.assertEqual(code, 0)
        with self.out.open(encoding="utf-8-sig") as fh:
            return list(csv.DictReader(fh))

    def test_csv_has_a_row_per_profile_sorted_by_score(self):
        rows = self._run()
        self.assertEqual(len(rows), 6)
        scores = [int(r["score"]) for r in rows]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_verdicts_match_the_fixtures(self):
        verdicts = {r["name"]: r["verdict"] for r in self._run()}
        self.assertEqual(verdicts["Aoife Brennan"], "no_web_presence")
        self.assertEqual(verdicts["Declan Moore"], "social_only")
        # Marie has both a Calendly and a Psychology Today link. A directory
        # profile is the stronger presence of the two, so it wins the label.
        self.assertEqual(verdicts["Marie Dunne"], "directory_only")
        self.assertEqual(verdicts["Niamh Kelly"], "has_website")
        self.assertEqual(verdicts["Sean O Ruairc"], "has_website")
        self.assertEqual(verdicts["Tom Fitzgerald"], "builder_website")

    def test_prospects_only_drops_the_one_with_a_real_site(self):
        rows = self._run("--prospects-only")
        names = {r["name"] for r in rows}
        self.assertNotIn("Niamh Kelly", names)
        self.assertIn("Aoife Brennan", names)

    def test_contact_details_reach_the_csv(self):
        rows = {r["name"]: r for r in self._run()}
        self.assertEqual(rows["Declan Moore"]["email"], "declan.moore@example.ie")
        self.assertEqual(rows["Aoife Brennan"]["phone"], "0871234567")
        self.assertEqual(rows["Aoife Brennan"]["county"], "Clare")
        self.assertIn("facebook.com", rows["Declan Moore"]["social"])
        self.assertTrue(rows["Declan Moore"]["pitch"])


if __name__ == "__main__":
    unittest.main()
