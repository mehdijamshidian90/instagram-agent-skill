#!/usr/bin/env python3
"""
caption.py - lint an Instagram caption and show exactly what the feed shows
before the "... more".

Instagram gives a caption about 125 characters in the feed and hides the rest
behind a tap. Almost every caption that fails, fails there: the hook is in
sentence three, or the first line is a greeting, or the whole thing opens on a
hashtag. This prints the visible window as a box so you can read it the way a
scrolling stranger does, then checks the eight things that are worth checking.

The 125-character cut is an approximation. The real number moves with the
device, the font size and where your line breaks fall, which is exactly why
you want a margin rather than a caption engineered to end at 125. Change it
with --truncate if you want to test a tighter one.

Persian (Farsi) captions get three extra checks, because they fail in ways an
English caption cannot:
  - DIRECTION   Instagram sets each line's direction from its first strong
                character. A Persian line that starts with an English word
                (ChatGPT, iPhone) is laid out left-to-right and its words come
                out in the wrong order. One that ends on an English word puts
                the full stop on the wrong side. Rephrase so the line starts
                and ends on a Persian word.
  - LETTERS     Arabic ي and ك instead of Persian ی and ک, usually from an
                Arabic keyboard layout. Searches typed on a Persian keyboard
                may not match them.
  - HASHTAGS    Persian tags are counted (the old pattern only saw Latin
                ones), and a half-space inside a tag is flagged, because the
                tag can stop at it. Use an underscore: #هوش_مصنوعی.

Usage
  python3 caption.py caption.txt
  python3 caption.py caption.txt --keywords "proposal software,client contract"
  pbpaste | python3 caption.py -
  python3 caption.py caption.txt --json
"""

import argparse
import json
import re
import sys
import os
import textwrap

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import persian  # noqa: E402

LIMIT = 2200             # Instagram's hard caption limit.
TRUNCATE = 125           # Roughly where the feed cuts to "... more".
HASHTAG_LIMIT = 5        # Instagram's cap per post or reel since 18 Dec 2025,
                         # down from 30. Announced by the @Creators account:
                         # "using fewer (up to 5) more targeted hashtags,
                         # rather than many generic ones, can improve both your
                         # content's performance and people's experience".

HASHTAG_RE = re.compile(r"(?:^|\s)(#[\w\u200c]+)")
MENTION_RE = re.compile(r"(?:^|\s)(@[A-Za-z0-9_.]+)")
LINK_RE = re.compile(r"https?://\S+|\bwww\.\S+|\b[a-z0-9-]+\.(?:com|co|io|net|org|ai|app)/\S*",
                     re.IGNORECASE)
EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF☀-➿←-⇿️]")
CONCRETE_RE = re.compile(r"\$\s?\d|\b\d[\d,.]*\b|(?<!^)\b[A-Z][a-z]{2,}\b", re.MULTILINE)


def concrete(text):
    if persian.is_persian(text):
        return persian.concrete_markers(text)
    return CONCRETE_RE.findall(text)

ASKS = [
    (re.compile(r"(?i)\bcomment (?:the word |\")?[A-Z0-9]{2,}\b"), "comment a keyword"),
    (re.compile(r"(?i)\b(?:dm|message) me\b"), "DM me"),
    (re.compile(r"(?i)\bsave (?:this|it)\b"), "save this"),
    (re.compile(r"(?i)\bshare (?:this|it)\b"), "share this"),
    (re.compile(r"(?i)\bfollow (?:me|for)\b"), "follow"),
    (re.compile(r"(?i)\blink in (?:my )?bio\b"), "link in bio"),
    (re.compile(r"(?i)\b(?:swipe|tap) (?:through|left|right|for|to)\b"), "swipe or tap"),
    (re.compile(r"(?i)\btell me\b|\bwhat would you\b|\bwhich one\b"), "answer a question"),
]
# Persian asks, matched against persian.normalize(caption): no half-spaces,
# "می" joined to its verb. Write new patterns in that form.
FA_ASKS = [
    (re.compile(r"(?:کلمه|کلمهی)?\s*[«\"]?\S+[»\"]?\s*(?:رو|را)\s*کامنت\s*(?:کن|کنید|کنین|بذار|بزار)"
                r"|کامنت\s*(?:کن|کنید|کنین|بذار|بزار)\s*[«\"]?[A-Za-z0-9\u0600-\u06ff]{2,}"),
     "comment a keyword"),
    (re.compile(r"دایرکت\s*(?:بده|بدید|بدین|بزن|بزنید)|(?:بهم|به ما)\s*پیام\s*(?:بده|بدید|بدین)"), "DM me"),
    (re.compile(r"(?:سیو|ذخیره)(?:ش|اش|هش)?\s*(?:کن|کنید|کنین)(?![\u0600-\u06ff])"), "save this"),
    (re.compile(r"(?:بفرست|بفرستید|بفرستین|شیر\s*کن|به\s*اشتراک\s*بذار)"), "share this"),
    (re.compile(r"فالو\s*(?:کن|کنید|کنین|یادت|یادتون)|(?:ما را|پیج رو)\s*(?:دنبال|فالو)"), "follow"),
    (re.compile(r"لینک\s*(?:تو|توی|در)\s*(?:بایو|بیو)"), "link in bio"),
    (re.compile(r"(?:ورق|اسلاید)\s*(?:بزن|بزنید|بزنین)|سوایپ\s*(?:کن|کنید)"), "swipe or tap"),
    (re.compile(r"(?:بهم|برام)\s*بگو|نظرت\s*چیه|نظرتون\s*چیه|کدومش|کدوم\s*(?:یکی|رو)|شما\s*بودید\s*چیکار"),
     "answer a question"),
]

FILLER_TAGS = {"#viral", "#fyp", "#explore", "#explorepage", "#foryou", "#foryoupage",
               "#trending", "#instagood", "#love", "#follow", "#like4like", "#reels",
               "#reelsinstagram", "#viralreels", "#instadaily",
               "#اکسپلور", "#اکسپلورر", "#اکسپلور_ایران", "#لایک", "#فالو", "#فالوور",
               "#لایک_فالو", "#فالو_لایک", "#وایرال", "#ترند", "#ریلز", "#ریلز_اینستاگرام",
               "#اینستاگرام", "#کلیپ", "#کلیپ_جذاب"}


def visible_window(text, cut):
    """What the feed shows. Instagram cuts mid-word, so this does too."""
    flat = text.strip()
    return flat if len(flat) <= cut else flat[:cut]


def render_box(window, truncated, out=sys.stdout, width=52):
    print("\n  WHAT THE FEED SHOWS", file=out)
    print("  +" + "-" * (width + 2) + "+", file=out)
    lines = []
    for raw in window.split("\n"):
        lines.extend(textwrap.wrap(raw, width) or [""])
    for line in lines[:8]:
        print(f"  | {line:<{width}} |", file=out)
    tail = "... more" if truncated else "(whole caption fits)"
    print("  +" + "-" * (width + 2 - len(tail) - 2) + f" {tail} " + "+", file=out)


def analyse(text, cut=TRUNCATE, keywords=None):
    text = text.rstrip()
    stripped = text.strip()
    chars = len(stripped)
    lines = [l for l in stripped.split("\n")]
    first_line = lines[0].strip() if lines else ""
    tags = HASHTAG_RE.findall(stripped)
    mentions = MENTION_RE.findall(stripped)
    links = LINK_RE.findall(stripped)
    emoji = EMOJI_RE.findall(stripped)
    window = visible_window(stripped, cut)
    truncated = chars > cut
    fa = persian.is_persian(stripped)
    asks = [name for pattern, name in ASKS if pattern.search(stripped)]
    if fa:
        flat = persian.normalize(stripped)
        asks += [name for pattern, name in FA_ASKS
                 if pattern.search(flat) and name not in asks]
    filler = [t for t in tags if t.lower() in FILLER_TAGS]
    keywords = [k.strip() for k in (keywords or []) if k.strip()]

    checks = []

    def add(name, status, detail):
        checks.append({"check": name, "status": status, "detail": detail})

    add("LENGTH", "FAIL" if chars > LIMIT else "PASS",
        f"{chars} / {LIMIT} characters" + (f", {chars - LIMIT} over the limit"
                                           if chars > LIMIT else ""))

    if not first_line:
        add("FIRST LINE", "FAIL", "the caption opens on a blank line")
    elif first_line.startswith("#") or first_line.startswith("@"):
        add("FIRST LINE", "FAIL",
            "opens on a hashtag or a mention, which is the one position worth a sentence")
    elif len(first_line) > cut:
        add("FIRST LINE", "WARN",
            f"{len(first_line)} characters, so it gets cut at {cut} mid-thought. "
            "Fine if the cut is a cliffhanger, bad if it is a subordinate clause")
    else:
        add("FIRST LINE", "PASS", f"{len(first_line)} characters, lands whole")

    markers = concrete(window)
    add("HOOK IS CONCRETE", "PASS" if markers else "WARN",
        f"{len(markers)} number(s) or name(s) in the visible window"
        + ("" if markers else " - nothing checkable before the tap"))

    if len(tags) > HASHTAG_LIMIT:
        add("HASHTAGS", "FAIL", f"{len(tags)} tags, over Instagram's cap of {HASHTAG_LIMIT}. "
                                "Tags past the fifth do not count and the block reads as old")
    elif len(tags) == HASHTAG_LIMIT and filler:
        add("HASHTAGS", "WARN", f"{len(tags)} tags, at the cap, and "
                                f"{len(filler)} of them generic. Spend the five on topics")
    elif filler:
        add("HASHTAGS", "WARN", f"{len(tags)} tags, {len(filler)} of them generic "
                                f"({', '.join(filler[:3])}). Those describe nothing")
    else:
        add("HASHTAGS", "PASS", f"{len(tags)} tag(s)" + (f": {' '.join(tags)}" if tags else ""))

    if not tags:
        add("TAG PLACEMENT", "PASS", "no tags to place")
    elif any(re.search(r"(?:^|\s)" + re.escape(t) + r"\b", window) for t in tags):
        add("TAG PLACEMENT", "WARN", "a hashtag is inside the visible window, "
                                     "spending feed space on a label")
    else:
        add("TAG PLACEMENT", "PASS", "tags are below the fold")

    add("LINKS", "WARN" if links else "PASS",
        f"{len(links)} link(s) in the caption, and captions are not clickable. "
        f"Move it to the bio or the DM" if links else "no dead links in the body")

    if len(asks) == 1:
        add("ONE ASK", "PASS", f"one call to action: {asks[0]}")
    elif not asks:
        add("ONE ASK", "WARN", "no call to action. Decide what this post is for")
    else:
        add("ONE ASK", "WARN", f"{len(asks)} asks ({', '.join(asks)}). "
                               "Two asks is the same as none")

    density = len(emoji) * 100 / max(chars, 1)
    add("EMOJI", "WARN" if density > 4 else "PASS",
        f"{len(emoji)} emoji, {density:.1f} per 100 characters"
        + (" - reads as decoration" if density > 4 else ""))

    if fa:
        flipped, tail = [], []
        for i, line in enumerate(stripped.split("\n"), 1):
            if not persian.has_rtl(line):
                continue                         # an all-English line is fine as it is
            body = re.sub(r"(?:\s*#[\w\u200c]+)+\s*$", "", line).strip()
            if persian.first_strong(body) == "ltr":
                flipped.append(i)
            elif persian.last_strong(re.sub(r"[\s.!?؟،,؛:)»\"'\U0001F300-\U0001FAFF☀-➿️]+$", "", body)) == "ltr":
                tail.append(i)
        if flipped:
            add("DIRECTION", "FAIL",
                f"line(s) {', '.join(map(str, flipped))} start with an English word, so Instagram lays "
                "them out left-to-right and the Persian comes out in the wrong order. "
                "Start the line with a Persian word"
                + (f". Line(s) {', '.join(map(str, tail))} also end on one" if tail else ""))
        elif tail:
            add("DIRECTION", "WARN",
                f"line(s) {', '.join(map(str, tail))} end on an English word, so the punctuation "
                "after it lands on the wrong side. End the line on a Persian word")
        else:
            add("DIRECTION", "PASS", "every Persian line starts and ends on a Persian word")

        arabic = sum(stripped.count(c) for c in "يكى")
        add("LETTERS", "WARN" if arabic else "PASS",
            f"{arabic} Arabic ي/ك. Searches typed on a Persian keyboard may not match them. "
            "humanize.py fixes this" if arabic else "Persian ی and ک throughout")

        broken = [t for t in tags if persian.ZWNJ in t]
        if broken:
            add("TAG SPELLING", "WARN",
                f"{', '.join(broken[:3])} contain a half-space, and the tag can stop at it. "
                "Use an underscore instead: #هوش_مصنوعی")

    if keywords:
        norm = (lambda t: persian.normalize(t).lower()) if fa else (lambda t: t.lower())
        low = norm(stripped)
        found = [k for k in keywords if norm(k) in low]
        missing = [k for k in keywords if norm(k) not in low]
        in_window = [k for k in found if norm(k) in norm(window)]
        status = "PASS" if not missing else ("WARN" if found else "FAIL")
        add("SEARCH TERMS", status,
            f"{len(found)}/{len(keywords)} present"
            + (f", {len(in_window)} in the visible window" if found else "")
            + (f". Missing: {', '.join(missing)}" if missing else ""))

    fails = sum(1 for c in checks if c["status"] == "FAIL")
    warns = sum(1 for c in checks if c["status"] == "WARN")
    verdict = "FIX" if fails else ("REVIEW" if warns else "READY")

    return {
        "characters": chars, "limit": LIMIT, "truncate_at": cut,
        "visible": window, "truncated": truncated,
        "first_line_chars": len(first_line),
        "hashtags": tags, "mentions": mentions, "links": links,
        "emoji": len(emoji), "asks": asks,
        "checks": checks, "verdict": verdict,
    }


def render(a, out=sys.stdout):
    head = (f"CAPTION LINT  ·  {a['characters']} / {a['limit']} chars  ·  "
            f"{len(a['hashtags'])} hashtags  ·  {len(a['asks'])} ask(s)")
    print("\n" + head, file=out)
    print("=" * max(len(head), 62), file=out)
    render_box(a["visible"], a["truncated"], out=out)
    print("", file=out)
    for c in a["checks"]:
        print(f"  {c['status']:<5} {c['check']:<17} {c['detail']}", file=out)
    print("-" * max(len(head), 62), file=out)
    print(f"  VERDICT  {a['verdict']}\n", file=out)


def main():
    ap = argparse.ArgumentParser(description="Lint an Instagram caption.")
    ap.add_argument("input", nargs="?", default="-", help="caption file, or - for stdin")
    ap.add_argument("--truncate", type=int, default=TRUNCATE,
                    help=f"characters shown before '... more' (default {TRUNCATE})")
    ap.add_argument("--keywords", default="", help="comma-separated terms you want to be found for")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    raw = sys.stdin.read() if args.input == "-" else open(args.input, encoding="utf-8").read()
    a = analyse(raw, cut=args.truncate, keywords=args.keywords.split(","))
    if args.json:
        print(json.dumps(a, indent=2, ensure_ascii=False))
    else:
        render(a)
    sys.exit(0 if a["verdict"] == "READY" else 1)


if __name__ == "__main__":
    main()
