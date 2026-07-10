"""
OmniGate Helper Userbot  (v14)
- DM only (silent in groups/channels)
- FIRST contact: clearly explains what this account is and how it works
- Debounced replies: rapid multi-message users get ONE combined, coherent answer
- Gemini AI with truncation fix (no more cut-off replies), retry, HTML-safe output
- Persistent state (intro shown once, /autoacceptoff survives restarts)
- Commands: /start /help /status /autoacceptoff /autoaccepton

⚠️ NOTE: This runs automation on a USER account, which Telegram's ToS restricts.
   Use a SECONDARY / throwaway account only. Auto-react raises ban risk the most —
   it is OFF by default (set AUTO_REACT=1 only if you accept the risk).
"""

import os
import re
import json
import time
import html
import asyncio
import random
import logging
from collections import defaultdict, deque

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import ReactionEmoji
from telethon.tl.functions.messages import SendReactionRequest

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
log = logging.getLogger("userbot")

VERSION = "14"

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION_STRING = os.environ.get("SESSION_STRING", "")

# Auto-react is OFF by default — it is the biggest ban-risk signal on a user account.
AUTO_REACT = os.environ.get("AUTO_REACT", "0") == "1"
REACT_CHANCE = float(os.environ.get("REACT_CHANCE", "0.5"))

# ── Behavior tuning ───────────────────────────────────────────────────
# DEBOUNCE_SECONDS: how long to wait after a user's last message before replying.
# Users often type in fragments ("hi" / "how do i join" / "still waiting") —
# we collect them and answer ONCE, coherently, instead of spamming per-fragment.
DEBOUNCE_SECONDS = float(os.environ.get("DEBOUNCE_SECONDS", "2.5"))
# Soft anti-spam: max replies per user per rolling hour (silent beyond this).
MAX_REPLIES_PER_HOUR = int(os.environ.get("MAX_REPLIES_PER_HOUR", "20"))

# ── Persistent state ──────────────────────────────────────────────────
# Survives restarts so users don't get the intro twice and /autoacceptoff sticks.
# On Railway, attach a Volume and set STATE_FILE=/data/state.json for persistence
# across redeploys (without a volume it still survives normal restarts).
STATE_FILE = os.environ.get("STATE_FILE", "state.json")

# ── Gemini AI (optional) ──────────────────────────────────────────────
# Uses the SAME key as the main bot. If unset, fails, or is rate-limited, the
# userbot automatically falls back to the keyword replies below.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
GEMINI_MAX_TOKENS = int(os.environ.get("GEMINI_MAX_TOKENS", "400"))
GEMINI_RETRIES = 2          # total attempts on 429/5xx
GEMINI_RETRY_DELAY = 2.0    # seconds between attempts

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
    "approvals, safety of this process, and the commands below. NOTHING ELSE.\n"
    "If the user asks about ANYTHING outside OmniGate — general knowledge, coding, math, news, "
    "advice, jokes, other apps, personal questions, 'what can you do', 'who are you' beyond your "
    "OmniGate role, etc. — you MUST politely REFUSE and redirect. Do NOT answer the off-topic part "
    "at all, not even briefly. Always bring it back to OmniGate.\n"
    "Example refusal: 'I can only help with OmniGate and your group's join requests. Is there "
    "anything about OmniGate or your pending members I can help with?'\n\n"
    "COMMANDS the admin can send you in this chat:\n"
    "- /autoacceptoff  -> stop auto-accepting old pending requests\n"
    "- /autoaccepton   -> resume auto-accepting\n"
    "- /status         -> check whether auto-accept is currently ON or OFF\n"
    "- /help           -> list the available commands\n\n"
    "NOTE: The user's message may contain several short lines — that just means they sent "
    "multiple quick messages. Read them together as ONE question and give ONE answer.\n\n"
    "RULES:\n"
    "- ALWAYS reply in ENGLISH only, regardless of what language the user writes in. "
    "Never reply in Tagalog or any other language.\n"
    "- Keep replies SHORT (1-3 sentences), warm, clear, and COMPLETE — always finish your "
    "sentence, never trail off.\n"
    "- Stay 100% on OmniGate. When in doubt whether something is on-topic, treat it as off-topic "
    "and redirect.\n"
    "- For detailed OmniGate features/pricing/settings: give a brief answer and point to the main "
    "bot @omnigatebot. Do NOT invent specifics, prices, or settings.\n"
    "- Never claim to be a human. Never ask for passwords, codes, or payment.\n"
    "- Plain text only. No markdown, no code blocks, no asterisks."
)

REACTION_POOL = ["\U0001F44D", "\U0001F525", "\U0001F44C", "\u2764\uFE0F",
                 "\U0001F389", "\U0001F60A", "\U0001F44F", "\u2728",
                 "\U0001F60D", "\U0001F4AF", "\U0001F64C", "\U0001F914"]

# ── FIRST-CONTACT INTRO ───────────────────────────────────────────────
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
        "\u2022 <code>/autoaccepton</code> \u2014 resume auto-accepting\n"
        "\u2022 <code>/status</code> \u2014 check if auto-accept is ON or OFF\n"
        "\u2022 <code>/help</code> \u2014 show this command list again\n\n"
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
        "\u2022 <code>/autoaccepton</code> \u2014 turn it back ON\n"
        "\u2022 <code>/status</code> \u2014 check current status\n"
        "\u2022 <code>/help</code> \u2014 show commands\n\n"
        "Feel free to ask any OmniGate question."
    ),
]

HELP_MESSAGE = (
    "\u2699\uFE0F <b>OmniGate Helper \u2014 Commands</b>\n\n"
    "\u2022 <code>/autoacceptoff</code> \u2014 stop auto-accepting old pending requests\n"
    "\u2022 <code>/autoaccepton</code> \u2014 resume auto-accepting\n"
    "\u2022 <code>/status</code> \u2014 check whether auto-accept is ON or OFF\n"
    "\u2022 <code>/help</code> \u2014 show this list\n\n"
    "For everything else about OmniGate \u2014 features, settings, setup \u2014 the main bot "
    "<b>@omnigatebot</b> has the full admin tools. \U0001F64C"
)

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
            "\u2022 <code>/autoaccepton</code> \u2014 resume auto-accepting\n"
            "\u2022 <code>/status</code> \u2014 check current status\n\n"
            "If it's about a join request, it's handled automatically. For anything else about "
            "@omnigatebot, just ask. \U0001F64F",
            "Happy to help! \u2699\uFE0F You can send <code>/autoacceptoff</code> to stop auto-accepting, "
            "or <code>/autoaccepton</code> to resume. Anything else about OmniGate \u2014 ask away.",
            "Sure \u2014 the main commands are <code>/autoacceptoff</code>, <code>/autoaccepton</code>, and "
            "<code>/status</code>. For other OmniGate questions, the admin tools live in @omnigatebot. \U0001F64C",
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

# Replies for non-text messages (stickers, photos, voice notes, etc.)
MEDIA_REPLIES = [
    "I can only read <b>text messages</b>. \U0001F60A If you have a question about OmniGate or your "
    "join request, just type it out and I'll help!",
    "Nice one! \U0001F44D I can't process media though \u2014 send me a text message if you need help "
    "with OmniGate or your pending request.",
    "I only understand text. \U0001F916 Type your OmniGate question and I'll get right to it!",
]

# ── Runtime state ─────────────────────────────────────────────────────
_last_reply_text = {}
_last_emoji = {}
_seen_users = set()          # users who have messaged before (so intro shows once) — persisted
_auto_accept_off = set()     # admins who turned auto-accept OFF — persisted
_msg_count = defaultdict(int)
_reply_times = defaultdict(deque)   # user_id -> deque of reply timestamps (hourly cap)
_pending = {}                # user_id -> {"texts": [...], "event": ev, "task": task, "media_only": bool}

# Short rolling conversation history per user (for AI context). Kept tiny on purpose.
_history = defaultdict(list)  # user_id -> [("user"/"model", text), ...]
_HISTORY_MAX = 6


# ── Persistence ───────────────────────────────────────────────────────
def load_state():
    global _seen_users, _auto_accept_off
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        _seen_users = set(int(x) for x in data.get("seen_users", []))
        _auto_accept_off = set(int(x) for x in data.get("auto_accept_off", []))
        log.info("State loaded: %d seen users, %d auto-accept-off", len(_seen_users), len(_auto_accept_off))
    except FileNotFoundError:
        log.info("No state file yet (%s) — starting fresh.", STATE_FILE)
    except Exception as e:
        log.warning("Failed to load state (%s) — starting fresh.", e)


def save_state():
    try:
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({
                "seen_users": sorted(_seen_users),
                "auto_accept_off": sorted(_auto_accept_off),
            }, f)
        os.replace(tmp, STATE_FILE)
    except Exception as e:
        log.warning("Failed to save state: %s", e)


def mark_seen(user_id):
    if user_id not in _seen_users:
        _seen_users.add(user_id)
        save_state()


# ── Anti-spam (rolling hourly cap; replaces the old hard 30s drop) ────
def over_hourly_cap(user_id):
    dq = _reply_times[user_id]
    now = time.time()
    while dq and now - dq[0] > 3600:
        dq.popleft()
    return len(dq) >= MAX_REPLIES_PER_HOUR


def record_reply(user_id):
    _reply_times[user_id].append(time.time())


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


# ── Gemini ────────────────────────────────────────────────────────────
def _trim_to_last_sentence(text):
    """If output was cut off (MAX_TOKENS), keep only up to the last finished sentence."""
    cut = max(text.rfind("."), text.rfind("!"), text.rfind("?"))
    if cut >= 20:  # keep only if a reasonable amount survives
        return text[:cut + 1].strip()
    return ""


async def ai_reply(user_id, text):
    """Try Gemini for a natural reply. Returns None on any failure so the caller
    can fall back to keyword replies. Keeps a short history for context."""
    if not GEMINI_API_KEY:
        log.warning("AI skipped: GEMINI_API_KEY is NOT set in this service — using keyword replies.")
        return None
    if not text.strip():
        return None

    # Build the conversation: system grounding + recent turns + this message
    contents = [{"role": "user", "parts": [{"text": AI_SYSTEM_PROMPT}]},
                {"role": "model", "parts": [{"text": "Understood. I'll help with OmniGate only."}]}]
    for role, msg in _history[user_id][-_HISTORY_MAX:]:
        contents.append({"role": role, "parts": [{"text": msg}]})
    contents.append({"role": "user", "parts": [{"text": text[:800]}]})

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.6,
            "maxOutputTokens": GEMINI_MAX_TOKENS,
            # CRITICAL: gemini-2.5 models spend "thinking" tokens INSIDE maxOutputTokens
            # by default, which was eating the budget and cutting replies mid-sentence.
            # thinkingBudget: 0 disables thinking -> full budget goes to the reply.
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }

    def _do_request():
        """Blocking HTTP POST using only the Python standard library."""
        import json as _json
        import urllib.request
        import urllib.error
        url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"
        body = _json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", errors="replace")
        except Exception as e:
            return -1, str(e)

    try:
        import json as _json
        status, raw = -1, ""
        for attempt in range(GEMINI_RETRIES):
            status, raw = await asyncio.to_thread(_do_request)
            if status == 200:
                break
            if status in (429, 500, 503, -1) and attempt < GEMINI_RETRIES - 1:
                log.warning("Gemini HTTP %s (attempt %d) — retrying in %.1fs",
                            status, attempt + 1, GEMINI_RETRY_DELAY)
                await asyncio.sleep(GEMINI_RETRY_DELAY)
            else:
                break
        if status != 200:
            log.warning("Gemini HTTP %s: %s — falling back to keywords", status, str(raw)[:300])
            return None

        data = _json.loads(raw)
        cand = data.get("candidates", [{}])[0]
        finish = cand.get("finishReason", "")
        parts = cand.get("content", {}).get("parts", [])
        # Join ALL text parts, skipping internal "thought" parts (2.5 models can
        # return multiple parts — taking only parts[0] was another cut-off cause).
        out = "".join(
            p.get("text", "") for p in parts
            if isinstance(p, dict) and not p.get("thought")
        ).strip()

        if not out:
            log.warning("Gemini returned empty text (finishReason=%s) — falling back", finish)
            return None
        if finish == "MAX_TOKENS":
            trimmed = _trim_to_last_sentence(out)
            if not trimmed:
                log.warning("Gemini output truncated beyond repair — falling back to keywords")
                return None
            log.info("Gemini output hit MAX_TOKENS — trimmed to last full sentence")
            out = trimmed

        # Record turns for context
        _history[user_id].append(("user", text[:800]))
        _history[user_id].append(("model", out))
        _history[user_id] = _history[user_id][-_HISTORY_MAX:]
        log.info("AI replied to %s: %.60s", user_id, out)
        return out
    except Exception as e:
        log.warning("AI reply failed (%s) — falling back to keywords", e)
        return None


def build_keyword_reply(user_id, text):
    rule = match_rule(text)
    if rule:
        return pick_non_repeating(user_id, rule["replies"])
    return pick_non_repeating(user_id, DEFAULT_REPLIES)


# ── Sending ───────────────────────────────────────────────────────────
async def send_reply(event, user_id, reply_html, tag):
    """Send with a natural typing delay. reply_html must already be HTML-safe."""
    try:
        async with event.client.action(event.chat_id, "typing"):
            await asyncio.sleep(min(1.5 + len(reply_html) * 0.01, 4))
        await event.reply(reply_html, parse_mode="html")
        record_reply(user_id)
        log.info("Replied to %s (%s): %.50s", user_id, tag, reply_html)
    except Exception as e:
        # If HTML parsing somehow fails, retry once as plain text so the user
        # is never left with NO reply (this was a silent-failure case before).
        log.warning("Reply failed (%s) — retrying as plain text", e)
        try:
            plain = re.sub(r"<[^>]+>", "", reply_html)
            await event.reply(plain, parse_mode=None)
            record_reply(user_id)
        except Exception as e2:
            log.warning("Plain-text retry also failed: %s", e2)


async def flush_pending(user_id):
    """Runs after the debounce window: combine the user's rapid messages into
    ONE text and send ONE coherent reply."""
    try:
        await asyncio.sleep(DEBOUNCE_SECONDS)
    except asyncio.CancelledError:
        return  # a newer message arrived; the new task will handle everything

    slot = _pending.pop(user_id, None)
    if not slot:
        return
    event = slot["event"]
    combined = "\n".join(t for t in slot["texts"] if t).strip()
    is_first_contact = user_id not in _seen_users
    mark_seen(user_id)

    if over_hourly_cap(user_id):
        log.info("Skipped reply to %s (hourly cap %d reached)", user_id, MAX_REPLIES_PER_HOUR)
        return

    # First contact always gets the clear intro (with safety + commands)
    if is_first_contact:
        await send_reply(event, user_id, pick_non_repeating(user_id, INTRO_MESSAGES), "intro")
        return

    # Media-only (stickers, photos, voice) with no text
    if not combined:
        if slot.get("media"):
            await send_reply(event, user_id, pick_non_repeating(user_id, MEDIA_REPLIES), "media")
        return

    # AI first (HTML-escaped so Gemini output can never break the send), keyword fallback
    ai = await ai_reply(user_id, combined)
    if ai:
        await send_reply(event, user_id, html.escape(ai), "ai")
    else:
        await send_reply(event, user_id, build_keyword_reply(user_id, combined), "keyword")


# ── Commands ──────────────────────────────────────────────────────────
async def handle_command(event, user_id, cmd):
    mark_seen(user_id)
    if cmd.startswith("/start"):
        await send_reply(event, user_id, pick_non_repeating(user_id, INTRO_MESSAGES), "cmd:start")
    elif cmd.startswith("/autoacceptoff"):
        _auto_accept_off.add(user_id)
        save_state()
        await send_reply(event, user_id,
            "\U0001F6D1 <b>Auto-accept turned OFF.</b>\n\n"
            "The OmniGate Helper will stop auto-accepting old pending requests for you. "
            "Send <code>/autoaccepton</code> anytime to turn it back on.", "cmd:off")
        log.info("Auto-accept OFF requested by %s", user_id)
    elif cmd.startswith("/autoaccepton"):
        _auto_accept_off.discard(user_id)
        save_state()
        await send_reply(event, user_id,
            "\u2705 <b>Auto-accept turned ON.</b>\n\n"
            "The OmniGate Helper will resume auto-accepting old pending requests. "
            "Send <code>/autoacceptoff</code> to stop it again.", "cmd:on")
        log.info("Auto-accept ON requested by %s", user_id)
    elif cmd.startswith("/status"):
        if user_id in _auto_accept_off:
            msg = ("\U0001F6D1 <b>Status: auto-accept is OFF</b> for you.\n\n"
                   "Send <code>/autoaccepton</code> to resume auto-accepting old pending requests.")
        else:
            msg = ("\u2705 <b>Status: auto-accept is ON.</b>\n\n"
                   "Old pending join requests are being cleared automatically. "
                   "Send <code>/autoacceptoff</code> to stop.")
        await send_reply(event, user_id, msg, "cmd:status")
    elif cmd.startswith("/help"):
        await send_reply(event, user_id, HELP_MESSAGE, "cmd:help")
    else:
        await send_reply(event, user_id,
            "\U0001F914 I don't recognize that command. Send <code>/help</code> to see what I can do.",
            "cmd:unknown")


# ── Client ────────────────────────────────────────────────────────────
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
    text = (event.raw_text or "").strip()
    _msg_count[user_id] += 1

    # Mark as read right away — looks natural and responsive
    try:
        await client.send_read_acknowledge(event.chat_id, event.message)
    except Exception:
        pass

    # Commands are handled IMMEDIATELY (never debounced, never rate-limited away)
    if text.lower().startswith("/"):
        # Cancel any pending debounce so the command answer isn't duplicated
        slot = _pending.pop(user_id, None)
        if slot and slot.get("task"):
            slot["task"].cancel()
        await handle_command(event, user_id, text.lower())
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

    # ── Debounce: collect rapid messages, reply ONCE ──────────────────
    slot = _pending.get(user_id)
    if slot:
        if slot.get("task"):
            slot["task"].cancel()
    else:
        slot = {"texts": [], "media": False}
        _pending[user_id] = slot
    if text:
        slot["texts"].append(text)
    if event.message.media:
        slot["media"] = True
    slot["event"] = event  # reply to the latest message
    slot["task"] = asyncio.create_task(flush_pending(user_id))


def main():
    if not SESSION_STRING:
        log.error("No SESSION_STRING. Run login.py locally first to generate one.")
        return
    log.info("OmniGate Helper userbot (v%s) starting...", VERSION)
    load_state()
    if GEMINI_API_KEY:
        log.info("Gemini AI: ENABLED (key detected, model=%s, maxTokens=%d, thinking=OFF)",
                 GEMINI_MODEL, GEMINI_MAX_TOKENS)
    else:
        log.warning("Gemini AI: DISABLED — GEMINI_API_KEY not set. Add it in this service's "
                    "Variables to enable natural replies. Using keyword replies for now.")
    client.start()
    log.info("Online. AUTO_REACT=%s, DEBOUNCE=%.1fs, HOURLY_CAP=%d, STATE_FILE=%s",
             AUTO_REACT, DEBOUNCE_SECONDS, MAX_REPLIES_PER_HOUR, STATE_FILE)
    client.run_until_disconnected()


if __name__ == "__main__":
    main()
