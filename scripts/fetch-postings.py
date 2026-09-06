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

A posting has no expiry unless its author sets one: a `deadline:` line
anywhere in the message, followed by a date (or a date range) in one of a
handful of formats — see DATE_FORMATS_WITH_YEAR and DATE_FORMATS_NO_YEAR
below. No `deadline:` line means no `expires` key at all, and the item
rides the board until it ages out of the channel or the 50-item cap. A
`deadline:` line that is present but unparseable also omits `expires`,
but — unlike a missing line — it prints a warning, since that is a
poster's typo the sync should surface rather than silently swallow.

When DISCORD_OFFICER_CHANNEL_ID is set, that same warning is also posted to
an officer channel — see build_items() and notify_officer_channel() — so
the typo gets found without an officer reading build logs. Dedup relies on
Discord's own message history instead of a state file: the sync reruns
from scratch every five minutes, so before posting, the officer channel's
own recent messages are checked for one already naming the offending
message id.

When DISCORD_OFFICER_ROLE_IDS is set to a comma-separated list of guild role
ids, a marker reaction only counts toward classify_markers() if at least one
of its reactors holds one of those roles — see build_item() and
_marker_counts(). A message's reactors and a reactor's guild roles are only
fetched when the message already carries a marker reaction, and each
reactor's roles are looked up once per run and cached (_member_roles()). A
failed lookup — a reactor who left the guild, a Discord hiccup — counts as
"holds no roles" rather than raising; the sync keeps going either way. When
the variable is unset or empty, any reactor counts, exactly as before this
existed.

The card's "Open ->" link is picked in order: an `apply:` line's URL, if
the author set one; else the first link in the message that isn't a known
personal-profile URL (see PROFILE_LINK_RES); else the first link outright;
else the Discord permalink. See apply_url() and pick_link().

Meant to run from the same dedicated checkout as fetch-announcements.py: it
commits and pushes, and rebases onto main first so a concurrent push does
not wedge it.
"""
import importlib.util
import json, os, re, subprocess, sys, urllib.parse, urllib.request
from datetime import datetime

API  = "https://discord.com/api/v10"
WANT = 50    # postings to publish
SCAN = 100   # Discord's per-request max; the whole channel fits one page
OUT  = "data/discord-postings.json"

BRIEFCASE      = "\U0001F4BC"  # 💼
GRADUATION_CAP = "\U0001F393"  # 🎓

LINK_RE = re.compile(r"https?://\S+")

# Author opt-in: an `apply:` line, anywhere in the raw message, whose value
# is itself an http(s) URL — same markdown tolerance as DEADLINE_LINE_RE
# below (`**apply:**`), matched before clean() strips it. If the text after
# the colon isn't a URL, this simply doesn't match and url selection falls
# through to the link-scanning rules in apply_url()'s caller.
APPLY_LINE_RE = re.compile(r"(?i)[*_]{0,2}apply[*_]{0,2}:[*_]{0,2}\s*(https?://\S+)")

# Trailing punctuation a URL picked out of prose shouldn't keep — the closing
# `.`/`,`/`)` of the sentence around it, not part of the link itself. Same
# set the board-feed.html linkify regex excludes from its final character;
# keep the two in sync. Balanced parentheses inside a URL (Wikipedia-style)
# are the same accepted edge case: a trailing `)` is always stripped.
TRAILING_URL_PUNCT = ".,;:!?)]\"'’”"

# Links that point at a person, not a job: not what "Open ->" should send a
# reader to. Small and explicit on purpose — grow this list as new patterns
# turn up instead of writing a general classifier.
PROFILE_LINK_RES = [
    re.compile(r"(?i)linkedin\.com/in/"),
]

# Author opt-in: a `deadline:` line, anywhere in the raw message, followed by
# a date or a date range. Tolerant of markdown emphasis around the keyword
# (`**deadline:**`) since this matches before clean() strips it. Captures the
# rest of the line — `.` does not span newlines without re.DOTALL, so this
# never reaches into the message body that follows.
DEADLINE_LINE_RE = re.compile(r"(?i)[*_]{0,2}deadline[*_]{0,2}:[*_]{0,2}\s*(.+)")

# A bare hyphen also separates the month/day/year of a numeric date
# (10-5-2026), so only a hyphen with space on both sides is treated as a
# range separator. En and em dashes never appear inside a single date, so
# they split a range even without surrounding space.
RANGE_SPLIT_RE = re.compile(r"(?i)\s+-\s+|–|—|\s+to\s+")

ORDINAL_RE = re.compile(r"(?i)\b(\d{1,2})(?:st|nd|rd|th)\b")

# Tried in order; the first one that matches the whole (trimmed) string wins.
# Numeric formats are US ordering (month first) — this is a Florida club.
DATE_FORMATS_WITH_YEAR = [
    "%Y-%m-%d",       # 2026-10-05
    "%m/%d/%Y",       # 10/05/2026
    "%m/%d/%y",       # 10/5/26
    "%m-%d-%Y",       # 10-5-2026
    "%B %d, %Y",      # October 5, 2026
    "%B %d %Y",       # October 5 2026
    "%b %d, %Y",      # Oct 5, 2026
    "%b %d %Y",       # Oct 5 2026
    "%d %B %Y",       # 5 October 2026
    "%d %b %Y",       # 5 Oct 2026
]

# Month-and-day with no year: resolves to the next occurrence on or after
# the message's own timestamp, never a past date.
DATE_FORMATS_NO_YEAR = [
    "%B %d",          # October 5
    "%b %d",          # Oct 5
]

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

def _marker_names(message):
    """The set of reaction emoji names on a message, marker or not."""
    return {r["emoji"]["name"] for r in message.get("reactions", []) if r.get("emoji")}

def classify_markers(is_job, is_internship, message_id):
    """The "job"/"internship"/None decision, given which markers count.

    Shared by classify() (any reactor counts) and build_item()'s
    DISCORD_OFFICER_ROLE_IDS path (only an officer's reactor counts) — the
    ambiguity rule is the same either way.
    """
    if is_job and is_internship:
        print(f"skip {message_id}: carries both job and internship markers", file=sys.stderr)
        return None
    if is_job:
        return "job"
    if is_internship:
        return "internship"
    return None

def classify(message):
    """Return "job", "internship", or None from a message's marker reactions."""
    names = _marker_names(message)
    return classify_markers(BRIEFCASE in names, GRADUATION_CAP in names, message.get("id"))

def _member_roles(guild, user_id, cache, api):
    """Cached set of role ids a guild member holds; any lookup failure means none.

    A 404 (the reactor left the guild) or any other error — rate limit,
    network hiccup — is indistinguishable here on purpose: either way there
    is no role to check, not an error worth stopping the sync for.
    """
    if user_id not in cache:
        try:
            cache[user_id] = set(api(f"/guilds/{guild}/members/{user_id}").get("roles", []))
        except Exception:
            cache[user_id] = set()
    return cache[user_id]

def _marker_counts(message, emoji, guild, channel, allowed_roles, member_cache, api):
    """True if a reactor of `emoji` on `message` holds one of `allowed_roles`.

    Only called for a marker already known to be present on the message —
    see build_item(). A failed reactors fetch is treated as no counting
    reactors on this message, printed once to stderr; the sync continues.
    """
    try:
        reactors = api(f"/channels/{channel}/messages/{message['id']}/reactions/{urllib.parse.quote(emoji, safe='')}")
    except Exception as e:
        print(f"reactors fetch failed for message {message.get('id')} marker {emoji!r}: {e}", file=sys.stderr)
        return False
    return any(_member_roles(guild, user["id"], member_cache, api) & allowed_roles for user in reactors)

def first_link(raw):
    """First http(s) link in the raw (uncleaned) message content, if any."""
    m = LINK_RE.search(raw)
    return m.group(0) if m else None

def _strip_trailing_url_punct(url):
    """Trim trailing sentence punctuation a regex match swept up with a URL."""
    return url.rstrip(TRAILING_URL_PUNCT)

def _is_profile_link(url):
    """True for a link that points at a person rather than a job posting."""
    return any(p.search(url) for p in PROFILE_LINK_RES)

def apply_url(raw):
    """The `apply:` line's URL, if the raw message has one — or None.

    The officer-facing opt-in: whoever posts can pin exactly which link the
    board's "Open ->" button should use, the same way `deadline:` pins the
    closing date.
    """
    m = APPLY_LINE_RE.search(raw)
    return _strip_trailing_url_punct(m.group(1)) if m else None

def pick_link(raw):
    """Best-guess http(s) link from the raw message body, or None.

    The first link whose host+path doesn't match a known personal-profile
    pattern (see PROFILE_LINK_RES) — falling back to the first link outright
    if every link found is a profile link. A message with no links at all
    returns None.
    """
    links = [_strip_trailing_url_punct(m.group(0)) for m in LINK_RE.finditer(raw)]
    for link in links:
        if not _is_profile_link(link):
            return link
    return links[0] if links else None

def _normalize_date_text(text):
    """Strip an ordinal suffix (`5th` -> `5`) and collapse whitespace."""
    return re.sub(r"\s+", " ", ORDINAL_RE.sub(r"\1", text.strip()))

def _try_formats(text, formats):
    """First successful `strptime` result among `formats`, or None."""
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None

def _resolve_year(dt, ref):
    """Attach the next occurrence of a year-less `dt` on or after `ref` — or None."""
    try:
        candidate = dt.replace(year=ref.year)
    except ValueError:
        return None   # e.g. Feb 29 outside a leap year
    if candidate.date() < ref.date():
        try:
            candidate = candidate.replace(year=ref.year + 1)
        except ValueError:
            return None
    return candidate.date()

def _parse_single_date(text, ref):
    """One date, in any accepted format, resolved against `ref` — or None.

    `ref` anchors a year-less month/day to its next occurrence: never a date
    before `ref` itself.
    """
    text = _normalize_date_text(text)
    dt = _try_formats(text, DATE_FORMATS_WITH_YEAR)
    if dt:
        return dt.date()
    dt = _try_formats(text, DATE_FORMATS_NO_YEAR)
    return _resolve_year(dt, ref) if dt else None

def _parse_range(start_text, end_text, ref):
    """A (start, end) date pair from the two sides of a range — or None.

    A year-less side borrows the other side's year rather than resolving
    independently: "March 30 to April 5, 2026" is one year, not two. Only
    when both sides omit the year do they fall back to `ref`, with the end
    resolved forward from the (now dated) start so the range can't invert.
    """
    start_text, end_text = _normalize_date_text(start_text), _normalize_date_text(end_text)
    start_dt = _try_formats(start_text, DATE_FORMATS_WITH_YEAR)
    end_dt = _try_formats(end_text, DATE_FORMATS_WITH_YEAR)
    if start_dt and end_dt:
        return start_dt.date(), end_dt.date()
    if start_dt and not end_dt:
        end_nd = _try_formats(end_text, DATE_FORMATS_NO_YEAR)
        end = _resolve_year(end_nd, start_dt) if end_nd else None
        return (start_dt.date(), end) if end else None
    if end_dt and not start_dt:
        start_nd = _try_formats(start_text, DATE_FORMATS_NO_YEAR)
        if not start_nd:
            return None
        try:
            start = start_nd.replace(year=end_dt.year).date()
        except ValueError:
            return None
        return start, end_dt.date()
    start_nd = _try_formats(start_text, DATE_FORMATS_NO_YEAR)
    start = _resolve_year(start_nd, ref) if start_nd else None
    if not start:
        return None
    end_nd = _try_formats(end_text, DATE_FORMATS_NO_YEAR)
    end = _resolve_year(end_nd, datetime.combine(start, datetime.min.time())) if end_nd else None
    return (start, end) if end else None

def deadline_fields(raw, ref):
    """Fields from a message's `deadline:` line, and the bad text if it failed to parse.

    Returns (fields, bad_text):
      - no `deadline:` line at all:            ({}, None) — nothing to warn about
      - line present, one date parses:         ({"expires": "YYYY-MM-DD"}, None)
      - line present, a range parses:          ({"starts": ..., "expires": ...}, None)
      - line present, nothing usable parses:   ({}, "<the text after the keyword>")

    `ref` is the message's own timestamp (a datetime), used to resolve a
    year-less date. Never raises: a human typed this in a chat client.
    """
    m = DEADLINE_LINE_RE.search(raw)
    if not m:
        return {}, None
    text = m.group(1).strip().rstrip("*_.,; \t")
    parts = RANGE_SPLIT_RE.split(text, maxsplit=1)
    if len(parts) == 2:
        result = _parse_range(parts[0], parts[1], ref)
        if result:
            starts, expires = result
            return {"starts": starts.isoformat(), "expires": expires.isoformat()}, None
    else:
        expires = _parse_single_date(text, ref)
        if expires:
            return {"expires": expires.isoformat()}, None
    return {}, text

def build_item(message, guild, channel, warnings=None, officer_role_ids=None, member_cache=None, api=None):
    """Build one data/discord-postings.json entry from a fetched message, or None to skip it.

    When `warnings` is given, an unparseable `deadline:` line also appends
    (message_id, author_id, bad_text) to it, for notify_officer_channel() —
    on top of the stderr print below, which always happens regardless.

    When `officer_role_ids` is a non-empty set, a marker only counts if one
    of its reactors holds one of those roles (see _marker_counts()) — `and`
    short-circuits so a marker absent from the message never triggers a
    reactors fetch. `member_cache` and `api` are required in that case; left
    unset (the default), behaviour is unchanged: any reactor counts.
    """
    if officer_role_ids:
        names = _marker_names(message)
        is_job = BRIEFCASE in names and _marker_counts(
            message, BRIEFCASE, guild, channel, officer_role_ids, member_cache, api)
        is_internship = GRADUATION_CAP in names and _marker_counts(
            message, GRADUATION_CAP, guild, channel, officer_role_ids, member_cache, api)
        kind = classify_markers(is_job, is_internship, message.get("id"))
    else:
        kind = classify(message)
    if kind is None:
        return None
    raw = message.get("content", "")
    url = (apply_url(raw) or pick_link(raw)
           or f"https://discord.com/channels/{guild}/{channel}/{message['id']}")
    fields, bad = deadline_fields(raw, datetime.fromisoformat(message["timestamp"]))
    if bad is not None:
        print(f"deadline unparseable in message {message.get('id')}: {bad!r}", file=sys.stderr)
        if warnings is not None:
            warnings.append((message["id"], message["author"]["id"], bad))
    return {
        "date": message["timestamp"],
        "kind": kind,
        "text": clean(raw),
        "url":  url,
        **fields,
    }

def format_warning(guild, jobs_channel, message_id, author_id, bad_text):
    """The plain-text officer-channel warning body for one unparseable `deadline:` line."""
    link = f"https://discord.com/channels/{guild}/{jobs_channel}/{message_id}"
    return (
        f"⚠️ Couldn't read the deadline on {link} by <@{author_id}>\n"
        f"It says: `{bad_text}`\n"
        "Write it as `deadline: 2026-10-05` (or a range: `deadline: 03/30/2026 - 04/05/2026`)"
    )

def notify_officer_channel(warnings, guild, jobs_channel, officer_channel, api):
    """Best-effort: POST one officer-channel warning per unparseable `deadline:` line.

    Dedup has no state file: the sync rebuilds from scratch every five minutes, so
    instead this fetches the officer channel's own last SCAN messages, keeps the ones
    authored by the bot itself (its own id from GET /users/@me), and skips any warning
    whose jobs-message id already appears in one of those. A dedup lookup or a post
    failure (403, rate limit, network error, malformed response) is caught and printed
    to stderr as one line — never raised, since a Discord hiccup here must never stop
    the board from publishing.
    """
    if not warnings:
        return
    try:
        bot_id = api("/users/@me")["id"]
        history = api(f"/channels/{officer_channel}/messages?limit={SCAN}")
    except Exception as e:
        print(f"officer channel: could not check warning history: {e}", file=sys.stderr)
        return
    already_posted = [m.get("content", "") for m in history
                       if m.get("author", {}).get("id") == bot_id]
    for message_id, author_id, bad_text in warnings:
        if any(message_id in content for content in already_posted):
            continue
        body = format_warning(guild, jobs_channel, message_id, author_id, bad_text)
        payload = json.dumps({
            "content": body,
            "allowed_mentions": {"parse": [], "users": [author_id]},
        }).encode()
        try:
            api(f"/channels/{officer_channel}/messages", payload)
        except Exception as e:
            print(f"officer channel: could not post warning for {message_id}: {e}", file=sys.stderr)

def build_items(jobs_channel, officer_channel, api, officer_role_ids=None):
    """Fetch #jobs, build the postings list, and (best-effort) flag bad deadlines.

    `api` is injected so tests can stub Discord out entirely. `officer_channel` may be
    None or empty — meaning DISCORD_OFFICER_CHANNEL_ID is unset — in which case no
    officer-channel call is made at all, and behaviour is exactly what it was before
    that feature existed. `officer_role_ids`, likewise, may be None or empty — meaning
    DISCORD_OFFICER_ROLE_IDS is unset — for the same reason. `member_cache` lives here,
    not in build_item(), so a reactor's guild roles are looked up once for the whole run
    even when they reacted on more than one message.
    """
    guild = api(f"/channels/{jobs_channel}")["guild_id"]
    messages = api(f"/channels/{jobs_channel}/messages?limit={SCAN}")
    warnings = []
    member_cache = {}
    items = [i for i in (build_item(m, guild, jobs_channel, warnings, officer_role_ids, member_cache, api)
                          for m in messages) if i]
    items.sort(key=lambda i: i["date"], reverse=True)
    del items[WANT:]
    if officer_channel:
        notify_officer_channel(warnings, guild, jobs_channel, officer_channel, api)
    return items

def main():
    token            = os.environ.get("DISCORD_BOT_TOKEN")
    channel          = os.environ.get("DISCORD_JOBS_CHANNEL_ID")
    officer_channel  = os.environ.get("DISCORD_OFFICER_CHANNEL_ID")
    officer_role_ids = {r.strip() for r in os.environ.get("DISCORD_OFFICER_ROLE_IDS", "").split(",") if r.strip()}
    if not (token and channel):
        sys.exit("DISCORD_BOT_TOKEN and DISCORD_JOBS_CHANNEL_ID must be set")

    def api(path, data=None):
        req = urllib.request.Request(API + path, data=data, headers={
            "Authorization": f"Bot {token}",
            # Discord's edge 403s the default Python-urllib UA; their API wants a
            # descriptive one.
            "User-Agent": "fau-csc-postings (+https://fau-cyber-wiki-test.necoconeco.net, 1.0)",
            **({"Content-Type": "application/json"} if data else {}),
        })
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)

    items = build_items(channel, officer_channel, api, officer_role_ids)

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
