"""Exercises the linkify regex inside layouts/partials/board-feed.html.

Pulls the pattern straight out of the template's `replaceRE` call instead of
keeping a hand-copied twin here, so this test tracks the live regex rather
than drifting from it. Hugo's `replaceRE` runs on RE2; the pattern here uses
only alternation and character classes (no lookaround, no backreferences),
which Python's `re` accepts identically, so compiling it directly is safe.

These cases cover the escape-then-wrap reasoning from the board-feed.html
comment: a query-string `&` (escaped to `&amp;`) must stay inside the href,
while a literal `<`, `>` or `"` next to a URL (escaped to `&lt;`, `&gt;`,
`&quot;`/`&#34;`) must not be swallowed into it, and trailing sentence
punctuation must not end up inside the href either.
"""
import html
import re
import unittest
from pathlib import Path

PARTIAL = Path(__file__).resolve().parent.parent / "layouts" / "partials" / "board-feed.html"


def _extract_pattern():
    text = PARTIAL.read_text(encoding="utf-8")
    m = re.search(r"replaceRE `(.+?)` `<a", text)
    if not m:
        raise AssertionError("could not find the linkify replaceRE pattern in board-feed.html")
    return m.group(1)


LINKIFY_RE = re.compile(_extract_pattern())


def linkify(raw):
    """What the template does at render time: escape, then wrap URL tokens."""
    escaped = html.escape(raw, quote=True)
    return LINKIFY_RE.sub(lambda m: f'<a href="{m.group(1)}" rel="external">{m.group(1)}</a>', escaped)


class TestLinkify(unittest.TestCase):
    def test_query_string_ampersand_stays_inside_the_href(self):
        out = linkify("See https://example.com/x?a=1&b=2 next.")
        self.assertIn('href="https://example.com/x?a=1&amp;b=2"', out)
        self.assertTrue(out.endswith(" next."))

    def test_angle_bracket_after_a_url_is_not_swallowed(self):
        out = linkify("Bracket <https://example.com/job> text.")
        self.assertIn('<a href="https://example.com/job" rel="external">https://example.com/job</a>', out)
        self.assertIn("&lt;<a", out)
        self.assertIn("</a>&gt;", out)

    def test_quote_after_a_url_is_not_swallowed(self):
        out = linkify('Quoted "https://example.com/job" text.')
        self.assertIn('<a href="https://example.com/job" rel="external">https://example.com/job</a>', out)

    def test_trailing_sentence_punctuation_excluded(self):
        cases = {
            "Apply at https://example.com/job.": "https://example.com/job",
            "See https://example.com/job, then.": "https://example.com/job",
            "List https://example.com/job; more.": "https://example.com/job",
            "Note https://example.com/job: info.": "https://example.com/job",
            "Ready https://example.com/job! go.": "https://example.com/job",
            "Ready https://example.com/job? go.": "https://example.com/job",
            "Link (https://example.com/job) here.": "https://example.com/job",
        }
        for raw, want in cases.items():
            out = linkify(raw)
            self.assertIn(f'href="{want}"', out, raw)

    def test_no_raw_markup_survives_escaping(self):
        out = linkify("<script>https://example.com/job</script>")
        self.assertNotIn("<script>", out)
        self.assertIn("&lt;script&gt;", out)


if __name__ == "__main__":
    unittest.main()
