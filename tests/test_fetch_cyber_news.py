import unittest
import xml.etree.ElementTree as ET

from loadscript import load

fetch_cyber_news = load("fetch-cyber-news.py")
parse_feed = fetch_cyber_news.parse_feed
PER_SOURCE = fetch_cyber_news.PER_SOURCE

RSS_TEMPLATE = """<rss><channel>
{items}
</channel></rss>"""

ITEM_TEMPLATE = """<item>
  <title>{title}</title>
  <link>{link}</link>
  <pubDate>{pub_date}</pubDate>
</item>"""


def feed(*items):
    return ET.fromstring(RSS_TEMPLATE.format(items="\n".join(items)))


class TestParseFeed(unittest.TestCase):
    def test_extracts_title_link_and_iso_date(self):
        root = feed(ITEM_TEMPLATE.format(
            title="Big breach disclosed",
            link="https://example.com/a",
            pub_date="Mon, 01 Jan 2024 12:00:00 GMT",
        ))
        got = parse_feed(root, "The Hacker News")
        self.assertEqual(len(got), 1)
        item = got[0]
        self.assertEqual(item["title"], "Big breach disclosed")
        self.assertEqual(item["url"], "https://example.com/a")
        self.assertEqual(item["source"], "The Hacker News")
        self.assertTrue(item["date"].startswith("2024-01-01"))

    def test_skips_items_missing_required_fields(self):
        root = feed(
            ITEM_TEMPLATE.format(title="", link="https://example.com/a", pub_date="Mon, 01 Jan 2024 12:00:00 GMT"),
            ITEM_TEMPLATE.format(title="No link", link="", pub_date="Mon, 01 Jan 2024 12:00:00 GMT"),
            "<item><title>No pubDate</title><link>https://example.com/b</link></item>",
        )
        self.assertEqual(parse_feed(root, "BleepingComputer"), [])

    def test_sorted_newest_first_and_truncated_to_per_source(self):
        items = [
            ITEM_TEMPLATE.format(title=f"Story {i}", link=f"https://example.com/{i}",
                                  pub_date=f"Mon, {i:02d} Jan 2024 12:00:00 GMT")
            for i in range(1, PER_SOURCE + 3)
        ]
        root = feed(*items)
        got = parse_feed(root, "Krebs on Security")
        self.assertEqual(len(got), PER_SOURCE)
        titles = [i["title"] for i in got]
        self.assertEqual(titles, sorted(titles, reverse=True))


if __name__ == "__main__":
    unittest.main()
