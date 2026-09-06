import unittest

from loadscript import load

fetch_postings = load("fetch-postings.py")
classify    = fetch_postings.classify
first_link  = fetch_postings.first_link
expires_for = fetch_postings.expires_for
build_item  = fetch_postings.build_item

GUILD   = "555000111222333444"
CHANNEL = "666000111222333444"

BRIEFCASE      = "\U0001F4BC"
GRADUATION_CAP = "\U0001F393"


def reaction(name, count=1):
    return {
        "emoji": {"id": None, "name": name},
        "count": count,
        "count_details": {"burst": 0, "normal": count},
        "burst_colors": [],
        "me_burst": False,
        "me": False,
    }


def message(content, reactions=(), message_id="1111122222333334444", timestamp="2026-08-01T15:04:23.512000+00:00"):
    """A message payload shaped like Discord's actual GET messages response."""
    return {
        "id": message_id,
        "type": 0,
        "content": content,
        "channel_id": CHANNEL,
        "author": {
            "id": "999000111222333444",
            "username": "recruiter_bot",
            "global_name": "Recruiter",
            "discriminator": "0",
            "avatar": None,
            "bot": True,
        },
        "timestamp": timestamp,
        "edited_timestamp": None,
        "tts": False,
        "mention_everyone": False,
        "mentions": [],
        "mention_roles": [],
        "attachments": [],
        "embeds": [],
        "reactions": list(reactions),
        "pinned": False,
        "flags": 0,
        "components": [],
    }


class TestClassify(unittest.TestCase):
    def test_briefcase_reaction_is_job(self):
        m = message("Hiring a SOC analyst.", reactions=[reaction(BRIEFCASE)])
        self.assertEqual(classify(m), "job")

    def test_graduation_cap_reaction_is_internship(self):
        m = message("Summer internship open.", reactions=[reaction(GRADUATION_CAP)])
        self.assertEqual(classify(m), "internship")

    def test_no_reactions_excluded(self):
        m = message("Just chatting, no marker here.", reactions=[])
        self.assertIsNone(classify(m))

    def test_unrelated_reaction_excluded(self):
        m = message("Nice meme.", reactions=[reaction("\U0001F44D")])  # 👍
        self.assertIsNone(classify(m))

    def test_both_markers_excluded(self):
        m = message("Is this a job or an internship?",
                     reactions=[reaction(BRIEFCASE), reaction(GRADUATION_CAP)])
        self.assertIsNone(classify(m))


class TestFirstLink(unittest.TestCase):
    def test_finds_first_http_or_https_link_in_raw_content(self):
        raw = "Apply here: https://example.com/careers/42 or http://example.org/backup"
        self.assertEqual(first_link(raw), "https://example.com/careers/42")

    def test_no_link_returns_none(self):
        self.assertIsNone(first_link("No link in this one, just apply in Discord."))


class TestExpiresFor(unittest.TestCase):
    def test_exactly_thirty_days_after_timestamp(self):
        self.assertEqual(expires_for("2026-08-01T15:04:23.512000+00:00"), "2026-08-31")

    def test_crosses_month_boundary(self):
        self.assertEqual(expires_for("2026-01-15T00:00:00.000000+00:00"), "2026-02-14")


class TestBuildItem(unittest.TestCase):
    def test_job_item_uses_raw_link_and_cleaned_text(self):
        m = message(
            "💼 **Hiring**: SOC analyst intern, apply at https://example.com/apply now @everyone",
            reactions=[reaction(BRIEFCASE)],
            timestamp="2026-08-01T15:04:23.512000+00:00",
        )
        item = build_item(m, GUILD, CHANNEL)
        self.assertEqual(item["kind"], "job")
        self.assertEqual(item["url"], "https://example.com/apply")
        self.assertEqual(item["date"], "2026-08-01T15:04:23.512000+00:00")
        self.assertEqual(item["expires"], "2026-08-31")
        self.assertNotIn("**", item["text"])
        self.assertNotIn("@everyone", item["text"])
        self.assertIn("💼", item["text"])

    def test_no_link_falls_back_to_permalink(self):
        m = message("🎓 Internship posting, DM me for details", reactions=[reaction(GRADUATION_CAP)],
                     message_id="777788889999000011")
        item = build_item(m, GUILD, CHANNEL)
        self.assertEqual(item["url"], f"https://discord.com/channels/{GUILD}/{CHANNEL}/777788889999000011")

    def test_message_with_neither_marker_is_not_built(self):
        m = message("Random chatter with no marker.", reactions=[])
        self.assertIsNone(build_item(m, GUILD, CHANNEL))

    def test_message_with_both_markers_is_not_built(self):
        m = message("Ambiguous post.", reactions=[reaction(BRIEFCASE), reaction(GRADUATION_CAP)])
        self.assertIsNone(build_item(m, GUILD, CHANNEL))

    def test_unicode_emoji_in_body_survive_cleaning(self):
        m = message("🚨 Job posting 📢 apply now 🎓", reactions=[reaction(BRIEFCASE)])
        item = build_item(m, GUILD, CHANNEL)
        self.assertIn("🚨", item["text"])
        self.assertIn("📢", item["text"])
        self.assertIn("🎓", item["text"])


if __name__ == "__main__":
    unittest.main()
