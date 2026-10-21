#!/usr/bin/env python3
"""
Tests for the Persian (Farsi) support, and a regression check that English
output is unchanged. No dependencies: run it with plain python3.

    python3 tests/test_persian.py
"""

import filecmp
import importlib.util
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(ROOT, "skills")
Z = "\u200c"          # half-space


def load(folder, name):
    path = os.path.join(SKILLS, folder)
    if path not in sys.path:
        sys.path.insert(0, path)
    spec = importlib.util.spec_from_file_location(f"{folder}_{name}", os.path.join(path, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


humanize = load("ig-human", "humanize")
detect = load("ig-human", "detect")
hookscore = load("ig-reel", "hookscore")
beats = load("ig-reel", "beats")
caption = load("ig-caption", "caption")
swipe = load("ig-viral", "swipe")
LEX = humanize.load_lexicon()

TESTS = []


def test(fn):
    TESTS.append(fn)
    return fn


# ------------------------------------------------------------------ shared --

@test
def persian_copies_are_identical():
    master = os.path.join(SKILLS, "ig-human", "persian.py")
    for folder in ("ig-reel", "ig-caption", "ig-viral"):
        assert filecmp.cmp(master, os.path.join(SKILLS, folder, "persian.py"), shallow=False), folder


@test
def normalize_folds_spellings():
    p = humanize.persian
    assert p.normalize(f"می{Z}خوام") == p.normalize("می خوام") == p.normalize("میخوام") == "میخوام"
    assert p.normalize("كتابي ۱۲") == "کتابی 12"
    assert p.words(f"من می{Z}خوام کتاب{Z}ها رو بخونم") == ["من", f"می{Z}خوام", f"کتاب{Z}ها", "رو", "بخونم"]


# --------------------------------------------------------------- humanizer --

@test
def humanize_keeps_half_spaces():
    text = f"من می{Z}خوام این کتاب{Z}ها رو سریع{Z}تر بخونم.\n"
    out, report = humanize.humanize(text, LEX)
    assert out == text, out
    kept = [h for h in report["invisible"] if h["action"] == "kept"]
    assert kept and kept[0]["count"] == 3


@test
def humanize_removes_stray_and_doubled_half_spaces():
    out, _ = humanize.humanize(f"سریع{Z}{Z}تر {Z}میشه\u200b.\n", LEX)
    assert out == f"سریع{Z}تر میشه.\n", repr(out)


@test
def humanize_still_strips_half_space_in_english():
    out, _ = humanize.humanize(f"plain{Z}text here.\n", LEX)
    assert Z not in out


@test
def humanize_keeps_direction_marks_only_in_rtl_text():
    out, _ = humanize.humanize("\u200fiPhone 17 هم اومد.\n", LEX)
    assert out.startswith("\u200f")
    out, _ = humanize.humanize("\u200fiPhone 17 is out.\n", LEX)
    assert "\u200f" not in out


@test
def humanize_keeps_emoji_joiner():
    out, _ = humanize.humanize("done \U0001F468\u200d\U0001F4BB\n", LEX)
    assert "\u200d" in out


@test
def humanize_persian_typography():
    out, _ = humanize.humanize("اين ابزار “رايگان” است — و خوب.\n", LEX)
    assert out == "این ابزار «رایگان» است، و خوب.\n", out


@test
def humanize_persian_lexicon_any_spacing():
    for verb in (f"می{Z}باشد", "میباشد", "می باشد"):
        out, _ = humanize.humanize(f"این ابزار رایگان {verb}.\n", LEX)
        assert out == "این ابزار رایگان است.\n", (verb, out)
    out, _ = humanize.humanize("در دنیای امروز، هوش مصنوعی همه جا هست.\n", LEX)
    assert out == "هوش مصنوعی همه جا هست.\n", out


@test
def humanize_flags_persian_structures():
    _, report = humanize.humanize("هوش مصنوعی فقط یک ابزار نیست، بلکه یک انقلاب است.\n", LEX)
    assert any("فقط یک" in s["name"] for s in report["structures"])


# ---------------------------------------------------------------- detector --

@test
def detect_half_spaces_are_not_fingerprint():
    score, _ = detect.check_fingerprint(f"من می{Z}خوام کتاب{Z}ها رو بخونم و بعد می{Z}رم.")
    assert score == 100.0


@test
def detect_counts_persian_words_and_colloquial_voice():
    text = ("دیروز سه ساعت وقت گذاشتم که با Claude یه اسکریپت بنویسم. "
            f"کاری که هر هفته ۴۰ دقیقه وقتمو می{Z}گرفت الان ۲ دقیقه{Z}ست. "
            f"راستش اولش فکر می{Z}کردم جواب نمیده و اشتباه می{Z}کردم. "
            "اگه خواستی امتحانش کن و بهم بگو کجاش گیر کرد.")
    assert len(detect.words(text)) > 30
    score, detail = detect.check_voice(text, LEX)
    assert score >= 80, detail
    score, detail = detect.check_specificity(text)
    assert score >= 70, detail


# -------------------------------------------------------------- hook score --

@test
def english_hook_scores_match_readme():
    expected = {
        "Nobody tells you that your first 30 reels are supposed to flop.": 85.6,
        "I lost $18,000 because of one missing contract.": 81.4,
        "Stop scrolling if you want to grow on Instagram in 2026 \U0001F525": 54.4,
        "Hey guys, today I wanted to talk about content strategy": 9.6,
    }
    for hook, want in expected.items():
        _, overall, _, _ = hookscore.run(hook)
        assert round(overall, 1) == want, (hook, overall)


@test
def persian_hooks_rank_sensibly():
    strong = f"هیچ{Z}کس بهت نمی{Z}گه که ۳۰ تا ریلز اولت قراره فلاپ بشه."
    weak = f"سلام دوستان، امروز می{Z}خوام درباره هوش مصنوعی صحبت کنم"
    _, s_score, s_verdict, s_flags = hookscore.run(strong)
    _, w_score, w_verdict, w_flags = hookscore.run(weak)
    assert s_verdict == "STRONG" and not s_flags, (s_score, s_flags)
    assert w_verdict == "WEAK" and len(w_flags) >= 2, (w_score, w_flags)


# ------------------------------------------------------------ hooks.json --

@test
def every_persian_example_classifies_as_its_own_formula():
    formulas = swipe.load_formulas(swipe.HOOKS)
    hooks = json.load(open(swipe.HOOKS, encoding="utf-8"))["hooks"]
    for h in hooks:
        for field in ("template_fa", "example_fa", "on_screen_fa", "match_fa"):
            assert h.get(field), (h["id"], field)
        fid, _ = swipe.classify(h["example_fa"], formulas)
        assert fid == h["id"], (h["id"], fid, h["example_fa"])


# ------------------------------------------------------------------ beats --

@test
def beats_times_persian():
    a = beats.analyse("۱۸ میلیون تومن ضرر کردم.\nهمین یه کلمه برام ۱۸ میلیون می\u200cارزید.\n")
    assert a["total_words"] == 12, a["total_words"]
    assert any("Loops" in n for n in a["notes"])


# ---------------------------------------------------------------- caption --

@test
def caption_catches_direction_and_counts_persian_tags():
    text = ("ChatGPT دیگه لازم نیست، این ابزار رایگانه.\n"
            "کلمه «ابزار» رو کامنت کن.\n"
            "#هوش_مصنوعی #تکنولوژی #اکسپلور")
    a = caption.analyse(text)
    status = {c["check"]: c["status"] for c in a["checks"]}
    assert status["DIRECTION"] == "FAIL"
    assert len(a["hashtags"]) == 3
    assert a["asks"] == ["comment a keyword"]


@test
def caption_passes_clean_persian():
    text = ("دیگه ChatGPT لازم نیست، این ابزار رایگانه.\n"
            "کلمه «ابزار» رو کامنت کن تا لینکشو بفرستم.\n"
            "#هوش_مصنوعی #تکنولوژی")
    status = {c["check"]: c["status"] for c in caption.analyse(text)["checks"]}
    assert status["DIRECTION"] == "PASS" and status["LETTERS"] == "PASS"


@test
def caption_english_unchanged():
    a = caption.analyse("I lost $18,000 on one clause.\n\nSave this.\n#freelance")
    assert [c["check"] for c in a["checks"]] == [
        "LENGTH", "FIRST LINE", "HOOK IS CONCRETE", "HASHTAGS", "TAG PLACEMENT",
        "LINKS", "ONE ASK", "EMOJI"]


# ------------------------------------------------------------------ swipe --

@test
def swipe_parses_instagram_counts():
    cases = {"412000": 412000, "412,000": 412000, "412K": 412000, "1.2M": 1200000,
             "۴۱۲٬۰۰۰": 412000, "۴۱۲ هزار": 412000, "۱٫۲ میلیون": 1200000, "": None}
    for cell, want in cases.items():
        assert swipe.parse_count(cell) == want, (cell, swipe.parse_count(cell))


# ------------------------------------------------------- review regressions --

@test
def humanize_pairs_quotes_in_reading_order():
    for text in ("این “رایگان” است.\n", "این ”رایگان“ است.\n"):
        out, _ = humanize.humanize(text, LEX)
        assert out == "این «رایگان» است.\n", out


@test
def trailing_comma_keeps_paragraph_break():
    out, _ = humanize.humanize("اول این،\n\nبعد اون.\n", LEX)
    assert out == "اول این\n\nبعد اون.\n", repr(out)
    out, _ = humanize.humanize("Hello,\n\nWorld is here.\n", LEX)
    assert out == "Hello\n\nWorld is here.\n", repr(out)


@test
def ambiguous_phrase_left_alone():
    out, _ = humanize.humanize("در جهت مخالف رفت.\n", LEX)
    assert out == "در جهت مخالف رفت.\n", out


@test
def to_meaning_in_is_not_second_person():
    r, _, _, _ = hookscore.run("این ابزار رایگان جای ۳ تا اپ رو تو گوشیم گرفت.")
    assert r["ADDRESS"][1] != "speaks to the viewer", r["ADDRESS"]


@test
def news_hook_with_emruz_is_not_a_preamble():
    _, _, _, flags = hookscore.run("امروز قراره اپل آیفون ۱۸ رو معرفی کنه")
    assert not flags, flags
    _, _, _, flags = hookscore.run("امروز می\u200cخوام بهتون یه ترفند نشون بدم")
    assert flags, "real preamble missed"


@test
def stake_stems_do_not_match_unrelated_words():
    r, _, _, _ = hookscore.run("بند ۴ قراردادم رو بنویس")
    assert "بند" not in r["STAKES"][1], r["STAKES"]
    r, _, _, _ = hookscore.run("این قرارداد رو نخون، بنویسش")
    assert "نخون" in r["STAKES"][1], r["STAKES"]


@test
def caption_asks_are_not_triggered_by_lookalikes():
    cases = {
        "کلمه «ابزار» رو کامنت کن تا لینکشو بفرستم.": ["comment a keyword"],
        "نظرتون رو کامنت کنید.": ["answer a question"],
        "به فالوکنندگان جدید خوش اومدید.": [],
        "اینو برای دوستت بفرست.": ["share this"],
        "سیوش کن که بعدا لازمت میشه.": ["save this"],
        "این ابزار وقتمو ذخیره کرد.": [],
    }
    for text, want in cases.items():
        assert caption.analyse(text)["asks"] == want, (text, caption.analyse(text)["asks"])


@test
def caption_keywords_ignore_half_space_and_space():
    a = caption.analyse("دیگه ChatGPT لازم نیست.\nهوش\u200cمصنوعی رو یاد بگیر.", keywords=["هوش مصنوعی"])
    status = {c["check"]: c["status"] for c in a["checks"]}
    assert status["SEARCH TERMS"] == "PASS"


@test
def swipe_parses_spaced_and_decimal_comma_counts():
    assert swipe.parse_count("1 234") == 1234
    assert swipe.parse_count("1,2K") == 1200
    assert swipe.parse_count("1,200K") == 1200000


@test
def code_has_no_hidden_bidi_characters():
    import glob
    bidi = set(range(0x202A, 0x202F)) | set(range(0x2066, 0x206A)) | {0x200E, 0x200F, 0x061C}
    for path in glob.glob(os.path.join(ROOT, "**", "*.py"), recursive=True):
        text = open(path, encoding="utf-8").read()
        assert not any(ord(c) in bidi for c in text), path


def main():
    failed = 0
    for fn in TESTS:
        try:
            fn()
            print(f"  ok    {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {fn.__name__}: {e}")
    print(f"\n{len(TESTS) - failed}/{len(TESTS)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
