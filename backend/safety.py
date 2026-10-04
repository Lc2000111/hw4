"""Sensitive-data guard for chat messages (Problem 9).

Shoppers sometimes paste card numbers, Social Security numbers, or passwords
into a chat box. Campus Customs can't take payments in chat and should never
store such data, so every message is cleaned BEFORE it reaches the AI model,
the database (chat_messages), or the server logs.

    redact("my card is 4111 1111 1111 1111")
    -> ("my card is [card number removed]", ["card number"])
"""

from __future__ import annotations

import re

# 13-19 digits, optionally grouped by spaces or dashes (e.g. 4111 1111 1111 1111).
CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
SSN_RE = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")
CVV_RE = re.compile(r"\b(cvv|cvc|security code)\s*(?:is|:|=)?\s*\d{3,4}\b", re.IGNORECASE)
PASSWORD_RE = re.compile(
    r"\b(password|passcode|passwd|pwd|pw)(\s*(?:is|:|=)\s*|\s+)(\S+)", re.IGNORECASE
)
# Words that follow "password" in normal questions ("password reset", "password for my account").
NOT_A_PASSWORD = {"reset", "for", "to", "change", "help", "forgot", "?", "and", "or", "please", "the", "a", "my"}


def luhn_ok(digits: str) -> bool:
    """The checksum every real card number passes, so order numbers or phone numbers aren't removed."""
    total, double = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if double:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
        double = not double
    return total % 10 == 0


def redact(text: str) -> tuple[str, list[str]]:
    """Return (cleaned text, kinds of data removed)."""
    found: list[str] = []

    def card(m: re.Match) -> str:
        digits = re.sub(r"\D", "", m.group(0))
        if 13 <= len(digits) <= 19 and luhn_ok(digits):
            found.append("card number")
            return "[card number removed]"
        return m.group(0)

    def password(m: re.Match) -> str:
        if m.group(3).lower().strip(".,!?") in NOT_A_PASSWORD:
            return m.group(0)
        found.append("password")
        return f"{m.group(1)}{m.group(2)}[password removed]"

    text = CARD_RE.sub(card, text)
    text, n = SSN_RE.subn("[SSN removed]", text)
    found += ["Social Security number"] * n
    text, n = CVV_RE.subn(lambda m: f"{m.group(1)} [security code removed]", text)
    found += ["security code"] * n
    text = PASSWORD_RE.sub(password, text)
    # unique, in order found
    return text, list(dict.fromkeys(found))


# ---------- Crisis language (Problem 12) ----------
# Checked in code BEFORE the model runs. The provider's content filter blocks these messages
# and would otherwise produce a generic refusal, which is the wrong response to someone in crisis.
CRISIS_RE = re.compile(
    r"\b(kill(ing)? myself|hurt(ing)? myself|harm(ing)? myself|self[- ]?harm|suicid\w*|end (it all|my life)"
    r"|want(ed)? to die|don'?t want to (live|be alive|be here)|take my (own )?life|no reason to live)\b",
    re.IGNORECASE,
)

CRISIS_REPLY = (
    "I'm really sorry you're feeling this way, and I'm glad you said something. You don't have to go through it "
    "alone. Please reach out right now: call or text 988 (Suicide & Crisis Lifeline, 24/7 in the US), or call 911 "
    "if you're in immediate danger. If you're a Yale student, Yale Mental Health & Counseling can help too. "
    "If you'd like to talk to someone you trust, now is a good time to reach out to them."
)


def is_crisis(text: str) -> bool:
    return bool(CRISIS_RE.search(text))
