"""Muse Bridge - Alexa skill backend (prototype).

Forwards what the user says to the Echo as an email to their Muse's own
mail address. The receiving Muse does the actual work (e.g. reading or
posting to AERU via its MCP tools) and replies by email; Alexa's built-in
email reading speaks the reply (v1 readback path).

No ASK SDK dependency: the Alexa request envelope is plain JSON.
Email is sent with Amazon SES (boto3 is included in the Lambda runtime).

Configuration (environment variables win; CONFIG below is the fallback for
Alexa-hosted skills, whose console has no environment-variable editor):
  BRIDGE_TO    - the Muse mail address that receives bridge requests
  BRIDGE_FROM  - a SES-verified sender address
  REPLY_TO     - the user's own mailbox (where Muse's replies should go,
                 and the mailbox Alexa reads aloud)
"""
import json
import os
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
SUBJECT_PREFIX = "[AERU-BRIDGE]"

CONFIG = {
    "BRIDGE_TO": "",    # e.g. "xxxx@muse.ai" - the receiving Muse address
    "BRIDGE_FROM": "",  # a SES-verified sender address
    "REPLY_TO": "",     # the user's own mailbox
}


def _cfg(name):
    return os.environ.get(name) or CONFIG.get(name) or ""

WELCOME = "ミューズブリッジです。ミューズへのお願いを、どうぞお話しください。"
WELCOME_REPROMPT = "たとえば、『最近の投稿を読んで、って頼んで』のように言ってください。"
SENT = "ミューズに伝えました。返事はメールで届きます。『アレクサ、メールを読んで』と聞いてください。"
SENT_NO_MAIL = "お願いは受け取りました。ただし、メール送信の設定がまだ終わっていないため、いまはミューズへ届いていません。設定が終わってから、もう一度お試しください。"
EMPTY_QUERY = "すみません、お願いの内容が聞き取れませんでした。もう一度お話しください。"
REPLY_GUIDE = "ミューズからの返事はメールで届きます。『アレクサ、メールを読んで』と言うと、読み上げてもらえます。"
HELP = "ミューズへのお願いを、そのまま伝えます。『最近の投稿を読んで、って頼んで』のように言ってください。"
FALLBACK = "すみません、うまく聞き取れませんでした。もう一度お願いします。"
GOODBYE = "ミューズブリッジを終わります。"


def _speech(text, reprompt=None, end_session=True):
    response = {
        "outputSpeech": {"type": "PlainText", "text": text},
        "shouldEndSession": end_session,
    }
    if reprompt:
        response["reprompt"] = {
            "outputSpeech": {"type": "PlainText", "text": reprompt}
        }
    return {"version": "1.0", "response": response}


def send_bridge_email(query):
    """Send the utterance to the Muse address via SES. Returns request id."""
    import boto3  # available in the Lambda runtime; stubbed in local tests

    request_id = uuid.uuid4().hex[:12]
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    body = (
        "以下は、Alexa経由で届いた音声リクエストです。\n"
        "BRIDGE_PROTOCOL.md の手順に従って処理し、結果を Reply-To 宛に\n"
        "読み上げしやすい文章で返信してください。\n\n"
        f"リクエストID: {request_id}\n"
        f"受信時刻: {now}\n"
        f"内容: {query}\n"
    )
    ses = boto3.client("ses")
    ses.send_email(
        Source=_cfg("BRIDGE_FROM"),
        Destination={"ToAddresses": [_cfg("BRIDGE_TO")]},
        ReplyToAddresses=[_cfg("REPLY_TO")],
        Message={
            "Subject": {"Data": f"{SUBJECT_PREFIX} 音声リクエスト", "Charset": "UTF-8"},
            "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
        },
    )
    return request_id


def _intent_name(event):
    return ((event.get("request") or {}).get("intent") or {}).get("name") or ""


def _slot_value(event, name):
    intent = (event.get("request") or {}).get("intent") or {}
    slot = (intent.get("slots") or {}).get(name) or {}
    return (slot.get("value") or "").strip()


def lambda_handler(event, context=None):
    request = event.get("request") or {}
    rtype = request.get("type")

    if rtype == "LaunchRequest":
        return _speech(WELCOME, reprompt=WELCOME_REPROMPT, end_session=False)

    if rtype == "SessionEndedRequest":
        return {"version": "1.0", "response": {}}

    if rtype == "IntentRequest":
        name = _intent_name(event)
        if name == "AskMuseIntent":
            query = _slot_value(event, "query")
            if not query:
                return _speech(EMPTY_QUERY, reprompt=WELCOME_REPROMPT, end_session=False)
            print(f"BRIDGE QUERY: {query}")  # visible in the skill's logs
            try:
                send_bridge_email(query)
            except Exception as e:
                print(f"BRIDGE MAIL FAILED: {e}")
                return _speech(SENT_NO_MAIL)
            return _speech(SENT)
        if name == "CheckReplyIntent":
            return _speech(REPLY_GUIDE)
        if name == "AMAZON.HelpIntent":
            return _speech(HELP, reprompt=WELCOME_REPROMPT, end_session=False)
        if name in ("AMAZON.StopIntent", "AMAZON.CancelIntent"):
            return _speech(GOODBYE)
        return _speech(FALLBACK, reprompt=WELCOME_REPROMPT, end_session=False)

    return _speech(FALLBACK, reprompt=WELCOME_REPROMPT, end_session=False)


# Allow `python3 lambda_function.py '<envelope-json>'` for quick manual checks.
if __name__ == "__main__":
    import sys

    print(json.dumps(lambda_handler(json.loads(sys.argv[1])), ensure_ascii=False, indent=2))
