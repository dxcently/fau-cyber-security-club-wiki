+++
title = "Discord Sync"
weight = 2
description = "How posts move from Discord onto the board, for officers — no code, just the rules."
icon = "fa-solid fa-robot"
+++

The board on this wiki is not edited by hand. A bot reads the club Discord
and writes the pages for you. Know the rules below and you can run the whole
thing from Discord — you never need to touch the wiki itself.

## Announcements

Everything posted in **#announcements** is picked up automatically. No
reaction, no keyword, nothing to do. The newest ten posts that have text show
up on the home page.

## Jobs & internships

Post in **#jobs** however you like. Then react to your own message with one
of two emoji:

- 💼 (briefcase) — publishes it as a job.
- 🎓 (graduation cap) — publishes it as an internship.

Nothing publishes without one of these two reactions. React with both and the
post is skipped — the bot cannot tell which board it belongs on, so it
publishes neither.

Remove the reaction later and the post drops off the board on the next sync.

## Setting a deadline

A closing date is optional. If you want one, add one line anywhere in the
message, in exactly this format:

```
deadline: 2026-10-15
```

This is the only format the bot understands: the word `deadline`, a colon,
then the date as `YYYY-MM-DD`. There is no other accepted wording — not
"closes," not "due," not a written-out date like "Oct 15" — and a line that
does not match this exactly is ignored. Leave the line out entirely and the
posting stays up for 30 days from the day you posted it.

## Fixing a mistake

Edit the Discord message, not the wiki. Every sync rebuilds the board from
the channel, so a wiki edit gets overwritten on the next run anyway. Fix the
typo, fix the date, fix the reaction — in Discord.

## Limits and timing

- The board shows the newest 50 postings. Older ones still exist in Discord,
  they just do not get a page.
- A sync runs every few minutes, so a post, a reaction, or an edit shows up
  on the wiki within about five minutes.

## The hand-edited list

Jobs and internships that never came through Discord — a flyer someone
emailed, a posting from before the bot existed — live in a hand-edited list
alongside the Discord ones. The Jobs & Internships page shows both lists
together, sorted newest first. If you need to add one of these by hand, ask
whoever maintains the wiki.
