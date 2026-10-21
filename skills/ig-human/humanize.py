#!/usr/bin/env python3
"""
humanize.py - strip the machine fingerprint out of a draft.

Three passes, in this order:

  1. INVISIBLE   delete or normalise the characters a human keyboard never
                 produces: zero-width joiners, word joiners, soft hyphens,
                 BOMs, Unicode tag characters, non-breaking and narrow spaces.
                 These survive copy-paste and are the most mechanical tell in
                 any generated text.
  2. TYPOGRAPHIC em dash -> comma, en dash -> hyphen, curly quotes -> straight,
                 ellipsis -> three dots, bullet -> hyphen.
  3. LEXICAL     replace the slop lexicon in slop.json with plain words,
                 preserving capitalisation and leaving URLs untouched.

Structural tells (rule-of-three, "not just X, it's Y", hashtag walls) are
REPORTED, never auto-rewritten - rewriting a sentence's shape needs judgement,
so that is the model's job, not a regex's.

Persian (Farsi) text is detected automatically and handled on its own terms:
  - the half-space (ZWNJ, U+200C) between two Persian letters is spelling, not
    a fingerprint, and is kept. Stray or doubled ones are still removed.
  - direction marks (RLM, LRM, ALM and the isolates) are kept whenever the
    text contains Persian, because that is what holds mixed Persian and
    English in the right order.
  - a zero-width joiner inside an emoji sequence is kept in any language.
  - em dash becomes the Persian comma, curly quotes become guillemets «»,
    Arabic yeh and kaf become Persian ی and ک.
  - the Persian half of slop.json is matched with or without half-spaces.

Usage
  python3 humanize.py draft.txt
  python3 humanize.py draft.txt --report
  pbpaste | python3 humanize.py - --report
  python3 humanize.py draft.txt --json
  python3 humanize.py draft.txt -o clean.txt
"""

import argparse
import json
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import persian  # noqa: E402

LEX = os.path.join(HERE, "slop.json")

URL_RE = re.compile(r"https?://\S+|www\.\S+|\S+@\S+\.\S+")
SENT_RE = persian.SENT_RE


def load_lexicon(path=LEX):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _cp(spec):
    """'U+200B' -> '\\u200b';  'U+E0000-U+E007F' -> (start, end)."""
    if "-" in spec:
        a, b = spec.split("-")
        return (int(a[2:], 16), int(b[2:], 16))
    return int(spec[2:], 16)


def protect_urls(text):
    """Swap URLs for placeholders so no pass rewrites inside a link."""
    found = []

    def stash(m):
        found.append(m.group(0))
        return f"\x00URL{len(found) - 1}\x00"

    return URL_RE.sub(stash, text), found


def restore_urls(text, found):
    for i, url in enumerate(found):
        text = text.replace(f"\x00URL{i}\x00", url)
    return text


def pass_invisible(text, lex):
    """Delete or space-normalise invisible characters. Returns (text, hits).

    A character that is doing a real job (a Persian half-space, a direction
    mark in right-to-left text, a joiner inside an emoji) is kept, and the
    report says how many were kept so nobody wonders where they went.
    """
    hits = []
    kept = {}
    doubled = len(re.findall(persian.ZWNJ + "{2,}", text))
    if doubled:
        text = re.sub(persian.ZWNJ + "{2,}", persian.ZWNJ, text)
        hits.append({"name": "U+200C doubled half-space", "count": doubled, "action": "collapse"})

    def sweep(text, is_target, replacement):
        out, n = [], 0
        for i, c in enumerate(text):
            if is_target(c):
                if persian.keep_invisible(text, i):
                    kept[c] = kept.get(c, 0) + 1
                    out.append(c)
                    continue
                n += 1
                out.append(replacement)
            else:
                out.append(c)
        return "".join(out), n

    listed = set()
    for entry in lex["invisible"]:
        cp = _cp(entry["cp"])
        listed.update(range(cp[0], cp[1] + 1) if isinstance(cp, tuple) else [cp])
        if isinstance(cp, tuple):
            lo, hi = cp
            is_target = (lambda lo, hi: lambda c: lo <= ord(c) <= hi)(lo, hi)
        else:
            is_target = (lambda cp: lambda c: ord(c) == cp)(cp)
        text, n = sweep(text, is_target, "" if entry["action"] == "delete" else " ")
        if n:
            hits.append({"name": entry["cp"] + " " + entry["name"], "count": n,
                         "action": entry["action"]})
    # Any remaining Cf (format) character is invisible by definition.
    text, n = sweep(text, lambda c: unicodedata.category(c) == "Cf"
                    and ord(c) not in listed, "")
    if n:
        hits.append({"name": "other invisible format chars", "count": n,
                     "action": "delete"})
    for c, n in kept.items():
        label = {persian.ZWNJ: "half-spaces (Persian spelling)",
                 persian.ZWJ: "emoji joiners",
                 }.get(c, "direction marks (right-to-left text)")
        hits.append({"name": f"U+{ord(c):04X} {label}", "count": n, "action": "kept"})
    return text, hits


def pass_typographic(text, lex):
    hits = []
    fa = persian.is_persian(text)
    for entry in lex["typographic"]:
        ch = entry["from"]
        n = text.count(ch)
        if not n:
            continue
        to = entry["to"]
        if fa and ch == "—":
            to = "، "
        elif fa and ch in "“”":
            continue                      # paired below, in reading order
        hits.append({"name": f"{ch} {entry['name']}", "count": n, "to": to.strip() or "(space)"})
        if ch == "—":
            # " word — word " and "word—word" both collapse to a comma + space.
            text = re.sub(r"\s*—\s*", to, text)
        elif ch == "–":
            text = re.sub(r"\s*–\s*(?=\d)", "-", text)      # 5–10  -> 5-10
            text = re.sub(r"\s+–\s+", "، " if fa else ", ", text)   # used as em dash
            text = text.replace("–", "-")
        else:
            text = text.replace(ch, to)
    if fa and ("“" in text or "”" in text):
        # Persian quotes are «». Writers and models put “ and ” on either side
        # in right-to-left text, so pair them in reading order instead of
        # trusting which one was typed: first is «, second is », and so on.
        n = sum(text.count(c) for c in "“”")
        hits.append({"name": "“” CURLY DOUBLE QUOTES", "count": n, "to": "«»"})
        marks = iter("«»" * n)
        text = re.sub("[“”]", lambda m: next(marks), text)
    if fa:
        for ch, name in (("ي", "ARABIC YEH"), ("ى", "ALEF MAKSURA"), ("ك", "ARABIC KAF")):
            n = text.count(ch)
            if n:
                hits.append({"name": f"{ch} {name}", "count": n,
                             "to": "ک" if ch == "ك" else "ی"})
        text = persian.fix_letters(text)
    # A comma inserted before existing punctuation reads wrong.
    text = re.sub(r"[,،]\s*([,.;:!?،؛؟])", r"\1", text)
    # [ \t]*, not \s*: "word,\n\nNext" must keep its paragraph break.
    text = re.sub(r"[,،][ \t]*\n", "\n", text)
    return text, hits


def _match_case(src, repl):
    if not repl:
        return repl
    if src.isupper() and len(src) > 1:
        return repl.upper()
    if src[0].isupper():
        return repl[0].upper() + repl[1:]
    return repl


def pass_lexical(text, lex):
    """Replace slop words and phrases. Longest first so phrases win."""
    hits = []
    entries = sorted(lex["phrases"] + lex["words"],
                     key=lambda e: len(e["find"]), reverse=True)
    for entry in entries:
        find = entry["find"]
        pattern = persian.phrase_re(find)
        found = pattern.findall(text)
        if not found:
            continue
        hits.append({"find": find, "replace": entry["replace"] or "(deleted)",
                     "count": len(found), "family": entry["family"]})
        text = pattern.sub(lambda m: _match_case(m.group(0), entry["replace"]), text)
    # Clean up after deletions. Deleting a whole clause leaves orphaned
    # punctuation behind ("system. ." or a line that now opens on a comma),
    # and that reads worse than the slop did.
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"(?m)^[ \t]*(?:[,.;:،؛]+[ \t]*)+", "", text)
    text = re.sub(r"(?m)^[ \t](?=\S)", "", text)       # one space left by a deletion.
                                                      # Deeper indents are deliberate.
    text = re.sub(r"\s+([,.;:!?،؛؟])", r"\1", text)
    text = re.sub(r"[,،]\s*([,.;:!?،؛؟])", r"\1", text)  # an em dash became a comma,
                                                      # then the clause after it went
    text = text.replace("...", "\x00ELL\x00")          # protect real ellipses
    text = re.sub(r"\.\s*\.+", ".", text)
    text = re.sub(r"([!?؟])\s*\.", r"\1", text)
    text = text.replace("\x00ELL\x00", "...")
    text = re.sub(r"(?m)^[ \t]+$", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # An em dash that became a comma, followed by a sentence connective, leaves
    # a splice ("is important, also, it's proof"). Promote it to a full stop.
    text = re.sub(r",\s*(also|so|still|basically|in the end)\s*,\s*",
                  lambda m: ". " + m.group(1)[0].upper() + m.group(1)[1:] + ", ", text)
    return text, hits


def scan_structures(text, lex):
    flags = []
    for s in lex["structures"]:
        try:
            pattern = re.compile(s["regex"], re.MULTILINE)
        except re.error:
            continue
        found = pattern.findall(text)
        if found:
            flags.append({"name": s["name"], "count": len(found), "fix": s["fix"]})
    # Sentence-length uniformity is structural too.
    lens = [len(s.split()) for s in SENT_RE.findall(text) if len(s.split()) > 2]
    if len(lens) >= 4:
        mean = sum(lens) / len(lens)
        var = sum((n - mean) ** 2 for n in lens) / len(lens)
        cv = (var ** 0.5) / mean if mean else 0
        if cv < 0.35:
            flags.append({
                "name": f"Uniform sentence length (variation {cv:.2f})",
                "count": len(lens),
                "fix": "Break one sentence in half. Let another run long. Machines write even.",
            })
    return flags


def restore_capitals(original, text):
    """Deleting an opener leaves the next word lower case.

    Only fix it for writers who capitalise their sentences in the first place:
    a deliberately lower-case voice is a style, not an artefact, and shouting
    over it would be exactly the kind of thing this script exists to stop.
    """
    starts = re.findall(r"(?:^|[.!?]\s+|\n)\s*([A-Za-z])", original)
    if not starts or sum(1 for c in starts if c.isupper()) * 2 < len(starts):
        return text
    return re.sub(r"(?:^|(?<=[.!?] )|(?<=[.!?]\n)|(?<=\n))\s*([a-z])",
                  lambda m: m.group(0)[:-1] + m.group(1).upper(), text)


def humanize(text, lex):
    raw_for_case = text
    text, urls = protect_urls(text)
    text, inv = pass_invisible(text, lex)
    text, typo = pass_typographic(text, lex)
    text, lexi = pass_lexical(text, lex)
    text = restore_capitals(raw_for_case, text)
    text = restore_urls(text, urls)
    return text.strip() + "\n", {
        "invisible": inv,
        "typographic": typo,
        "lexical": lexi,
        "structures": scan_structures(text, lex),
    }


def render_report(report, out=sys.stderr):
    def head(title):
        print(f"\n{title}\n" + "-" * len(title), file=out)

    total = sum(h["count"] for h in report["invisible"] if h["action"] != "kept") \
        + sum(h["count"] for h in report["typographic"]) \
        + sum(h["count"] for h in report["lexical"])

    head("HUMANIZE REPORT")
    print(f"{total} machine artefacts removed, "
          f"{len(report['structures'])} structural tells flagged for rewrite", file=out)

    if report["invisible"]:
        head("1. INVISIBLE CHARACTERS")
        for h in report["invisible"]:
            print(f"  {h['count']:>3}x  {h['name']}  -> {h['action']}", file=out)
    if report["typographic"]:
        head("2. TYPOGRAPHY")
        for h in report["typographic"]:
            print(f"  {h['count']:>3}x  {h['name']}  -> {h['to']}", file=out)
    if report["lexical"]:
        head("3. SLOP LEXICON")
        for h in report["lexical"]:
            print(f"  {h['count']:>3}x  {h['find']}  -> {h['replace']}   [{h['family']}]", file=out)
    if report["structures"]:
        head("4. STRUCTURAL TELLS  (not auto-fixed - rewrite these yourself)")
        for h in report["structures"]:
            print(f"  {h['count']:>3}x  {h['name']}\n        {h['fix']}", file=out)
    if not any(report.values()):
        head("CLEAN")
        print("  Nothing to strip.", file=out)
    print("", file=out)


def main():
    ap = argparse.ArgumentParser(description="Strip the machine fingerprint out of a draft.")
    ap.add_argument("input", nargs="?", default="-", help="file, or - for stdin")
    ap.add_argument("-o", "--out", help="write cleaned text here instead of stdout")
    ap.add_argument("--report", action="store_true", help="print what changed, to stderr")
    ap.add_argument("--json", action="store_true", help="emit {text, report} as JSON")
    ap.add_argument("--lexicon", default=LEX, help="path to slop.json")
    args = ap.parse_args()

    raw = sys.stdin.read() if args.input == "-" else open(args.input, encoding="utf-8").read()
    lex = load_lexicon(args.lexicon)
    clean, report = humanize(raw, lex)

    if args.json:
        print(json.dumps({"text": clean, "report": report}, indent=2, ensure_ascii=False))
        return
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(clean)
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(clean)
    if args.report:
        render_report(report)


if __name__ == "__main__":
    main()
