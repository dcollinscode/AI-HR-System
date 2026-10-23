"""Deterministic intent classification for candidate e-mail replies.

The reply agent used to hand *every* message to a small LLM. That is slow and
unreliable for the cases where the right answer is already known (status
questions, attendance confirmations) and unsafe for the ones where a model
should not improvise (salary, legal, complaints, withdrawals). This module picks
the handling route up-front; only ``QUESTION`` falls through to the AI draft.
"""
import re

THANKS = "thanks"
CONFIRM = "confirm"
WITHDRAW = "withdraw"
ESCALATE = "escalate"
STATUS = "status"
QUESTION = "question"

# Roman-Urdu / Hindi variants are included because candidates mix languages.
_WITHDRAW = (
    r"\bwithdraw", r"no longer (interested|available)", r"not interested",
    r"cancel my application", r"remove my (application|profile|cv|data)",
    r"don'?t want (the|this) (job|position)", r"decline (the|this) (offer|interview)",
    r"interest nahi", r"interested nahi", r"nahi karna", r"apply wapas",
)
_ESCALATE = (
    r"\bsalary\b", r"\bpackage\b", r"\bcompensation\b", r"\bnegotiat", r"\boffer letter\b",
    r"\bcomplain", r"\blegal\b", r"\blawyer\b", r"\bharass", r"\bdiscriminat",
    r"\bvisa\b", r"\brelocat", r"\bunfair\b", r"\bmanager\b.*\bcall me\b",
    r"\bspeak to (a |the )?(human|person|hr|manager)\b", r"\burgent(ly)?\b",
)
_CONFIRM = (
    r"\bi (will|'ll|shall) (be )?(attend|there|present|join|come)",
    r"\b(confirm(ed|ing)?|accepted?)\b.*\b(interview|slot|time|attend)",
    r"\b(interview|slot|time)\b.*\b(confirm(ed)?|works for me|is fine|is good|suits me)",
    r"\bsee you\b", r"\bworks for me\b", r"\bi confirm\b", r"\bconfirmed\b",
    r"\bjee? haan\b.*\binterview\b", r"\bmain aa (jaunga|jaungi)\b", r"\bawa(unga|ungi)\b",
)
_STATUS = (
    r"\bstatus\b", r"\bany (update|news|progress)\b", r"\bupdate on my\b",
    r"\bwhat'?s? (the )?(result|outcome|next)\b", r"\bhave you (reviewed|shortlisted)\b",
    r"\bhear (back|from you)\b", r"\bresult kab\b", r"\bupdate kab\b",
)
_QUESTION_MARK_RE = re.compile(r"\?|\b(when|where|what|which|how|can|could|is|are|do|does|kya|kab|kahan|kaise)\b", re.I)
_THANKS_RE = re.compile(r"\b(thank(s| you)|thx|shukriya|jazak)", re.I)
_FILLER_RE = re.compile(
    r"\b(thank(s| you)|thx|shukriya|dear|hi|hello|regards|best|sincerely|ok(ay)?|"
    r"noted|received|got it|great|sure|will do|much|so|very|a lot|for|your|the|"
    r"email|mail|update|information|info|response|reply|hr|team|sir|madam|ma'?am|"
    r"and|you|i|appreciate|it|this)\b",
    re.I,
)


def _any(patterns: tuple[str, ...], text: str) -> bool:
    return any(re.search(p, text, re.I | re.S) for p in patterns)


def classify_reply(text: str | None, *, has_interview: bool = False) -> str:
    """Return one of THANKS / CONFIRM / WITHDRAW / ESCALATE / STATUS / QUESTION.

    Order matters: a withdrawal or a sensitive topic always wins over the rest,
    and a bare "thank you" is detected only when nothing else is being asked.
    """
    body = (text or "").strip()
    if not body:
        return THANKS
    lowered = body.lower()

    if _any(_WITHDRAW, lowered):
        return WITHDRAW
    if _any(_ESCALATE, lowered):
        return ESCALATE
    if has_interview and _any(_CONFIRM, lowered) and "?" not in body:
        return CONFIRM
    if _any(_STATUS, lowered):
        return STATUS

    if _THANKS_RE.search(lowered) and "?" not in body:
        leftover = re.sub(r"[^a-z\s']", " ", _FILLER_RE.sub(" ", lowered))
        if len(leftover.split()) <= 3:
            return THANKS
    return QUESTION


_STATUS_TEXT = {
    "APPLIED": "We have received your application and it is queued for review.",
    "PROCESSING": "Your application is currently being processed and evaluated.",
    "HR_REVIEW": "Your application is under review by our hiring team.",
    "SHORTLISTED": "Good news: you have been shortlisted. Our team will contact you about the next steps.",
    "INTERVIEW_SCHEDULED": "Your interview has been scheduled; please check the details sent to you.",
    "TECHNICAL_INTERVIEW": "You are in the technical interview stage.",
    "TECHNICAL_REVIEW": "Your technical interview is being reviewed by our team.",
    "BEHAVIORAL_INTERVIEW": "You are in the behavioural interview stage.",
    "FINAL_REVIEW": "Your application is in the final review stage; a decision will follow soon.",
    "SELECTED": "Congratulations, you have been selected. Our team will contact you with the next steps.",
    "HOLD": "Your application is on hold for now. We will get back to you as soon as there is movement.",
    "REJECTED": "After careful review we are not moving forward with your application. Thank you for your interest.",
}


def status_sentence(status: str | None) -> str:
    return _STATUS_TEXT.get(
        status or "", "Your application is being reviewed by our hiring team."
    )
