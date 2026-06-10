"""
OmniGate Helper Userbot  (v4)
- DM only (silent in groups/channels)
- FIRST contact: clearly explains what this account is and how it works
- Afterwards: smart keyword replies, non-repeating, varied
- All replies are about OmniGate / pending requests / access (English)

⚠️ NOTE: This runs automation on a USER account, which Telegram's ToS restricts.
   Use a SECONDARY / throwaway account only. Auto-react raises ban risk the most —
   it is OFF by default (set AUTO_REACT=1 only if you accept the risk).
"""

import os
import re
import time
import asyncio
import random
import logging
from collections import defaultdict

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import ReactionEmoji
from telethon.tl.functions.messages import SendReactionRequest

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
log = logging.getLogger("userbot")

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION_STRING = os.environ.get("SESSION_STRING", "")

# Auto-react is OFF by default — it is the biggest ban-risk signal on a user account.
AUTO_REACT = os.environ.get("AUTO_REACT", "0") == "1"
REACT_CHANCE = float(os.environ.get("REACT_CHANCE", "0.5"))
REPLY_COOLDOWN = int(os.environ.get("REPLY_COOLDOWN", "30"))

# ── Gemini AI (optional) ──────────────────────────────────────────────
# Uses the SAME key as the main bot. If unset, fails, or is rate-limited, the
# userbot automatically falls back to the keyword replies below.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

# Persona/grounding the AI must stay within. Keeps answers accurate & on-topic.
AI_SYSTEM_PROMPT = (
    "You are the 'OmniGate Helper', a friendly assistant that works alongside the main "
    "Telegram bot @omnigatebot. You are talking in DM to a GROUP/CHANNEL ADMIN.\n\n"
    "WHO YOU ARE:\n"
    "- You were auto-added to help clear a large backlog of OLD pending join requests "
    "(from before OmniGate was set up). You accept those old pending requests automatically, "
    "which the main bot cannot do on its own.\n"
    "- You are SAFE: you only approve users who already requested to join. You never change "
    "the admin's settings, never ask for passwords, login codes, or payment.\n\n"
    "STRICT TOPIC LOCK — THIS IS YOUR MOST IMPORTANT RULE:\n"
    "You ONLY talk about OmniGate (@omnigatebot): join requests, pending requests, access, "
    "approvals, safety of this process, and the two commands below. NOTHING ELSE.\n"
    "If the user asks about ANYTHING outside OmniGate — general knowledge, coding, math, news, "
    "advice, jokes, other apps, personal questions, 'what can you do', 'who are you' beyond your "
    "OmniGate role, etc. — you MUST politely REFUSE and redirect. Do NOT answer the off-topic part "
    "at all, not even briefly. Always bring it back to OmniGate.\n"
    "Example refusal: 'I can only help with OmniGate and your group's join requests. Is there "
    "anything about OmniGate or your pending members I can help with?'\n\n"
    "COMMANDS the admin can send you in this chat:\n"
    "- /autoacceptoff  -> stop auto-accepting old pending requests\n"
    "- /autoaccepton   -> resume auto-accepting\n\n"
    "RULES:\n"
    "- ALWAYS reply in ENGLISH only, regardless of what language the user writes in. "
    "Never reply in Tagalog or any other language.\n"
    "- Keep replies SHORT (1-3 sentences), warm, and clear.\n"
    "- Stay 100% on OmniGate. When in doubt whether something is on-topic, treat it as off-topic "
    "and redirect.\n"
    "- For detailed OmniGate features/pricing/settings: give a brief answer and point to the main "
    "bot @omnigatebot. Do NOT invent specifics, prices, or settings.\n"
    "- Never claim to be a human. Never ask for passwords, codes, or payment.\n"
    "- Plain text only. No markdown, no code blocks."
)

REACTION_POOL = ["\U0001F44D", "\U0001F525", "\U0001F44C", "\u2764\uFE0F",
                 "\U0001F389", "\U0001F60A", "\U0001F44F", "\u2728",
                 "\U0001F60D", "\U0001F4AF", "\U0001F64C", "\U0001F914"]

# ── FIRST-CONTACT INTRO ───────────────────────────────────────────────
# Shown the FIRST time a user ever messages this account. Explains what it is
# and how it works, so people aren't confused about who they're talking to.
INTRO_MESSAGES = [
    (
        "\U0001F44B Hi! This is the <b>OmniGate Helper</b>, working alongside the main bot "
        "<b>@omnigatebot</b>.\n\n"
        "I was added to help clear the <b>large backlog of old pending join requests</b> in your "
        "group or channel \u2014 the ones from before OmniGate was set up. I accept them "
        "<b>automatically</b>, which the main bot can't do on its own.\n\n"
        "\U0001F512 <b>This is completely safe.</b> I only approve people who already requested to "
        "join. I never touch your settings, never ask for codes or payment, and your account is "
        "never at risk.\n\n"
        "\u2699\uFE0F <b>Commands (send here in this chat):</b>\n"
        "\u2022 <code>/autoacceptoff</code> \u2014 stop auto-accepting old pending requests\n"
        "\u2022 <code>/autoaccepton</code> \u2014 resume auto-accepting\n\n"
        "Any OmniGate questions? Just ask."
    ),
    (
        "\U0001F916 Hello! You've reached the <b>OmniGate Helper</b>, the companion to "
        "<b>@omnigatebot</b>.\n\n"
        "Your group/channel had a <b>big backlog of old pending requests</b> (from before OmniGate), "
        "so I was added to <b>accept them automatically</b> \u2014 something the main bot can't do for "
        "older requests on its own.\n\n"
        "\U0001F512 <b>100% safe:</b> I only approve users who already asked to join. I never change "
        "your settings, never ask for logins, codes, or money, and your account stays perfectly safe.\n\n"
        "\u2699\uFE0F <b>Commands (just send them here):</b>\n"
        "\u2022 <code>/autoacceptoff</code> \u2014 turn OFF auto-accept\n"
        "\u2022 <code>/autoaccepton</code> \u2014 turn it back ON\n\n"
        "Feel free to ask any OmniGate question."
    ),
]

KEYWORD_RULES = [
    {
        "name": "greeting",
        "patterns": [r"\bhi\b", r"\bhello\b", r"\bhey\b", r"\byo\b",
                     r"good (morning|afternoon|evening)"],
        "replies": [
            "Hey there! \U0001F44B Your join request is being processed \u2014 you'll be approved automatically.",
            "Hi! Your pending request is in the queue and will be accepted shortly. \u2705",
            "Hello! No action needed on your end \u2014 your request gets approved for you. \U0001F64C",
        ],
    },
    {
        "name": "join_pending",
        "patterns": [r"\bjoin\b", r"\baccept", r"\bpending\b", r"\brequest\b",
                     r"\bapprove", r"\bwait", r"how long", r"\bqueue\b",
                     r"how (do|can) i (get in|join)", r"let me in", r"not in yet",
                     r"still waiting"],
        "replies": [
            "Your join request gets approved automatically \u2014 usually within a short while. No need to re-send. \u2705",
            "You're already in the queue. Older pending requests get cleared automatically, so just hold on. \U0001F44D",
            "No worries \u2014 pending requests are accepted for you. Give it a bit and you'll be in. \U0001F3AC",
            "It's all automated. Your request will go through; please don't cancel or re-request.",
            "It's being handled \u2014 approvals happen automatically, including older pending requests. \u23F3",
        ],
    },
    {
        "name": "denied_problem",
        "patterns": [r"\bdenied\b", r"\brejected\b", r"\bdeclined\b", r"\bblocked\b",
                     r"can'?t (join|get in)", r"not working", r"\bstuck\b", r"\berror\b"],
        "replies": [
            "If you're still not in after a while, try sending the join request again \u2014 it'll be picked up automatically.",
            "Sometimes it takes a moment. If it's been long, re-request once and it should clear. \U0001F44D",
            "No problem \u2014 re-send the join request and it'll be processed. Let me know if it still doesn't work.",
        ],
    },
    {
        "name": "what_is_this",
        "patterns": [r"what (is|are) (this|you)", r"\bwho are you\b", r"\bbot\b",
                     r"\bautomated\b", r"\bomnigate\b", r"\bhelper\b", r"how (does|do) (this|you) work"],
        "replies": [
            "This account is the <b>OmniGate Helper</b> \u2014 an automated assistant that clears pending join "
            "requests (including older ones) so members get in without a manual approval. \U0001F916",
            "I'm the OmniGate Helper \u2014 I make sure pending requests get accepted automatically. \u2705",
            "Automated helper here! My job is to clear pending join requests so members get in smoothly.",
        ],
    },
    {
        "name": "safety_worry",
        "patterns": [r"\bsafe\b", r"\bscam\b", r"\blegit\b", r"\bscammer\b", r"\bfake\b",
                     r"\bvirus\b", r"\bhack", r"\bsteal", r"\bsuspicious\b", r"\btrust\b",
                     r"is this real", r"are you real", r"\bphishing\b", r"\bsketchy\b"],
        "replies": [
            "\U0001F512 Totally understandable to check! Yes \u2014 this is safe. Getting approved here is the "
            "normal, official join process for @omnigatebot. I never ask for passwords, codes, or payment, "
            "and your account is never at risk. You're simply being let into the group/channel. \u2705",
            "\U0001F512 Good question \u2014 and yes, it's completely safe. I only accept pending join requests; "
            "I'll never ask for your login, a code, or money. This is the same approval an admin would do, "
            "just automatic. \u2705",
            "No worries at all \u2014 this is legitimate. The OmniGate Helper only approves join requests for "
            "@omnigatebot. Nothing is required from you and nothing about your account changes. \U0001F64C",
        ],
    },
    {
        "name": "help",
        "patterns": [r"\bhelp\b", r"\bsupport\b", r"\bproblem\b",
                     r"\bissue\b", r"\bconcern\b", r"\bask\b", r"\bquestion\b"],
        "replies": [
            "\u2699\uFE0F <b>OmniGate Helper commands:</b>\n"
            "\u2022 <code>/autoacceptoff</code> \u2014 stop auto-accepting old pending requests\n"
            "\u2022 <code>/autoaccepton</code> \u2014 resume auto-accepting\n\n"
            "If it's about a join request, it's handled automatically. For anything else about "
            "@omnigatebot, just ask. \U0001F64F",
            "Happy to help! \u2699\uFE0F You can send <code>/autoacceptoff</code> to stop auto-accepting, "
            "or <code>/autoaccepton</code> to resume. Anything else about OmniGate \u2014 ask away.",
            "Sure \u2014 the main commands are <code>/autoacceptoff</code> and <code>/autoaccepton</code>. "
            "For other OmniGate questions, the admin tools live in @omnigatebot. \U0001F64C",
        ],
    },
    {
        "name": "thanks",
        "patterns": [r"\bthank", r"\bthanks\b", r"\bty\b",
                     r"\bappreciate", r"\bnice\b", r"\bgreat\b", r"\bok\b", r"\bokay\b"],
        "replies": [
            "Anytime! Enjoy. \U0001F60A",
            "You got it \u2014 welcome in! \U0001F64C",
            "No problem at all. \U0001F44D",
            "Glad to help. Take care!",
        ],
    },
    {
        "name": "bye",
        "patterns": [r"\bbye\b", r"\bgoodbye\b", r"\bcya\b", r"\bsee you\b"],
        "replies": [
            "Take care! \U0001F44B",
            "See you around \u2014 welcome aboard!",
            "Later! Reach out anytime.",
        ],
    },
]

DEFAULT_REPLIES = [
    "I'm the <b>OmniGate Helper</b>, and I mainly assist with <b>join requests and access</b> for "
    "@omnigatebot. If you're waiting to be let in, you're being approved automatically \u2014 nothing to "
    "do on your end. \u2705\n\nFor topics outside OmniGate I won't be able to help, but feel free to ask "
    "anything about OmniGate or your access!",
    "I can only help with <b>OmniGate</b> topics \u2014 mainly getting you accepted into the group or "
    "channel. \u2705 Your pending request is handled for you automatically.\n\nIf your question is about "
    "OmniGate or your access, ask away!",
    "I'm focused on <b>OmniGate</b> and join requests, so I may not understand other topics. \U0001F916 "
    "If you're trying to get in, no action is needed \u2014 you're approved automatically.\n\nGot an "
    "OmniGate question? I'm happy to help.",
]

_last_reply_time = {}
_last_reply_text = {}
_last_emoji = {}
_seen_users = set()          # users who have messaged before (so intro shows once)
_auto_accept_off = set()     # admins who turned auto-accept OFF (in-memory, this session)
_msg_count = defaultdict(int)


def on_cooldown(user_id):
    now = time.time()
    if now - _last_reply_time.get(user_id, 0) < REPLY_COOLDOWN:
        return True
    _last_reply_time[user_id] = now
    return False


def pick_non_repeating(user_id, options):
    if len(options) == 1:
        return options[0]
    last = _last_reply_text.get(user_id)
    choices = [o for o in options if o != last] or options
    chosen = random.choice(choices)
    _last_reply_text[user_id] = chosen
    return chosen


def match_rule(text):
    if not text:
        return None
    low = text.lower().strip()
    for rule in KEYWORD_RULES:
        for pat in rule["patterns"]:
            if re.search(pat, low):
                return rule
    return None


# Short rolling conversation history per user (for AI context). Kept tiny on purpose.
_history = defaultdict(list)  # user_id -> [("user"/"model", text), ...]
_HISTORY_MAX = 6


async def ai_reply(user_id, text):
    """Try Gemini for a natural reply. Returns None on any failure so the caller
    can fall back to keyword replies. Keeps a short history for context."""
    if not GEMINI_API_KEY or not text.strip():
        return None

    # Build the conversation: system grounding + recent turns + this message
    contents = [{"role": "user", "parts": [{"text": AI_SYSTEM_PROMPT}]},
                {"role": "model", "parts": [{"text": "Understood. I'll help with OmniGate only."}]}]
    for role, msg in _history[user_id][-_HISTORY_MAX:]:
        contents.append({"role": role, "parts": [{"text": msg}]})
    contents.append({"role": "user", "parts": [{"text": text[:800]}]})

    payload = {
        "contents": contents,
        "generationConfig": {"temperature": 0.6, "maxOutputTokens": 180},
    }
    try:
        import requests
        resp = await asyncio.to_thread(
            requests.post,
            f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
            json=payload, timeout=20,
        )
        if resp.status_code != 200:
            log.warning("Gemini HTTP %s — falling back to keywords", resp.status_code)
            return None
        data = resp.json()
        out = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        if not out:
            return None
        # Record turns for context
        _history[user_id].append(("user", text[:800]))
        _history[user_id].append(("model", out))
        _history[user_id] = _history[user_id][-_HISTORY_MAX:]
        return out
    except Exception as e:
        log.warning("AI reply failed (%s) — falling back to keywords", e)
        return None


def build_reply(user_id, text, is_first_contact):
    # On the very first message, always lead with the clear intro
    if is_first_contact:
        return pick_non_repeating(user_id, INTRO_MESSAGES)
    rule = match_rule(text)
    if rule:
        return pick_non_repeating(user_id, rule["replies"])
    return pick_non_repeating(user_id, DEFAULT_REPLIES)


if SESSION_STRING:
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
else:
    client = TelegramClient("userbot_local", API_ID, API_HASH)


@client.on(events.NewMessage(incoming=True))
async def handle_dm(event):
    if not event.is_private:
        return
    sender = await event.get_sender()
    if getattr(sender, "bot", False):
        return

    user_id = event.sender_id
    text = event.raw_text or ""
    _msg_count[user_id] += 1
    is_first_contact = user_id not in _seen_users

    # ── Commands (checked first) ──────────────────────────────────────
    cmd = text.strip().lower()
    if cmd.startswith("/autoacceptoff"):
        _auto_accept_off.add(user_id)
        _seen_users.add(user_id)
        await event.reply(
            "\U0001F6D1 <b>Auto-accept turned OFF.</b>\n\n"
            "The OmniGate Helper will stop auto-accepting old pending requests for you. "
            "Send <code>/autoaccepton</code> anytime to turn it back on.",
            parse_mode="html"
        )
        log.info("Auto-accept OFF requested by %s", user_id)
        return
    if cmd.startswith("/autoaccepton"):
        _auto_accept_off.discard(user_id)
        _seen_users.add(user_id)
        await event.reply(
            "\u2705 <b>Auto-accept turned ON.</b>\n\n"
            "The OmniGate Helper will resume auto-accepting old pending requests. "
            "Send <code>/autoacceptoff</code> to stop it again.",
            parse_mode="html"
        )
        log.info("Auto-accept ON requested by %s", user_id)
        return

    # Optional auto-react (OFF by default — raises ban risk)
    if AUTO_REACT and random.random() < REACT_CHANCE:
        try:
            choices = [e for e in REACTION_POOL if e != _last_emoji.get(user_id)] or REACTION_POOL
            emoji = random.choice(choices)
            _last_emoji[user_id] = emoji
            await client(SendReactionRequest(
                peer=event.chat_id, msg_id=event.id,
                reaction=[ReactionEmoji(emoticon=emoji)],
            ))
        except Exception as e:
            log.warning("React failed: %s", e)

    # First contact always gets the intro (bypasses cooldown so it's never missed)
    if not is_first_contact and on_cooldown(user_id):
        log.info("Skipped reply to %s (cooldown)", user_id)
        _seen_users.add(user_id)
        return

    # First contact: fixed intro (with safety + commands). Otherwise: AI first, keyword fallback.
    if is_first_contact:
        reply = pick_non_repeating(user_id, INTRO_MESSAGES)
    else:
        reply = await ai_reply(user_id, text)
        if not reply:
            reply = build_reply(user_id, text, False)
    _seen_users.add(user_id)
    _last_reply_time[user_id] = time.time()

    try:
        async with client.action(event.chat_id, "typing"):
            await asyncio.sleep(min(1.5 + len(reply) * 0.01, 4))
        await event.reply(reply, parse_mode="html")
        log.info("Replied to %s (%s): %.50s",
                 user_id, "intro" if is_first_contact else "keyword", reply)
    except Exception as e:
        log.warning("Reply failed: %s", e)


def main():
    if not SESSION_STRING:
        log.error("No SESSION_STRING. Run login.py locally first to generate one.")
        return
    log.info("OmniGate Helper userbot (v4) starting...")
    client.start()
    log.info("Online. First-contact intro + keyword DM replies active. AUTO_REACT=%s", AUTO_REACT)
    client.run_until_disconnected()


if __name__ == "__main__":
    main()
