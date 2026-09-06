+++
title = "Meta"
weight = 90
description = "How this wiki itself is built and maintained — authoring guide and the open TODO list."
icon = "fa-solid fa-gear"
homecard = false
+++

This section is about the wiki, not about security. If you want to write a
page, fix something, or see what is still unfinished, it starts here.

- [Authoring](/meta/authoring/) — how to write and submit a page, the
  shortcode reference, and how to make deeper changes to the site config.
- [Discord Sync](/meta/discord-sync/) — how the bot moves posts from
  Discord onto the board, for officers running #announcements and #jobs.
- [Logo & Brand](/meta/brand/) — the club owl mark in both forms, with
  downloads and usage rules.
- [TODO](/meta/todo/) — the running list of what has not been built yet.

---

## Who maintains this

Wiki upkeep and edits: **@dxcently** on the
[Discord](http://discord.gg/2Yun8WAUuy), or email **kho2025@fau.edu**. Ping them
if a page is wrong, a link is dead, or you want commit access.

For anything about the club itself rather than the wiki, contact details are
on the [home page](/).

---

## How this wiki is built

Two tools, and both are worth naming because the club teaches one of them.

**[Hugo](https://gohugo.io/)** turns the Markdown in `content/` into the
static HTML you are reading. No database, no server-side code, no build
pipeline beyond one command. That is deliberate: the whole site is plain text
in git, so anyone who can write Markdown can contribute, and the thing that
gets deployed is a folder of files.

**[Claude Code](https://github.com/anthropics/claude-code)** is being used to
build and restructure it — the theme work, the layout partials, the SVG owl,
and a good deal of the prose. This is stated plainly rather than hidden,
because pretending otherwise would be dishonest and because the club has a
whole [section on agent harnesses](/learn/ai/harnesses-and-loops/) that this
is a live example of.

Two caveats that matter more than the tool choice:

- **Claude Code is not open source.** Its licence is proprietary. If you want
  a harness you can read and modify, the
  [harnesses page](/learn/ai/harnesses-and-loops/) lists MIT and Apache-2.0
  alternatives that do the same job.
- **A human is accountable for every page.** An agent wrote a lot of this and
  a person reviewed it. Where a claim has a source, it is linked; where a
  number could not be traced to a primary source, it was cut rather than
  guessed. If you find something wrong, that is a review failure, not an
  excuse — report it and it gets fixed.

---

## Reference

What this site is built on. You need these if you are editing the theme, the
config, or writing anything more involved than a plain page.

- [Hugo documentation](https://gohugo.io/documentation/) — the static site
  generator this wiki runs on.
- [Relearn theme documentation](https://mcshelby.github.io/hugo-theme-relearn/index.html)
  — shortcodes, front matter options, and theme config.
- [Markdown cheatsheet](https://github.com/im-luka/markdown-cheatsheet?tab=readme-ov-file#paragraph)
  — syntax reference if you are new to Markdown.

---

{{< section-grid >}}
