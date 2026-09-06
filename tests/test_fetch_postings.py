import io
import sys
import unittest
from contextlib import redirect_stderr
from datetime import datetime

from loadscript import load

fetch_postings   = load("fetch-postings.py")
classify         = fetch_postings.classify
first_link       = fetch_postings.first_link
deadline_fields  = fetch_postings.deadline_fields
build_item       = fetch_postings.build_item

GUILD   = "555000111222333444"
CHANNEL = "666000111222333444"

BRIEFCASE      = "\U0001F4BC"
GRADUATION_CAP = "\U0001F393"

REF = datetime.fromisoformat("2026-08-01T15:04:23.512000+00:00")


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


class TestDeadlineFieldsNoLine(unittest.TestCase):
    def test_no_deadline_line_yields_no_fields(self):
        fields, bad = deadline_fields("Apply whenever, no rush.", REF)
        self.assertEqual(fields, {})
        self.assertIsNone(bad)

    def test_synonym_keyword_not_accepted(self):
        fields, bad = deadline_fields("closes: 2026-09-05", REF)
        self.assertEqual(fields, {})
        self.assertIsNone(bad)


class TestDeadlineFieldsSingleDate(unittest.TestCase):
    def test_iso_date(self):
        fields, bad = deadline_fields("deadline: 2026-10-05", REF)
        self.assertEqual(fields, {"expires": "2026-10-05"})
        self.assertIsNone(bad)

    def test_us_slash_date_with_four_digit_year(self):
        fields, _ = deadline_fields("deadline: 10/05/2026", REF)
        self.assertEqual(fields, {"expires": "2026-10-05"})

    def test_us_slash_date_with_two_digit_year(self):
        fields, _ = deadline_fields("deadline: 10/5/26", REF)
        self.assertEqual(fields, {"expires": "2026-10-05"})

    def test_us_dash_date(self):
        fields, _ = deadline_fields("deadline: 10-5-2026", REF)
        self.assertEqual(fields, {"expires": "2026-10-05"})

    def test_written_out_date_with_comma(self):
        fields, _ = deadline_fields("deadline: October 5, 2026", REF)
        self.assertEqual(fields, {"expires": "2026-10-05"})

    def test_abbreviated_month_no_comma(self):
        fields, _ = deadline_fields("deadline: Oct 5 2026", REF)
        self.assertEqual(fields, {"expires": "2026-10-05"})

    def test_ordinal_suffix(self):
        fields, bad = deadline_fields("deadline: Oct 5th", REF)
        self.assertEqual(fields, {"expires": "2026-10-05"})
        self.assertIsNone(bad)

    def test_day_first_written_date(self):
        fields, _ = deadline_fields("deadline: 5 October 2026", REF)
        self.assertEqual(fields, {"expires": "2026-10-05"})

    def test_bold_markdown_keyword_still_matches(self):
        fields, _ = deadline_fields("**deadline:** 2026-10-05", REF)
        self.assertEqual(fields, {"expires": "2026-10-05"})

    def test_case_insensitive_keyword(self):
        fields, _ = deadline_fields("DEADLINE: 2026-09-05", REF)
        self.assertEqual(fields, {"expires": "2026-09-05"})

    def test_deadline_line_anywhere_in_body(self):
        raw = "Hey everyone, cool internship!\n\ndeadline: 2026-09-05\n\nApply on our site."
        fields, _ = deadline_fields(raw, REF)
        self.assertEqual(fields, {"expires": "2026-09-05"})

    def test_no_starts_key_for_a_single_date(self):
        fields, _ = deadline_fields("deadline: 2026-10-05", REF)
        self.assertNotIn("starts", fields)


class TestDeadlineFieldsYearlessDate(unittest.TestCase):
    def test_month_day_after_ref_resolves_to_current_year(self):
        # REF is 2026-08-01; Nov 1 hasn't happened yet this year.
        fields, _ = deadline_fields("deadline: Nov 1", REF)
        self.assertEqual(fields, {"expires": "2026-11-01"})

    def test_month_day_before_ref_resolves_to_next_year(self):
        # REF is 2026-08-01; Jan 1 already passed this year.
        fields, _ = deadline_fields("deadline: Jan 1", REF)
        self.assertEqual(fields, {"expires": "2027-01-01"})


class TestDeadlineFieldsRange(unittest.TestCase):
    def test_hyphen_separator(self):
        fields, bad = deadline_fields("deadline: 03/30/2026 - 04/05/2026", REF)
        self.assertEqual(fields, {"starts": "2026-03-30", "expires": "2026-04-05"})
        self.assertIsNone(bad)

    def test_to_separator_with_written_dates(self):
        fields, bad = deadline_fields("deadline: March 30 to April 5, 2026", REF)
        self.assertEqual(fields, {"starts": "2026-03-30", "expires": "2026-04-05"})
        self.assertIsNone(bad)

    def test_en_dash_separator(self):
        fields, _ = deadline_fields("deadline: March 30 – April 5, 2026", REF)
        self.assertEqual(fields, {"starts": "2026-03-30", "expires": "2026-04-05"})

    def test_em_dash_separator(self):
        fields, _ = deadline_fields("deadline: March 30 — April 5, 2026", REF)
        self.assertEqual(fields, {"starts": "2026-03-30", "expires": "2026-04-05"})

    def test_year_on_end_only_applies_to_both_sides(self):
        # Without this, a naive year-less resolve would push "March 30" (a
        # date already past REF this year) into 2027 while "April 5, 2026"
        # stayed put, splitting the range across two different years.
        fields, _ = deadline_fields("deadline: March 30 to April 5, 2026", REF)
        self.assertEqual(fields["starts"][:4], fields["expires"][:4])

    def test_numeric_dash_dates_do_not_get_split_mid_date(self):
        fields, bad = deadline_fields("deadline: 10-5-2026", REF)
        self.assertNotIn("starts", fields)
        self.assertEqual(fields, {"expires": "2026-10-05"})
        self.assertIsNone(bad)


class TestDeadlineFieldsMalformed(unittest.TestCase):
    def test_unrecognized_text_yields_no_expires(self):
        fields, bad = deadline_fields("deadline: whenever works", REF)
        self.assertEqual(fields, {})
        self.assertIsNotNone(bad)

    def test_impossible_calendar_date_yields_no_expires(self):
        fields, bad = deadline_fields("deadline: 2026-13-45", REF)
        self.assertEqual(fields, {})
        self.assertIsNotNone(bad)

    def test_non_iso_numeric_with_wrong_field_count_is_malformed(self):
        fields, bad = deadline_fields("deadline: 2026/40/99", REF)
        self.assertEqual(fields, {})
        self.assertIsNotNone(bad)


class TestBuildItemDeadlineWarnings(unittest.TestCase):
    def _run(self, content, timestamp="2026-08-01T15:04:23.512000+00:00"):
        m = message(content, reactions=[reaction(BRIEFCASE)], timestamp=timestamp)
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            item = build_item(m, GUILD, CHANNEL)
        return item, stderr.getvalue()

    def test_no_deadline_line_does_not_warn(self):
        item, err = self._run("Hiring now, apply on our site.")
        self.assertNotIn("expires", item)
        self.assertEqual(err, "")

    def test_malformed_deadline_warns_and_omits_expires(self):
        item, err = self._run("Hiring now.\ndeadline: sometime soon")
        self.assertNotIn("expires", item)
        self.assertIn("1111122222333334444", err)
        self.assertIn("sometime soon", err)

    def test_valid_deadline_does_not_warn(self):
        item, err = self._run("Hiring now.\ndeadline: 2026-10-05")
        self.assertEqual(item["expires"], "2026-10-05")
        self.assertEqual(err, "")


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
        self.assertNotIn("expires", item)
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

    def test_range_deadline_sets_starts_and_expires(self):
        m = message(
            "Career fair booth sign-ups.\ndeadline: 03/30/2026 - 04/05/2026",
            reactions=[reaction(BRIEFCASE)],
        )
        item = build_item(m, GUILD, CHANNEL)
        self.assertEqual(item["starts"], "2026-03-30")
        self.assertEqual(item["expires"], "2026-04-05")


if __name__ == "__main__":
    unittest.main()
