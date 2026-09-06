#!/usr/bin/env python3
"""Publish reaction-marked Discord posts from #jobs to the Jobs & Internships board.

Reads DISCORD_BOT_TOKEN and DISCORD_JOBS_CHANNEL_ID from the environment —
never from the repo. Pulls the #jobs channel's recent messages and keeps
only the ones marked with a briefcase (💼 -> job) or graduation cap
(🎓 -> internship) reaction. A message carrying both markers is skipped —
an ambiguous mark is a human mistake, not something to guess at — and one
carrying neither is not published. Reuses clean() from
fetch-announcements.py instead of reimplementing its regexes.

Writes data/discord-postings.json, rebuilt in full from the channel on
every run: this is deliberate, since removing a marker reaction in Discord
must unpublish the item on the next run. The hand-edited data/postings.toml
is a separate file this script never writes to; the two are merged only at
render time by the board-feed partial.

Meant to run from the same dedicated checkout as fetch-announcements.py: it
commits and pushes, and rebases onto main first so a concurrent push does
not wedge it.
"""
import importlib.util
import json, os, re, subprocess, sys, urllib.request
from datetime import datetime, timedelta

API  = "https://discord.com/api/v10"
SCAN = 100   # Discord's per-request max; the whole channel fits one page
OUT  = "data/discord-postings.json"

BRIEFCASE      = "\U0001F4BC"  # 💼
GRADUATION_CAP = "\U0001F393"  # 🎓

LINK_RE = re.compile(r"https?://\S+")

def _load_sibling(name):
    """Import a hyphenated sibling script under scripts/ without copying it.

    Hyphens rule out a normal `import`, and fetch-announcements.py's
    network/git side effects sit behind `if __name__ == "__main__":`, so
    this only defines its functions.
    """
    path = os.path.join(os.path.dirname(__file__), name)
    spec = importlib.util.spec_from_file_location(name.replace("-", "_").removesuffix(".py"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

clean = _load_sibling("fetch-announcements.py").clean

def classify(message):
    """Return "job", "internship", or None from a message's marker reactions."""
    names = {r["emoji"]["name"] for r in message.get("reactions", []) if r.get("emoji")}
    is_job         = BRIEFCASE in names
    is_internship  = GRADUATION_CAP in names
    if is_job and is_internship:
        print(f"skip {message.get('id')}: carries both job and internship markers", file=sys.stderr)
        return None
    if is_job:
        return "job"
    if is_internship:
        return "internship"
    return None

def first_link(raw):
    """First http(s) link in the raw (uncleaned) message content, if any."""
    m = LINK_RE.search(raw)
    return m.group(0) if m else None

def expires_for(timestamp):
    """Message timestamp + 30 days, formatted YYYY-MM-DD."""
    return (datetime.fromisoformat(timestamp) + timedelta(days=30)).strftime("%Y-%m-%d")

def build_item(message, guild, channel):
    """Build one data/discord-postings.json entry from a fetched message, or None to skip it."""
    kind = classify(message)
    if kind is None:
        return None
    raw = message.get("content", "")
    url = first_link(raw) or f"https://discord.com/channels/{guild}/{channel}/{message['id']}"
    return {
        "date":    message["timestamp"],
        "kind":    kind,
        "text":    clean(raw),
        "url":     url,
        "expires": expires_for(message["timestamp"]),
    }

def main():
    token   = os.environ.get("DISCORD_BOT_TOKEN")
    channel = os.environ.get("DISCORD_JOBS_CHANNEL_ID")
    if not (token and channel):
        sys.exit("DISCORD_BOT_TOKEN and DISCORD_JOBS_CHANNEL_ID must be set")

    def api(path):
        req = urllib.request.Request(API + path, headers={
            "Authorization": f"Bot {token}",
            # Discord's edge 403s the default Python-urllib UA; their API wants a
            # descriptive one.
            "User-Agent": "fau-csc-postings (+https://fau-cyber-wiki-test.necoconeco.net, 1.0)",
        })
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)

    guild = api(f"/channels/{channel}")["guild_id"]
    messages = api(f"/channels/{channel}/messages?limit={SCAN}")
    items = [i for i in (build_item(m, guild, channel) for m in messages) if i]
    items.sort(key=lambda i: i["date"], reverse=True)

    new = json.dumps(items, indent=2, ensure_ascii=False) + "\n"
    old = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
    if new == old:
        print("unchanged")
        sys.exit(0)

    if "--dry-run" in sys.argv:            # preview the JSON, touch nothing
        print(new)
        sys.exit(0)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write(new)

    ident = ["-c", "user.name=csc-announcements-bot",
             "-c", "user.email=csc-announcements-bot@users.noreply.github.com"]
    push  = ["-c", "credential.helper=!gh auth git-credential"]
    subprocess.run(["git", "add", OUT], check=True)
    subprocess.run(["git", *ident, "commit", "-q", "-m", "postings: sync from Discord"], check=True)
    subprocess.run(["git", "pull", "--rebase", "--quiet", "origin", "main"], check=True)
    subprocess.run(["git", *push, "push", "-q", "origin", "HEAD:main"], check=True)
    print(f"published {len(items)} posting(s)")

if __name__ == "__main__":
    main()
