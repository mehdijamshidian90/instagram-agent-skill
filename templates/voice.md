# voice.md

Copy this to `~/.claude/instagram/voice.md` and fill it in. Every skill in the
pack reads it. Ten minutes here is the difference between scripts you shoot and
scripts you rewrite.

If you would rather not fill it in by hand, send Claude three of your own reels
or captions and say "write my voice.md from these". That works better than
guessing at the answers.

This file matters more on Instagram than anywhere else, because you have to say
the words out loud. A line you would never say is not a draft, it is a retake.

---

## Who I am

- **Name:**
- **Handle:**
- **What I do, in one sentence:**
- **Who I am talking to:** (be specific: "photographers charging under $2,000",
  not "creatives")
- **What I sell:**

## What I sound like

- **Three of my own reels or captions that sound most like me:** (paste them)
- **On camera I am:** (fast and loud / dry / calm / funny / deadpan)
- **Words I actually use:**
- **Words I would never say out loud:**
- **Do I swear:** (yes / mild / no)
- **Emoji in captions:** (never / one, rarely / freely)
- **Face on camera:** (always / sometimes / faceless)
- **Voiceover or to-camera:**
- **Pace:** (words per minute, if you have timed yourself reading a script.
  `beats.py --wpm` uses this. Most people are between 150 and 200.)

## Language

- **I post in:** (English / Persian / both - which posts in which)
- **Register:** (Persian: colloquial محاوره / formal رسمی / colloquial on camera,
  formal in captions)
- **Digits:** (Persian: ۱۲۳ / Latin: 123)
- **Brand and tool names:** (keep in Latin script: ChatGPT / write in Persian:
  چت‌جی‌پی‌تی)

### If I post in Persian, every skill follows these

1. **Write it the way it is said.** Reels and captions are colloquial unless the
   register above says formal: "می‌خوام"، "رو"، "یه"، "نمی‌دونستم". Never mix
   registers in one line ("می‌خواهم بهت بگم").
2. **Half-spaces are spelling.** Use the half-space (نیم‌فاصله) wherever Persian
   needs one: "می‌خوام"، "کتاب‌ها"، "سریع‌تر"، "خونه‌ام". Not a full space, not
   nothing. `humanize.py` keeps them.
3. **No line starts or ends with an English word.** Instagram sets each line's
   direction from its first letter, so "ChatGPT دیگه رایگانه" comes out
   scrambled. Write "دیگه ChatGPT رایگانه". This holds for captions, bios,
   comments, DMs and on-screen text. `caption.py` checks it.
4. **Persian letters and punctuation.** ی and ک, never Arabic ي and ك. The
   Persian comma "،" and question mark "؟". Quotes are «».
5. **One kind of digit.** Whatever the Digits line above says, in every number,
   in every slide.
6. **No Finglish** in anything that gets published.
7. **Do not translate English drafts.** A translated hook keeps the English
   rhythm and sounds dubbed. Write the Persian version from the Persian
   template in `hooks.json`.
8. **Hashtags** join words with an underscore: `#هوش_مصنوعی`. Five at most.

## My positions

Three to five things I believe that some of my audience does not. These are
where the good reels come from.

1.
2.
3.

## Off limits

- **Topics I do not post about:**
- **Clients, numbers or names I cannot say publicly:**
- **Claims I am not allowed to make:** (regulated industry, employer policy, NDA)

## Proof I can use

Real numbers, outcomes and stories I am happy to put my name on. The skills will
never invent one, so if this section is empty, every draft comes back with
`{{your number}}` in it.

-
-
-

## The ask

- **My keyword CTA, if I use one:** (one word, sayable, no spaces)
- **What the keyword sends them:**
- **Where my link goes:**
