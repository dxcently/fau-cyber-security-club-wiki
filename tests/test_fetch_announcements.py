import unittest

from loadscript import load

fetch_announcements = load("fetch-announcements.py")
clean = fetch_announcements.clean


class TestClean(unittest.TestCase):
    def test_strips_everyone_and_here_pings(self):
        self.assertEqual(clean("@everyone meeting moved to 6pm"), "meeting moved to 6pm")
        self.assertEqual(clean("@here anyone free now?"), "anyone free now?")

    def test_strips_mention_tokens(self):
        self.assertEqual(clean("check <#123456789>"), "check")
        self.assertEqual(clean("ping <@123456789>"), "ping")
        self.assertEqual(clean("ping <@!123456789>"), "ping")
        self.assertEqual(clean("hey <@&123456789>"), "hey")

    def test_custom_emoji_becomes_shortcode(self):
        self.assertEqual(clean("nice job <:pepehacker:123456789>"), "nice job :pepehacker:")
        self.assertEqual(clean("nice job <a:pepehacker:123456789>"), "nice job :pepehacker:")

    def test_markdown_markers_removed_but_text_survives(self):
        self.assertEqual(clean("**bold**"), "bold")
        self.assertEqual(clean("__underline__"), "underline")
        self.assertEqual(clean("~~strike~~"), "strike")
        self.assertEqual(clean("`code`"), "code")
        self.assertEqual(clean("**bold** and __underline__ and ~~strike~~ and `code`"),
                          "bold and underline and strike and code")

    def test_headings_and_quotes_stripped(self):
        self.assertEqual(clean("# Heading"), "Heading")
        self.assertEqual(clean("## Heading"), "Heading")
        self.assertEqual(clean("### Heading"), "Heading")
        self.assertEqual(clean("> quoted line"), "quoted line")

    def test_collapses_whitespace(self):
        self.assertEqual(clean("a    b\t\tc"), "a b c")
        self.assertEqual(clean("a\n\n\n\n\nb"), "a\n\nb")

    def test_ping_only_message_collapses_to_empty(self):
        self.assertEqual(clean("@everyone"), "")
        self.assertEqual(clean("@everyone <@123456789> <#123456789>"), "")

    def test_unicode_emoji_are_not_stripped(self):
        self.assertEqual(clean("🚨 job posting 📢"), "🚨 job posting 📢")
        self.assertEqual(clean("🎓 congrats grads 👀"), "🎓 congrats grads 👀")

    def test_markdown_link_becomes_label_then_bare_url(self):
        self.assertEqual(
            clean("[Wade Thomas](https://www.linkedin.com/in/wadethomas/)"),
            "Wade Thomas https://www.linkedin.com/in/wadethomas/",
        )

    def test_markdown_link_inline_with_other_text(self):
        self.assertEqual(
            clean("Apply through [our site](https://example.com/jobs/42) today."),
            "Apply through our site https://example.com/jobs/42 today.",
        )

    def test_bold_markdown_link_loses_both_markers(self):
        self.assertEqual(
            clean("**[Apply here](https://example.com/apply)**"),
            "Apply here https://example.com/apply",
        )


if __name__ == "__main__":
    unittest.main()
