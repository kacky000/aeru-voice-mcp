#!/usr/bin/env python3
"""Local tests for the Muse Bridge Lambda (no AWS needed).

Stubs boto3's SES client, feeds Alexa request envelopes to the handler,
and checks the spoken responses and the composed bridge email.
"""
import os
import sys
import types

os.environ["BRIDGE_TO"] = "muse-address@example.invalid"
os.environ["BRIDGE_FROM"] = "bridge@example.invalid"
os.environ["REPLY_TO"] = "user-mailbox@example.invalid"

SENT = {"calls": []}


class FakeSES:
    def send_email(self, **kwargs):
        SENT["calls"].append(kwargs)
        return {"MessageId": "fake"}


fake_boto3 = types.ModuleType("boto3")
fake_boto3.client = lambda service: FakeSES()
sys.modules["boto3"] = fake_boto3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lambda_function as lf  # noqa: E402


def envelope(rtype, intent=None, slots=None):
    req = {"type": rtype}
    if intent:
        req["intent"] = {"name": intent, "slots": slots or {}}
    return {"version": "1.0", "request": req}


def speech_of(result):
    return result["response"]["outputSpeech"]["text"]


def check(label, cond):
    print(("PASS" if cond else "FAIL"), label)
    assert cond, label


# Launch
r = lf.lambda_handler(envelope("LaunchRequest"))
check("launch welcomes and keeps session open",
      "ミューズブリッジ" in speech_of(r) and r["response"]["shouldEndSession"] is False)

# Ask with a query -> one SES email containing the query
SENT["calls"].clear()
r = lf.lambda_handler(envelope(
    "IntentRequest", "AskMuseIntent",
    {"query": {"name": "query", "value": "最近の投稿を読んで"}}))
check("ask confirms sending", "伝えました" in speech_of(r))
check("exactly one email sent", len(SENT["calls"]) == 1)
call = SENT["calls"][0]
body = call["Message"]["Body"]["Text"]["Data"]
check("email goes to the Muse address",
      call["Destination"]["ToAddresses"] == ["muse-address@example.invalid"])
check("reply-to is the user mailbox",
      call["ReplyToAddresses"] == ["user-mailbox@example.invalid"])
check("subject carries the bridge prefix",
      call["Message"]["Subject"]["Data"].startswith("[AERU-BRIDGE]"))
check("body carries the utterance and a request id",
      "最近の投稿を読んで" in body and "リクエストID:" in body)

# Ask without a query -> reprompt, no email
SENT["calls"].clear()
r = lf.lambda_handler(envelope("IntentRequest", "AskMuseIntent", {}))
check("empty query reprompts without sending",
      "聞き取れませんでした" in speech_of(r) and len(SENT["calls"]) == 0)

# Check reply -> guidance
r = lf.lambda_handler(envelope("IntentRequest", "CheckReplyIntent"))
check("reply check explains the email readback", "メールで届きます" in speech_of(r))

# Stop -> goodbye, session ends
r = lf.lambda_handler(envelope("IntentRequest", "AMAZON.StopIntent"))
check("stop ends the session",
      "終わります" in speech_of(r) and r["response"]["shouldEndSession"] is True)

# Session ended -> empty response, no crash
r = lf.lambda_handler(envelope("SessionEndedRequest"))
check("session-ended returns an empty response", r["response"] == {})

print("ALL TESTS PASSED")
