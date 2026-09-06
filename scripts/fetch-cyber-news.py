#!/usr/bin/env python3
"""Sync recent security headlines into the wiki.

Same shape as fetch-announcements.py: pull three feeds, keep the newest
PER_SOURCE from each so a chatty feed cannot crowd out a slow one, write
data/cyber-news.json in the {date, source, title, url} shape the board-feed
shortcode renders, commit as the bot, push to main only when the result
changed. Runs from the same dedicated checkout, on a six-hour timer.

Headlines and links only — no article bodies are copied.
"""
import json, os, subprocess, sys, urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

FEEDS = {
    "The Hacker News":   "https://feeds.feedburner.com/TheHackersNews",
    "Krebs on Security": "https://krebsonsecurity.com/feed/",
    "BleepingComputer":  "https://www.bleepingcomputer.com/feed/",
}
PER_SOURCE = 3          # 3 feeds x 3 = 9 headlines on the page
OUT  = "data/cyber-news.json"

def fetch(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "fau-csc-cyber-news (+https://fau-cyber-wiki-test.necoconeco.net, 1.0)",
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        return ET.fromstring(r.read())

def parse_feed(root, source):
    """Pull the newest PER_SOURCE items out of a parsed RSS <channel> root."""
    got = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link  = (it.findtext("link") or "").strip()
        pub   = it.findtext("pubDate")
        if not (title and link and pub):
            continue
        got.append({
            "date":   parsedate_to_datetime(pub).isoformat(),
            "source": source,
            "title":  title,
            "url":    link,
        })
    got.sort(key=lambda i: i["date"], reverse=True)
    return got[:PER_SOURCE]

def main():
    items = []
    for source, url in FEEDS.items():
        try:
            root = fetch(url)
        except Exception as e:                # one dead feed must not empty the page
            print(f"skip {source}: {e}", file=sys.stderr)
            continue
        items += parse_feed(root, source)

    items.sort(key=lambda i: i["date"], reverse=True)

    new = json.dumps(items, indent=2, ensure_ascii=False) + "\n"
    old = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
    if new == old:
        print("unchanged")
        sys.exit(0)

    if "--dry-run" in sys.argv:
        print(new)
        sys.exit(0)

    open(OUT, "w", encoding="utf-8").write(new)

    ident = ["-c", "user.name=csc-announcements-bot",
             "-c", "user.email=csc-announcements-bot@users.noreply.github.com"]
    push  = ["-c", "credential.helper=!gh auth git-credential"]
    subprocess.run(["git", "add", OUT], check=True)
    subprocess.run(["git", *ident, "commit", "-q", "-m", "cyber-news: sync from RSS"], check=True)
    subprocess.run(["git", "pull", "--rebase", "--quiet", "origin", "main"], check=True)
    subprocess.run(["git", *push, "push", "-q", "origin", "HEAD:main"], check=True)
    print(f"published {len(items)} headline(s)")

if __name__ == "__main__":
    main()
