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

ZWNJ = "\u200c"           # نیم‌فاصله. Part of correct Persian spelling.
ZWJ = "\u200d"
RLM, LRM, ALM = "\u200f", "\u200e", "\u061c"

# Arabic-script letters, harakat and tatweel, minus punctuation and digits.
FA_CHARS = "\u0620-\u063f\u0641-\u065f\u0670-\u06d3\u06d5\u06ee\u06ef\u06fa-\u06ff\u0640"
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
    "\u0640": None,   # tatweel, decorative stretching
})
HARAKAT_RE = re.compile("[\u064b-\u065f\u0670]")


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
    if c in (RLM, LRM, ALM) or "\u202a" <= c <= "\u202e" or "\u2066" <= c <= "\u2069":
        return has_rtl(text)
    if c == ZWJ:
        def pictographic(ch):
            return bool(ch) and (unicodedata.category(ch) == "So" or ch == "\ufe0f"
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
    "تو",   # colloquial both as "you" and as "in" (formal: شما / در)
}
_FA = "\u0622-\u06cc"
COLLOQ_VERB_RE = re.compile(f"^ن?می[{_FA}]{{1,10}}(?:ه|ین|ن)$")


# ------------------------------------------------------------- person --
# Who is speaking to whom. English has "I" and "you" as separate words;
# Persian mostly carries person on the end of a word: "گوشیم" is "my phone",
# "زندگیتو" is "your life", "داریم" is "we have". A suffix like "م" is also the
# last letter of hundreds of ordinary nouns (تمام، پیام، فیلم، تصمیم), so each
# rule below only fires where the ending is reliable, and each has a stop list
# of the common words it would otherwise catch. All lists are normalised: no
# half-spaces, Persian yeh and kaf.

FIRST_WORDS = {"من", "ما", "خودم", "خودمون", "برام", "برامون", "بهم", "بهمون",
               "ازم", "باهام", "باهامون"}
SECOND_WORDS = {"شما", "خودت", "خودتون", "بهت", "بهتون", "برات", "براتون",
                "باهات", "باهاتون", "ازت", "ازتون"}
# "تو" is left out on purpose: in spoken Persian it is "in" as often as "you".
# The verb after it carries the person when it means "you".
PERSONAL_WORDS = FIRST_WORDS | SECOND_WORDS

# Everyday things people say "my ..." and "your ..." about on Instagram. A word
# from this list plus a person ending ("کارم", "اکانتت", "پیجمون", "پولمو") is
# possessive. Nouns ending in ی (گوشی، زندگی) are covered by the یم / یت rules
# instead, and nouns ending in ه by the half-space rule ("خونه‌ام").
POSSESSABLE = {
    "کار", "پول", "وقت", "اکانت", "پیج", "حساب", "دوست", "رئیس", "همکار", "شوهر",
    "زن", "مامان", "بابا", "داداش", "خواهر", "برادر", "پسر", "دختر", "خانواده",
    "ماشین", "لپتاپ", "سیستم", "اسم", "سن", "حقوق", "درآمد", "دراومد", "شغل",
    "بیزنس", "استارتاپ", "قرارداد", "فیلم", "عکس", "پست", "ویدیو", "ویدئو",
    "کانال", "فالوور", "پیام", "ایمیل", "دایرکت", "سایت", "اپ", "مغز", "دست",
    "سر", "چشم", "دل", "ذهن", "روز", "شب", "عمر", "مدیر", "استاد", "معلم",
    "مانیتور", "هدفون", "ساعت", "کیف", "کمد", "اتاق", "تخت", "بدن", "پوست",
    "صدا", "حرف", "سوال", "جواب", "نظر", "ایده", "هدف", "برنامه", "پروفایل",
    "بایو", "کامنت", "ریلز", "استوری", "لایو", "پادکست",
    # nouns ending in ی take the ending directly: گوشیت، زندگیتو
    "گوشی", "زندگی", "مشتری", "صندلی", "بازی",
}
POSSESSABLE = {w.replace(ZWNJ, "") for w in POSSESSABLE}
FIRST_ENDINGS = ("مونو", "مون", "مو", "م")
SECOND_ENDINGS = ("تونو", "تون", "تو", "ت")
# Words that end like "my ..." / "your ..." but are one word.
NOT_FIRST = {
    "سیستم", "مردم", "آیتم", "الگوریتم", "گندم", "اتم", "ریتم", "مقدم", "سوم",
    "دوم", "چهارم", "پنجم", "ششم", "هفتم", "هشتم", "نهم", "دهم", "کدوم", "کدام",
    # ...یم that is not "my" or "we"
    "تیم", "تصمیم", "تنظیم", "قدیم", "مستقیم", "عظیم", "رژیم", "تحریم", "تقسیم",
    "تقدیم", "تسلیم", "تعمیم", "ترسیم", "ترمیم", "سیم", "نسیم", "حریم", "کریم",
    "اقلیم", "تعلیم", "رحیم", "حکیم", "ابراهیم", "مریم", "جحیم", "تقویم",
    "تحکیم", "تفهیم", "تکریم", "تجسیم", "تعظیم", "حجیم", "فهیم", "سهیم", "یتیم",
    "ضخیم", "پریم", "تقدم", "مستخدم", "منهدم", "متصادم", "متقدم",
    "بیستم", "دویستم", "سیصدم", "چهارصدم", "پانصدم", "پونصدم", "ششصدم",
    "هفتصدم", "هشتصدم", "نهصدم",
    # ...هام that is not "my ...s"
    "الهام", "ابهام", "سهام", "اتهام", "اوهام", "افهام", "استفهام", "ایهام",
}
NOT_SECOND = {
    "کارت",      # card
    "کارتون",    # cartoon
    "سنت",       # tradition
    # ...هات that is not "your ...s"
    "اشتباهات", "جهات", "توجهات", "شبهات", "مباهات", "تشابهات",
}
PERSONAL_VERB_1 = re.compile(f"^ن?می[{_FA}]{{1,10}}(?:م|یم)$")
PERSONAL_VERB_2 = re.compile(f"^ن?می[{_FA}]{{1,10}}(?:ی|ین|ید)$")
PAST_FIRST_RE = re.compile(f"^[{_FA}]{{2,}}(?:تم|دم|تیم|دیم)$")
WE_VERB_RE = re.compile(f"^(?:ن?(?:داریم|هستیم)|نیستیم|ن?ب[{_FA}]{{1,8}}یم)$")
NOT_FIRST_PERSON = NOT_FIRST    # older name, kept for anything importing it


def person_of(raw):
    """1 for a first-person word, 2 for second person, None for neither.

    `raw` is one token as persian.words() returns it, half-spaces included:
    the half-space is the most reliable signal there is ("خونه‌ام", "کتاب‌هات").
    """
    k = normalize(raw).lower()
    if k in FIRST_WORDS:
        return 1
    if k in SECOND_WORDS:
        return 2
    # After a half-space the ending is unambiguous.
    tail = raw.translate(LETTERS).split(ZWNJ)[-1] if ZWNJ in raw else None
    if tail in ("ام", "م", "هام", "امو", "مو", "مون", "امون"):
        return 1
    if tail in ("ات", "ت", "هات", "اتو", "تو", "تون", "اتون"):
        return 2
    if k not in NOT_MI_VERB:
        if PERSONAL_VERB_1.match(k):
            return 1
        if PERSONAL_VERB_2.match(k):
            return 2
    if k in NOT_FIRST or k in NOT_SECOND:
        return None
    for end in FIRST_ENDINGS:
        if k.endswith(end) and k[:-len(end)] in POSSESSABLE:
            return 1
    for end in SECOND_ENDINGS:
        if k.endswith(end) and k[:-len(end)] in POSSESSABLE:
            return 2
    # "...یم" on its own is not safe: loanwords end that way too (استریم، تیم،
    # رژیم). Only the verb shapes: "داریم"، "هستیم" and the subjunctive "بریم".
    if WE_VERB_RE.match(k):
        return 1
    if len(k) >= 5 and k.endswith("هام"):                          # قراردادهام، پستهام
        return 1
    if len(k) >= 5 and (k.endswith("هات") or k.endswith("هاتو")):  # ویدیوهات
        return 2
    if PAST_FIRST_RE.match(k):                                      # خوندم، داشتیم
        return 1
    return None


def persons(text):
    """The set of grammatical persons that occur in a text, from {1, 2}."""
    return {p for p in (person_of(w) for w in words(text)) if p}


def colloquial_count(text):
    n = 0
    for k in norm_words(text):
        if k in COLLOQUIAL_WORDS:
            n += 1
        elif k not in NOT_MI_VERB and COLLOQ_VERB_RE.match(k):
            n += 1
    return n


def personal_count(text):
    return sum(1 for w in words(text) if person_of(w))


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
