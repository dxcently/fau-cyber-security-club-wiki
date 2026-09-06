#!/usr/bin/env python3
"""Sync the club Discord's newest announcements into the wiki.

Reads DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID from the environment — never from
the repo. Pulls the channel's recent messages, keeps the newest few that carry
text, softens Discord-only artifacts (@everyone/@here pings, raw mention and
custom-emoji tokens) into text that reads on a public page, and writes
data/announcements.json in the {date, author, text, url} shape the home panel
renders. Commits as the bot and pushes to main only when the result changed, so
an unchanged channel produces no commit.

Meant to run from a dedicated checkout (see the systemd unit): it commits and
pushes, and rebases onto main first so a concurrent push does not wedge it.
"""
import json, os, re, subprocess, sys, urllib.request

API  = "https://discord.com/api/v10"
WANT = 10    # announcements to publish
SCAN = 100   # Discord's per-request max; scan enough to always find WANT text posts
OUT  = "data/announcements.json"

def clean(t):
    t = re.sub(r"@(everyone|here)\b", "", t)          # drop pings
    t = re.sub(r"<#\d+>|<@&\d+>|<@!?\d+>", "", t)      # channel / role / user mentions
    t = re.sub(r"<a?:(\w+):\d+>", r":\1:", t)          # custom emoji -> :name:
    # Discord markdown that would show as literal punctuation on the panel
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t, flags=re.S)  # **bold**
    t = re.sub(r"__(.+?)__", r"\1", t, flags=re.S)          # __underline__
    t = re.sub(r"~~(.+?)~~", r"\1", t, flags=re.S)          # ~~strike~~
    t = re.sub(r"`([^`]+)`", r"\1", t)                       # `code`
    t = re.sub(r"(?m)^\s{0,3}#{1,3}\s+", "", t)            # # headings
    t = re.sub(r"(?m)^\s{0,3}>\s?", "", t)                 # > quotes
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()

def main():
    token   = os.environ.get("DISCORD_BOT_TOKEN")
    channel = os.environ.get("DISCORD_CHANNEL_ID")
    if not (token and channel):
        sys.exit("DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID must be set")

    def api(path):
        req = urllib.request.Request(API + path, headers={
            "Authorization": f"Bot {token}",
            # Discord's edge 403s the default Python-urllib UA; their API wants a
            # descriptive one.
            "User-Agent": "fau-csc-announcements (+https://fau-cyber-wiki-test.necoconeco.net, 1.0)",
        })
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)

    guild = api(f"/channels/{channel}")["guild_id"]
    items = []
    for m in api(f"/channels/{channel}/messages?limit={SCAN}"):   # newest first
        if m.get("type") not in (0, 19):                          # skip system messages
            continue
        text = clean(m.get("content", ""))
        if not text:                                              # skip image-only / empty
            continue
        a = m["author"]
        items.append({
            "date":   m["timestamp"],
            "author": a.get("global_name") or a["username"],
            "text":   text,
            "url":    f"https://discord.com/channels/{guild}/{channel}/{m['id']}",
        })
        if len(items) >= WANT:
            break

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
    subprocess.run(["git", *ident, "commit", "-q", "-m", "announcements: sync from Discord"], check=True)
    subprocess.run(["git", "pull", "--rebase", "--quiet", "origin", "main"], check=True)
    subprocess.run(["git", *push, "push", "-q", "origin", "HEAD:main"], check=True)
    print(f"published {len(items)} announcement(s)")

if __name__ == "__main__":
    main()
