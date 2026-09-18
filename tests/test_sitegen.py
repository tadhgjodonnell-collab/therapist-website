import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from iacp_leads import sitegen as S


class TestRenderer(unittest.TestCase):
    def test_nested_section_with_the_same_name(self):
        """A list used as its own guard: the case a regex renderer gets wrong."""
        out = S.render("{{#xs}}<ul>{{#xs}}<li>{{.}}</li>{{/xs}}</ul>{{/xs}}",
                       {"xs": ["a"]})
        self.assertEqual(out, "<ul><li>a</li></ul>")

    def test_inverted_section(self):
        t = "{{#photo}}img{{/photo}}{{^photo}}placeholder{{/photo}}"
        self.assertEqual(S.render(t, {"photo": ""}), "placeholder")
        self.assertEqual(S.render(t, {"photo": "p.jpg"}), "img")

    def test_values_are_escaped_unless_asked_otherwise(self):
        self.assertEqual(S.render("{{a}}", {"a": '"<b>&'}), "&quot;&lt;b&gt;&amp;")
        self.assertEqual(S.render("{{&a}}", {"a": "<b>"}), "<b>")

    def test_mismatched_tags_are_reported_not_silently_wrong(self):
        with self.assertRaises(ValueError):
            S.render("{{#a}}x{{/b}}", {"a": 1})
        with self.assertRaises(ValueError):
            S.render("{{#a}}x", {"a": 1})

    def test_missing_keys_render_empty(self):
        self.assertEqual(S.render("[{{nope}}]", {}), "[]")


class TestPhoneFormatting(unittest.TestCase):
    def test_irish_formats(self):
        self.assertEqual(S.format_phone("0871234567"), "087 123 4567")
        self.assertEqual(S.format_phone("016611234"), "01 661 1234")
        self.assertEqual(S.format_phone(""), "")

    def test_tel_href_is_international(self):
        self.assertEqual(S._tel_href("0871234567"), "+353871234567")


class TestBuild(unittest.TestCase):
    def test_a_draft_site_builds_and_is_not_indexable(self):
        ctx = S.content_for("Aoife Brennan", town="Ennis", county="Clare",
                            phone="0871234567", email="a@example.ie")
        with tempfile.TemporaryDirectory() as tmp:
            page = S.build(ctx, tmp)
            html = pathlib.Path(page).read_text(encoding="utf-8")
        self.assertIn("noindex", html)
        self.assertIn("Draft preview for Aoife Brennan", html)
        self.assertIn("087 123 4567", html)
        self.assertIn("+353871234567", html)
        self.assertNotIn("{{", html)

    def test_a_live_site_drops_the_banner_and_is_indexable(self):
        ctx = S.content_for("Aoife Brennan", town="Ennis", county="Clare",
                            draft=False)
        with tempfile.TemporaryDirectory() as tmp:
            html = pathlib.Path(S.build(ctx, tmp)).read_text(encoding="utf-8")
        self.assertIn("index, follow", html)
        self.assertNotIn("Draft preview", html)

    def test_the_copy_avoids_the_words_that_give_a_template_away(self):
        ctx = S.content_for("Aoife Brennan", town="Ennis", county="Clare")
        with tempfile.TemporaryDirectory() as tmp:
            html = pathlib.Path(S.build(ctx, tmp)).read_text(encoding="utf-8").lower()
        for word in ("journey", "safe space", "empower", "holistic",
                     "thrive", "reach out", "unlock", "your best self"):
            self.assertNotIn(word, html, f"{word!r} is a giveaway phrase")

    def test_no_testimonials_section(self):
        """IACP ethics restrict soliciting client endorsements."""
        import re
        template = (S.SITE_DIR / "template.html").read_text(encoding="utf-8").lower()
        for pattern in (r"testimonial", r"what clients say", r"\breviews?\b",
                        r"client stories"):
            self.assertIsNone(re.search(pattern, template),
                              f"{pattern!r} should not appear in a therapist site")

    def test_crisis_signposting_is_present(self):
        ctx = S.content_for("A B", town="Ennis", county="Clare")
        with tempfile.TemporaryDirectory() as tmp:
            html = pathlib.Path(S.build(ctx, tmp)).read_text(encoding="utf-8")
        self.assertIn("116 123", html)
        self.assertIn("50808", html)

    def test_row_from_the_csv_drives_the_page(self):
        row = {"name": "Declan Moore", "town": "Tralee", "county": "Kerry",
               "email": "d@example.ie", "phone": "0667123456",
               "accreditation": "MIACP",
               "specialisms": "Anxiety and panic; Bereavement and loss"}
        ctx = S.content_for_row(row)
        self.assertEqual(ctx["helps_with"], ["Anxiety and panic", "Bereavement and loss"])
        self.assertEqual(ctx["credentials"], "MIACP")
        self.assertIn("Tralee", ctx["lead"])


if __name__ == "__main__":
    unittest.main()
