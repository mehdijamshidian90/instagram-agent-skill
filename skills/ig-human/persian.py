"""
persian.py - the small amount of Persian (Farsi) knowledge every script in
this pack needs, kept in one file so they all agree.

Identical copies live in ig-human, ig-reel, ig-caption and ig-viral, so any
one skill folder still works when it is copied on its own. If you edit one,
copy it to the other three (tests/test_persian.py checks they match).

What it covers:
  - deciding whether a text is Persian
  - normalising the things that make the same Persian word look different to
    a regex: Arabic yeh and kaf, Persian and Arabic digits, the half-space
    (ZWNJ) versus a full space versus nothing, and "می" written apart
  - splitting Persian into words without breaking a word at its half-space
  - the half-space and direction-mark rules, which a humanizer must respect:
    in Persian these characters are spelling, not a machine fingerprint
"""

import re
import unicodedata

ZWNJ = "‌"           # نیم‌فاصله. Part of correct Persian spelling.
ZWJ = "‍"
RLM, LRM, ALM = "‏", "‎", "؜"

# Arabic-script letters, harakat and tatweel, minus punctuation and digits.
FA_CHARS = "ؠ-ؿف-ٰٟ-ۓەۮۯۺ-ۿـ"
FA_LETTER_RE = re.compile(f"[{FA_CHARS}]")
LATIN_LETTER_RE = re.compile(r"[A-Za-z]")

# A Persian word may contain half-spaces, but never starts or ends with one.
FA_WORD = f"[{FA_CHARS}](?:[{FA_CHARS}{ZWNJ}]*[{FA_CHARS}])?"
LATIN_WORD = r"[A-Za-z0-9$%'’-]+"
WORD_RE = re.compile(f"{FA_WORD}|{LATIN_WORD}")
FA_WORD_RE = re.compile(FA_WORD)

# Sentence ends, Persian question mark included. The Persian comma is not one.
SENT_END = ".!?؟"
SENT_RE = re.compile(f"[^{SENT_END}\\n]+[{SENT_END}]*")

DIGITS = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٬٫٪",
    "01234567890123456789,.%",
)
LETTERS = str.maketrans({
    "ي": "ی",   # Arabic yeh
    "ى": "ی",   # alef maksura
    "ك": "ک",   # Arabic kaf
    "ۀ": "ه",   # heh with yeh above -> heh, for matching only
    "ة": "ه",
    "ـ": None,   # tatweel, decorative stretching
})
HARAKAT_RE = re.compile("[ً-ٰٟ]")


def is_persian(text, threshold=0.3):
    """True when Persian letters are at least `threshold` of all letters."""
    fa = len(FA_LETTER_RE.findall(text))
    la = len(LATIN_LETTER_RE.findall(text))
    return fa >= 3 and fa / max(fa + la, 1) >= threshold


def has_rtl(text):
    return bool(FA_LETTER_RE.search(text))


def fix_letters(text):
    """Arabic yeh/kaf to Persian. Safe to apply to text you will publish."""
    return text.replace("ي", "ی").replace("ى", "ی").replace("ك", "ک")


def to_ascii_digits(text):
    return text.translate(DIGITS)


def normalize(text):
    """A matching key, never text to publish.

    Folds every way of writing the same Persian word onto one spelling:
    Arabic letters to Persian, Persian digits to ASCII, harakat removed,
    half-spaces removed, and the verb prefixes "می" and "نمی" joined to their
    verb whether they were written with a half-space, a space, or nothing.
    "می‌خوام", "می خوام" and "میخوام" all become "میخوام".
    """
    text = text.translate(DIGITS).translate(LETTERS)
    text = HARAKAT_RE.sub("", text)
    text = text.replace(ZWNJ, "")
    text = re.sub(f"(?<![{FA_CHARS}])(ن?می) (?=[{FA_CHARS}])", r"\1", text)
    # Plural and comparative suffixes written apart: "کتاب ها" -> "کتابها".
    text = re.sub(f"(?<=[{FA_CHARS}]) (ها|های|هایی|تر|ترین)(?![{FA_CHARS}])", r"\1", text)
    return text


def words(text):
    """Words in reading order. A half-space never splits a Persian word."""
    text = re.sub(r"(?<=\d),(?=\d)", "", to_ascii_digits(text))
    return WORD_RE.findall(text)


def norm_words(text):
    """Lower-cased, normalised word keys, for set lookups."""
    return [normalize(w).lower().strip("'’") for w in words(text)]


def keep_invisible(text, i):
    """Is the format character at text[i] doing a real job?

    - ZWNJ between two Persian letters is the half-space: correct spelling.
    - RLM / LRM / ALM and the isolate and embedding controls are how mixed
      Persian and English text is kept in the right order. Keep them whenever
      the text contains any right-to-left script.
    - ZWJ inside an emoji sequence is what makes it one emoji.
    Everything else of category Cf is the mechanical kind and can go.
    """
    c = text[i]
    prev_c = text[i - 1] if i > 0 else ""
    next_c = text[i + 1] if i + 1 < len(text) else ""
    if c == ZWNJ:
        return bool(prev_c and next_c and FA_LETTER_RE.match(prev_c)
                    and FA_LETTER_RE.match(next_c))
    if c in (RLM, LRM, ALM) or "‪" <= c <= "‮" or "⁦" <= c <= "⁩":
        return has_rtl(text)
    if c == ZWJ:
        def pictographic(ch):
            return bool(ch) and (unicodedata.category(ch) == "So" or ch == "️"
                                 or "\U0001f3fb" <= ch <= "\U0001f3ff")
        return pictographic(prev_c) and pictographic(next_c)
    return False


def flexible(phrase):
    """A regex for a Persian phrase that tolerates how people actually type it.

    Half-space, space or nothing between parts; Arabic or Persian yeh and kaf.
    """
    out = []
    for ch in phrase:
        if ch == ZWNJ:
            out.append(f"[{ZWNJ} ]?")
        elif ch == " ":
            out.append(f"[\\s{ZWNJ}]*")
        elif ch == "ی":
            out.append("[یيى]")
        elif ch == "ک":
            out.append("[کك]")
        else:
            out.append(re.escape(ch))
    return "".join(out)


def phrase_re(find, flags=re.IGNORECASE):
    """Whole-word regex for a lexicon entry in either language."""
    if has_rtl(find):
        body = flexible(find)
        return re.compile(f"(?<![{FA_CHARS}{ZWNJ}]){body}(?![{FA_CHARS}{ZWNJ}])", flags)
    return re.compile(r"\b" + re.escape(find).replace(r"\ ", r"\s+") + r"\b", flags)


# Spoken numbers. "یک" and "یه" are left out for the same reason "one" is in
# English: they are an article far more often than a quantity. "نه" is out
# because it is also "no".
SPOKEN_NUMBERS = {
    "دو", "سه", "چهار", "پنج", "شش", "شیش", "هفت", "هشت", "ده", "یازده",
    "دوازده", "پانزده", "پونزده", "بیست", "سی", "چهل", "پنجاه", "شصت",
    "هفتاد", "هشتاد", "نود", "صد", "دویست", "سیصد", "پانصد", "پونصد",
    "هزار", "میلیون", "میلیارد", "نصف", "نیم", "دوبرابر", "سهبرابر", "دهبرابر",
}
MONEY_WORDS = {
    "تومن", "تومان", "دلار", "ریال", "یورو", "درصد", "حقوق", "درآمد", "دراومد",
    "اجاره", "سود", "ضرر", "میلیونی", "میلیاردی", "دلاری", "قیمت", "پول",
}
# Words that look like a person ending but are ordinary nouns.
NOT_FIRST_PERSON = {"سیستم", "مردم", "آیتم", "الگوریتم", "گندم", "اتم", "ریتم", "سوم", "دوم",
                    "چهارم", "پنجم", "ششم", "هفتم", "هشتم", "نهم", "دهم", "کدوم", "کدام"}
NOT_MI_VERB = {"میلیون", "میلیونها", "میلیونی", "میلیارد", "میزان", "میدان", "میدون",
               "میان", "میهن", "میکروفون", "میوه", "میز", "میزبان", "میراث", "مینیمال",
               "میانگین", "میکس", "میم", "میمون", "میهمان", "میلی", "میتینگ"}


def concrete_markers(text):
    """Numbers, Persian number words, @handles and Latin-script names.

    In a Persian caption the English words are nearly always names: the tool,
    the phone, the app. That is exactly the kind of concrete thing a reader
    can check, so they count the way a capitalised name counts in English.
    """
    flat = to_ascii_digits(text)
    found = re.findall(r"\$\s?\d[\d,.]*|\b\d[\d,.]*%?", flat)
    found += re.findall(r"@[A-Za-z0-9_.]+", flat)
    keys = norm_words(text)
    found += [k for k in keys if k in SPOKEN_NUMBERS or k in MONEY_WORDS]
    if is_persian(text):
        found += sorted({w for w in re.findall(r"\b[A-Za-z][A-Za-z0-9.+-]*\b", flat)
                         if len(w) >= 3 or any(ch.isdigit() for ch in w)})
    return found


# Colloquial (spoken) Persian. Instagram Persian is written the way it is said,
# and text that never once drops into the spoken register reads like a press
# release. This is the Persian stand-in for counting English contractions.
COLLOQUIAL_WORDS = {
    "رو", "اینو", "اونو", "همینو", "چیو", "یه", "خب", "آره", "آخه", "دیگه",
    "واسه", "بهش", "ازش", "باهاش", "توش", "بهت", "بهتون", "برات", "براتون",
    "برام", "بهم", "بهمون", "اصلا", "اصن", "چیه", "کیه", "کجاس", "اینه", "اونه",
    "نمیدونم", "میدونی", "میدونین", "ببین", "ببینین", "بگم", "بگین", "هستش",
    "اونجا", "اینجوری", "اونجوری", "چجوری", "چطوری", "خیلیا", "همهشون", "یکیش",
}
PERSONAL_WORDS = {
    "من", "ما", "شما", "تو", "خودم", "خودمون", "خودت", "خودتون", "بهت",
    "بهتون", "برات", "براتون", "برام", "بهم", "بهمون", "مال", "باهات", "باهاتون",
}
_FA = "\u0622-\u06cc"
COLLOQ_VERB_RE = re.compile(f"^ن?(?:می|ب)[{_FA}]{{1,10}}(?:ه|ین|ن)$")
PERSONAL_VERB_RE = re.compile(f"^ن?می[{_FA}]{{1,10}}(?:م|یم|ی|ین|ید)$")
PAST_FIRST_RE = re.compile(f"^[{_FA}]{{2,}}(?:تم|دم|تیم|دیم)$")


def colloquial_count(text):
    n = 0
    for k in norm_words(text):
        if k in COLLOQUIAL_WORDS:
            n += 1
        elif k.startswith("می") and k not in NOT_MI_VERB and COLLOQ_VERB_RE.match(k):
            n += 1
    return n


def personal_count(text):
    n = 0
    for k in norm_words(text):
        if k in PERSONAL_WORDS:
            n += 1
        elif k not in NOT_MI_VERB and PERSONAL_VERB_RE.match(k):
            n += 1
        elif k not in NOT_FIRST_PERSON and PAST_FIRST_RE.match(k):
            n += 1
    return n


def first_strong(line):
    """'rtl', 'ltr' or None: the direction Instagram will give this line."""
    for ch in line:
        if ch in (RLM, ALM):
            return "rtl"
        if ch == LRM:
            return "ltr"
        d = unicodedata.bidirectional(ch)
        if d in ("R", "AL"):
            return "rtl"
        if d == "L":
            return "ltr"
    return None


def last_strong(line):
    return first_strong(line[::-1])
