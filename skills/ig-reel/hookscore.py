#!/usr/bin/env python3
"""
hookscore.py - score the first line of a Reel on the five things strong hooks
have in common, and rank a batch of them against each other.

What this is:  five local heuristics, computed on your machine from the text
alone. They measure properties that hooks which hold attention tend to share -
a length you can say in under three seconds, a concrete marker, something at stake,
the payload at the front rather than the back, and a viewer to aim it at.

What this is NOT:  a view predictor. It was tested against 74 real short-form
hooks, transcribed from the first three seconds of the top eight and bottom
eight performers on five channels. Separating a real hook from a deliberately
bad one it does well: AUC 0.83, and 9 of 10 written-to-be-bad hooks scored
below the real median. Separating a good creator's hits from that same
creator's misses it barely does at all: AUC 0.56, where 0.50 is a coin flip.

So use it for what it measured well. It catches greetings, preambles, hooks
with nothing concrete in them and hooks that take five seconds to say. It will
not tell you which of two decent hooks will travel, and nothing that reads text
can, because that is decided by your face, your edit, your audio and who
Instagram shows it to. Trust the retention graph over this script.

Each check returns 0 to 100. Higher is better.

Persian (Farsi) hooks are detected automatically and scored with Persian word
lists: spoken numbers and money words, stakes and negation (any "نمی..." verb
counts), weak openers like "سلام" and "امروز می‌خوام", second-person address,
and Latin-script names (ChatGPT, iPhone) as the concrete marker Persian has
no capital letters for. The English thresholds were measured; the Persian
word lists were not, so treat Persian scores as the same kind of filter -
good at catching the weak hook, silent on which decent hook wins.

Usage
  python3 hookscore.py hooks.txt              # one hook per line, ranked
  python3 hookscore.py --hook "I lost $18,000 on one missing contract."
  pbpaste | python3 hookscore.py -
  python3 hookscore.py hooks.txt --json
"""

import argparse
import json
import re
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import persian  # noqa: E402

WORD_RE = re.compile(r"[A-Za-z0-9$%'’-]+")
NUMBER_RE = re.compile(
    r"\$\s?\d[\d,]*(?:\.\d+)?"                       # money, whole
    r"|\b\d[\d,]*(?:\.\d+)?\s?"                      # a figure, with or
    r"(?:%|k\b|x\b|hrs?\b|hours?\b|mins?\b|minutes?\b"  # without a unit
    r"|days?\b|weeks?\b|months?\b|years?\b)?",
    re.IGNORECASE)
PROPER_RE = re.compile(r"(?<!^)\b[A-Z][a-z]{2,}\b")
HASHTAG_RE = re.compile(r"(?:^|\s)#\w+")
EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF☀-➿]")

# Spoken hooks say their numbers out loud. "Zero dollars" and "twenty grand"
# are as concrete as "$0" and "$20,000", and counting only digits missed them.
# "one" and "first" are deliberately absent: they are filler far more often
# than they are a quantity.
SPOKEN_NUMBERS = {
    "zero", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "fifteen", "twenty", "thirty", "forty", "fifty",
    "sixty", "seventy", "eighty", "ninety", "hundred", "thousand", "million",
    "billion", "dozen", "half", "twice", "triple",
}
MONEY_WORDS = {
    "dollars", "dollar", "bucks", "grand", "percent", "cents",
    "millionaire", "billionaire", "revenue", "profit", "salary", "rent",
}

# Words that put something on the line. A hook with none of these is a
# statement; a hook with one is a reason to keep watching.
STAKES = {
    "stop", "never", "wrong", "mistake", "mistakes", "lost", "lose", "losing",
    "cost", "costs", "broke", "broken", "failed", "failure", "fail", "nobody",
    "no", "not", "don't", "dont", "doesn't", "didn't", "can't", "won't",
    "quit", "quitting", "fired", "deleted", "delete", "killed", "kills", "kill",
    "replaced", "replaces", "cut", "beat", "free", "paid", "charged", "hired",
    "saved", "first",
    "banned", "illegal", "worst", "hate", "hated", "wasted", "waste", "scam",
    "lie", "lied", "lying", "truth", "secret", "hidden", "stole", "stolen",
    "before", "until", "instead", "but", "except", "unless", "problem",
    "risk", "danger", "warning", "regret", "wish", "should", "shouldn't",
    "still", "already", "only", "without", "versus", "vs", "actually",
}

# Openers that spend the first second saying nothing.
WEAK_OPENERS = [
    "so", "ok", "okay", "hey", "hi", "hello", "guys", "yo", "alright",
    "welcome", "today", "basically", "honestly", "look", "listen", "um",
    "just", "let", "lets", "let's", "i wanted", "i want", "one of",
    "have you", "did you", "do you", "are you", "in this", "in today",
    "the thing", "a lot", "there is", "there are", "this is", "it is",
    "as a", "when it", "if you've", "you know",
]

# Imperatives that earn the front position.
IMPERATIVES = {
    "stop", "steal", "copy", "delete", "try", "watch", "read", "save",
    "use", "build", "make", "write", "send", "take", "start", "quit",
    "never", "always", "don't", "dont", "do", "put", "run", "check",
}

DEALBREAKERS = [
    (re.compile(r"(?i)^\s*(?:stop scrolling|don'?t scroll)"),
     "Opens with \"stop scrolling\". Asking for attention proves you have not earned it."),
    (re.compile(r"(?i)\b(?:in (?:this|today'?s) (?:video|reel)|i'?m going to show you|i'?ll show you how)\b"),
     "Video preamble. Delete it and open on the payoff."),
    (re.compile(r"(?i)^\s*(?:hey |hi |what'?s up |welcome )"),
     "Greeting. Nobody came to the feed to be greeted."),
    (HASHTAG_RE,
     "Hashtag in the hook. Hashtags belong at the bottom of the caption, if anywhere."),
    (EMOJI_RE,
     "Emoji in the hook. On-screen text at hook size has room for words or for an emoji, not both."),
]


# ---------------------------------------------------------------- Persian --
# All Persian lists are in normalised form (see persian.normalize): no
# half-spaces, Persian yeh and kaf, "می" joined to its verb. Write new entries
# the same way: "میخوام", not "می‌خوام".

FA_STAKES = {
    "نه", "نکن", "نکنید", "نکنین", "هیچوقت", "هرگز", "هیچکس", "هیچکی", "هیچ",
    "ولی", "اما", "جز", "بدون", "فقط", "هنوز", "قبل", "قبلش", "بجای", "بهجای",
    "کاش", "نباید", "باید", "اصلا", "واقعا", "واقعیت", "حقیقت", "راز", "رازی",
    "مخفی", "پنهان", "رایگان", "مجانی", "اولین", "آخرین", "بدترین", "بهترین",
    "یعنی", "وگرنه", "تقلب", "دروغ", "ممنوع", "غیرقانونی", "جریمه",
}
# Stems: a token that starts with one of these counts, so "اشتباهی",
# "اشتباهاتی" and "اشتباهمو" all land.
FA_STAKE_STEMS = (
    "اشتباه", "غلط", "ضرر", "باخت", "هزینه", "گرون", "گران", "اخراج", "حذف",
    "پاکش", "جایگزین", "شکست", "ورشکست", "خراب", "متنفر", "کلاهبردار", "مشکل",
    "خطر", "هشدار", "پشیمون", "پشیمان", "دزد", "هدر", "سوخت", "پولم", "پولت",
    "بلاک", "بن", "ریجکت", "رد شد",
)
FA_WEAK_OPENERS = [
    "سلام", "درود", "دوستان", "بچهها", "رفقا", "خب", "خوب", "امروز", "ببین",
    "ببینید", "گوش", "راستش", "یعنی", "اوکی", "بریم", "بیاین", "بیایید",
    "میخوام", "میخواهم", "تو این", "توی این", "در این", "یکی از", "آیا",
    "تا حالا", "این یه", "این یک", "وقتی", "اگه شما", "میدونی", "میدونستی",
    "همونطور", "همانطور", "خیلیها", "خیلی از", "بذارید", "بزارید", "بذار",
    "هی", "های", "خوش اومدین", "خوش آمدید",
]
FA_IMPERATIVES = {
    "نکن", "نکنید", "نکنین", "نزن", "ننویس", "نخر", "نخرید", "بخر", "بخرید",
    "بساز", "بسازید", "بنویس", "بنویسید", "بفرست", "بفرستید", "بگیر", "بگیرید",
    "بخون", "بخوانید", "بزن", "بزنید", "ببین", "ببینید", "امتحان", "کپی",
    "پاک", "سیو", "ذخیره", "استفاده", "شروع", "ول", "چک", "هیچوقت", "همیشه",
    "دانلود", "نصب", "بدزد", "بدزدید",
}
FA_SECOND = {"شما", "تو", "خودت", "خودتون", "بهت", "بهتون", "برات", "براتون",
             "باهات", "باهاتون", "ازت", "ازتون"}
FA_FIRST = {"من", "ما", "خودم", "خودمون", "برام", "بهم", "بهمون", "ازم"}
FA_SECOND_VERB = re.compile("^ن?(?:می)?[\u0622-\u06cc]{1,10}(?:ی|ین|ید)$")
FA_FIRST_VERB = re.compile("^ن?می[\u0622-\u06cc]{1,10}(?:م|یم)$")
FA_NUM_RE = re.compile(r"\d[\d,.]*\s?%?")

FA_DEALBREAKERS = [
    (re.compile(r"^\s*(?:اسکرول نکن|رد نشو|رد نشید|صبر کن)"),
     "Opens with \"اسکرول نکن\". Asking for attention proves you have not earned it."),
    (re.compile(r"(?:(?:تو|توی|در) این (?:ویدیو|ویدئو|ریلز|ریل|پست|کلیپ)"
                r"|امروز (?:میخوام|میخواهم|قراره)"
                r"|(?:میخوام|قراره) (?:بهتون|به شما|بهت) (?:نشون|یاد|بگم))"),
     "Video preamble (\"تو این ویدیو\", \"امروز می‌خوام\"). Delete it and open on the payoff."),
    (re.compile(r"^\s*(?:سلام|درود|هی|های|خوش اومدین|خوش آمدید|دوستان|بچهها)(?![\u0600-\u06ff])"),
     "Greeting. Nobody came to the feed to be greeted."),
]


def _fa_is_stake(k):
    return (k in FA_STAKES or k.startswith("نمی") or k.startswith("نکرد")
            or any(k.startswith(st) for st in FA_STAKE_STEMS))


def _fa_is_payload(k, raw):
    return (_fa_is_stake(k) or k in persian.SPOKEN_NUMBERS or k in persian.MONEY_WORDS
            or bool(re.match(r"\d", k)) or bool(re.match(r"[A-Za-z]{3,}|[A-Za-z]+\d", raw)))


def clamp(n):
    return max(0.0, min(100.0, n))


def words(text):
    # "$18,000" is one word when it is spoken, so it is one word here too.
    if persian.is_persian(text):
        return persian.words(text)
    return WORD_RE.findall(re.sub(r"(?<=\d),(?=\d)", "", text))


def check_length(text):
    """A hook has to land before the thumb moves. Roughly two seconds."""
    w = words(text)
    n = len(w)
    secs = n / 2.75                      # ~165 words per minute, spoken
    chars = len(text.strip())
    if 5 <= n <= 12:
        score = 100.0
    elif n < 5:
        score = clamp(100 - (5 - n) * 20)
    else:
        score = clamp(100 - (n - 12) * 11)
    if chars > 60:                       # two lines of big on-screen text
        score -= 12
    return clamp(score), f"{n} words, {chars} chars, ~{secs:.1f}s spoken (want 5-12 words)"


def check_specificity(text):
    """One concrete thing beats three abstract ones."""
    if persian.is_persian(text):
        found = persian.concrete_markers(text)
        hits = len(found)
        score = 15.0 if hits == 0 else clamp(45 + hits * 30)
        return score, (f"{hits} concrete marker(s)" + (f": {', '.join(found[:4])}" if found else
                       " - no number, no name, nothing checkable"))
    nums = [n.strip() for n in NUMBER_RE.findall(text) if n.strip()]
    propers = set(PROPER_RE.findall(text))
    low = [w.lower().strip("'’") for w in words(text)]
    spoken = [w for w in low if w in SPOKEN_NUMBERS or w in MONEY_WORDS]
    hits = len(nums) + len(propers) + len(spoken)
    score = 15.0 if hits == 0 else clamp(45 + hits * 30)
    found = ", ".join(nums[:2] + sorted(propers)[:2] + spoken[:2])
    return score, (f"{hits} concrete marker(s)" + (f": {found}" if found else
                   " - no number, no name, nothing checkable"))


def check_stakes(text):
    """Tension, cost, negation. Something the viewer might lose."""
    if persian.is_persian(text):
        keys = persian.norm_words(text)
        markers = sorted({k for k in keys if _fa_is_stake(k)})
        flat = persian.normalize(text)
        if re.search(r"\$\s?\d|\d[\d,.]*\s?(?:تومن|تومان|دلار|میلیون)", flat):
            markers.append("a price")
        n = len(markers)
        score = {0: 20.0, 1: 70.0}.get(n, 100.0)
        return score, f"{n} tension marker(s)" + (f": {', '.join(markers[:4])}" if markers else
                                                  " - nothing is at stake in this line")
    w = [x.lower().strip("'’") for x in words(text)]
    hits = [x for x in w if x in STAKES]
    markers = sorted(set(hits))
    if re.search(r"\$\s?\d", text):
        markers.append("a price")
    n = len(markers)
    score = {0: 20.0, 1: 70.0}.get(n, 100.0)
    detail = f"{n} tension marker(s)" + (f": {', '.join(markers[:4])}" if markers else
                                         " - nothing is at stake in this line")
    return clamp(score), detail


def check_frontload(text):
    """The interesting word cannot be in position nine."""
    w = words(text)
    if not w:
        return 0.0, "empty"
    fa = persian.is_persian(text)
    low = persian.norm_words(text) if fa else [x.lower().strip("'’") for x in w]
    opener = " ".join(low[:2])
    penalty = 0
    hit_opener = None
    for weak in (FA_WEAK_OPENERS if fa else WEAK_OPENERS):
        if opener == weak or opener.startswith(weak + " ") or low[0] == weak \
                or (not fa and opener.startswith(weak)):
            penalty, hit_opener = 30, weak
            break
    payload = None
    for i, token in enumerate(low):
        if fa:
            if _fa_is_payload(token, w[i]):
                payload = i
                break
        elif (token in STAKES or token in SPOKEN_NUMBERS or token in MONEY_WORDS
                or NUMBER_RE.match(w[i]) or (i and PROPER_RE.match(w[i]))):
            payload = i
            break
    if payload is None:
        base = 30.0
        where = "no payload word anywhere in the line"
    elif payload <= 3:
        base = 100.0
        where = f"payload at word {payload + 1}"
    elif payload <= 6:
        base = 70.0
        where = f"payload at word {payload + 1}, could move forward"
    else:
        base = 40.0
        where = f"payload at word {payload + 1}, too late"
    detail = where + (f"; weak opener \"{hit_opener}\"" if hit_opener else "")
    return clamp(base - penalty), detail


def check_address(text):
    """Aimed at one viewer, or floating in the air."""
    if persian.is_persian(text):
        keys = persian.norm_words(text)
        if any(k in FA_SECOND or (k not in persian.NOT_MI_VERB and FA_SECOND_VERB.match(k)
                                  and (k.startswith("می") or k.startswith("نمی")))
               or (len(k) >= 5 and (k.endswith("تون") or k.endswith("تو"))) for k in keys):
            return 100.0, "speaks to the viewer"
        if keys and keys[0] in FA_IMPERATIVES:
            return 90.0, f"imperative opener (\"{keys[0]}\")"
        if any(k in FA_FIRST or FA_FIRST_VERB.match(k)
               or (k not in persian.NOT_FIRST_PERSON and persian.PAST_FIRST_RE.match(k))
               for k in keys):
            return 70.0, "first person, no viewer named"
        return 35.0, "third person, nobody in the room"
    low = text.lower()
    w = [x.lower().strip("'’") for x in words(text)]
    if re.search(r"\b(you|your|you're|youre|yourself)\b", low):
        return 100.0, "speaks to the viewer"
    if w and w[0] in IMPERATIVES:
        return 90.0, f"imperative opener (\"{w[0]}\")"
    if re.search(r"\b(i|my|me|we|our)\b", low):
        return 70.0, "first person, no viewer named"
    return 35.0, "third person, nobody in the room"


CHECKS = ["LENGTH", "SPECIFICITY", "STAKES", "FRONTLOAD", "ADDRESS"]


def run(text):
    results = {
        "LENGTH": check_length(text),
        "SPECIFICITY": check_specificity(text),
        "STAKES": check_stakes(text),
        "FRONTLOAD": check_frontload(text),
        "ADDRESS": check_address(text),
    }
    flags = [msg for pattern, msg in DEALBREAKERS if pattern.search(text)]
    if persian.is_persian(text):
        flat = persian.normalize(text)
        flags += [msg for pattern, msg in FA_DEALBREAKERS if pattern.search(flat)]
    scores = [results[c][0] for c in CHECKS]
    # The weakest property caps the hook, same logic as detect.py: one bad
    # property is enough for the thumb to keep moving.
    overall = statistics.mean(scores) * 0.6 + min(scores) * 0.4 - len(flags) * 15
    overall = clamp(overall)
    verdict = "STRONG" if overall >= 70 and min(scores) >= 55 and not flags else (
        "OK" if overall >= 50 else "WEAK")
    return results, overall, verdict, flags


def bar(score, width=24):
    filled = round(score / 100 * width)
    return "#" * filled + "." * (width - filled)


def render_one(text, results, overall, verdict, flags, out=sys.stdout):
    print("\nHOOK SCORE", file=out)
    print("=" * 62, file=out)
    print(f"  \"{text.strip()}\"\n", file=out)
    for name in CHECKS:
        score, detail = results[name]
        print(f"  {name:<13} {bar(score)} {score:5.1f}", file=out)
        print(f"  {'':<13} {detail}", file=out)
    print("-" * 62, file=out)
    print(f"  {'HOOK SCORE':<13} {bar(overall)} {overall:5.1f}   {verdict}", file=out)
    for f in flags:
        print(f"\n  DEALBREAKER  {f}", file=out)
    if verdict != "STRONG":
        weakest = min(CHECKS, key=lambda c: results[c][0])
        print(f"\n  Weakest property: {weakest}. Fix that one and re-run.", file=out)
    print("", file=out)


def render_table(rows, out=sys.stdout):
    print("\nHOOK RANKING\n" + "=" * 78, file=out)
    for i, r in enumerate(rows, 1):
        mark = "->" if i == 1 else "  "
        hook = r["hook"] if len(r["hook"]) <= 62 else r["hook"][:59] + "..."
        print(f"{mark} {r['score']:5.1f} {r['verdict']:<7} {hook}", file=out)
        print(f"        weakest: {r['weakest']} ({r['checks'][r['weakest']]['score']:.0f})", file=out)
        for f in r["flags"]:
            print(f"        dealbreaker: {f}", file=out)
    print("\nShoot the top one. If the top one is under 50, none of these are the hook.\n",
          file=out)


def main():
    ap = argparse.ArgumentParser(description="Score a Reel hook on five properties.")
    ap.add_argument("input", nargs="?", default="-", help="file with one hook per line, or -")
    ap.add_argument("--hook", help="score a single hook given on the command line")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.hook:
        lines = [args.hook]
    else:
        raw = sys.stdin.read() if args.input == "-" else open(args.input, encoding="utf-8").read()
        lines = [l.strip() for l in raw.splitlines() if l.strip()]
    if not lines:
        print("nothing to score", file=sys.stderr)
        sys.exit(2)

    payload = []
    for line in lines:
        results, overall, verdict, flags = run(line)
        payload.append({
            "hook": line,
            "checks": {k: {"score": round(v[0], 1), "detail": v[1]} for k, v in results.items()},
            "weakest": min(CHECKS, key=lambda c: results[c][0]),
            "flags": flags,
            "score": round(overall, 1),
            "verdict": verdict,
        })

    if args.json:
        print(json.dumps(payload if len(payload) > 1 else payload[0], indent=2, ensure_ascii=False))
        return

    if len(payload) == 1:
        results, overall, verdict, flags = run(lines[0])
        render_one(lines[0], results, overall, verdict, flags)
    else:
        render_table(sorted(payload, key=lambda r: -r["score"]))

    sys.exit(0 if max(p["score"] for p in payload) >= 70 else 1)


if __name__ == "__main__":
    main()
