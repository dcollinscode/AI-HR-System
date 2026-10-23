import pytest

from app.services.reply_intents import (
    CONFIRM, ESCALATE, QUESTION, STATUS, THANKS, WITHDRAW, classify_reply,
)


@pytest.mark.parametrize(
    "text,interview,expected",
    [
        ("Thank you!", False, THANKS),
        ("Thanks so much for the update", False, THANKS),
        ("shukriya", False, THANKS),
        ("Thank you. When is the interview?", True, QUESTION),
        ("I confirm I will attend the interview", True, CONFIRM),
        ("Tuesday 3 PM works for me", True, CONFIRM),
        ("Will 3 PM work? I confirm", True, QUESTION),
        ("What is the status of my application?", False, STATUS),
        ("Any update on my application", False, STATUS),
        ("I want to withdraw my application", False, WITHDRAW),
        ("I am no longer interested", True, WITHDRAW),
        ("What is the salary range?", False, ESCALATE),
        ("I would like to negotiate", True, ESCALATE),
        ("Where is the office located?", True, QUESTION),
        ("", False, THANKS),
    ],
)
def test_classify(text, interview, expected):
    assert classify_reply(text, has_interview=interview) == expected
