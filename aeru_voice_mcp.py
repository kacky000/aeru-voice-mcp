#!/usr/bin/env python3
"""AERU voice MCP server (single-file distribution).

Wraps the Misskey API of AERU SNS for WA (https://wa-community.xsns.jp) so a
Muse can read the timeline aloud, summarise notifications, post, reply and
react on behalf of the token's owner — designed for voice-only use.

Setup (done by the receiving Muse, see SETUP_FOR_MUSE.md):
  1. python3 -m venv .venv && .venv/bin/pip install "mcp<2"
  2. Register the owner's AERU access token as the custom connector
     `custom.aeru-misskey` (api_key, bearer_header, host wa-community.xsns.jp).
     The token itself is never written into this file.
  3. Run: .venv/bin/python aeru_voice_mcp.py   (stdio MCP server)

The token is attached at request time through the registered connection
(dynamic credential surrogate); it never appears in this file or in logs.
"""
import http.client
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
from dynamic_credentials import add_surrogate_to_request  # noqa: E402

from mcp.server.fastmcp import FastMCP  # noqa: E402

BASE = "https://wa-community.xsns.jp/api"
HOST = "wa-community.xsns.jp"
CONNECTOR = "custom.aeru-misskey"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
JST = ZoneInfo("Asia/Tokyo")
MAX_TEXT = 280

# --------------------------------------------------------------------------
# Misskey API client
# --------------------------------------------------------------------------


class MisskeyError(RuntimeError):
    def __init__(self, status, payload):
        self.status = status
        self.payload = payload
        err = payload.get("error") if isinstance(payload, dict) else None
        if err:
            msg = f"{err.get('code', 'ERROR')}: {err.get('message', '')}"
        else:
            msg = json.dumps(payload, ensure_ascii=False)[:300]
        super().__init__(f"HTTP {status} {msg}")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise RuntimeError("redirect refused, verify the endpoint")


def _request(path, params, auth):
    body = json.dumps(params or {}).encode("utf-8")
    request = urllib.request.Request(
        f"{BASE}/{path}", data=body,
        headers={"Content-Type": "application/json", **UA}, method="POST",
    )
    if auth:
        add_surrogate_to_request(request, CONNECTOR, allowed_hosts=[HOST])
    return urllib.request.build_opener(NoRedirect()), request


def api(path, params=None, auth=True, retry=True):
    """POST to a Misskey API endpoint. retry is for reads only: a dropped
    connection on a write could mean the write landed; retrying would
    double-post."""
    opener, request = _request(path, params, auth)
    attempts = 3 if retry else 1
    last = None
    for i in range(attempts):
        try:
            with opener.open(request, timeout=30) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
            try:
                payload = json.loads(raw)
            except Exception:
                payload = {"raw": raw[:300]}
            raise MisskeyError(e.code, payload) from None
        except (http.client.RemoteDisconnected, ConnectionError, TimeoutError) as e:
            last = e
            if i < attempts - 1:
                time.sleep(1.5 * (i + 1))
    raise last


def whoami():
    return api("i")


def home_timeline(limit=10):
    return api("notes/timeline", {"limit": limit})


def notifications(limit=10):
    return api("i/notifications", {"limit": limit})


def user_notes(username, limit=5):
    user = api("users/show", {"username": username}, auth=False)
    return api("users/notes", {"userId": user["id"], "limit": limit}, auth=False)


def get_note(note_id):
    return api("notes/show", {"noteId": note_id}, auth=False)


def create_note(text, reply_id=None):
    params = {"text": text, "visibility": "public", "localOnly": True}
    if reply_id:
        params["replyId"] = reply_id
    result = api("notes/create", params, retry=False)
    return result.get("createdNote") or {}


def create_reaction(note_id, reaction="❤️"):
    api("notes/reactions/create", {"noteId": note_id, "reaction": reaction}, retry=False)
    return True


# --------------------------------------------------------------------------
# Voice-friendly formatting
# --------------------------------------------------------------------------

_URL_RE = re.compile(r"https?://\S+")
_MFM_FN_RE = re.compile(r"\$\[[^\s\]]+\s+([^\]]*)\]")
_MFM_TAG_RE = re.compile(r"\$\[[^\]]*\]")
_CUSTOM_EMOJI_RE = re.compile(r":[a-zA-Z0-9_]+:")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*", re.S)
_MENTION_RE = re.compile(r"@([a-zA-Z0-9_]+)(@[a-zA-Z0-9.\-]+)?")


def clean_text(text):
    if not text:
        return ""
    t = _URL_RE.sub("（リンク）", text)
    t = _MFM_FN_RE.sub(r"\1", t)
    t = _MFM_TAG_RE.sub("", t)
    t = _BOLD_RE.sub(r"\1", t)
    t = _CUSTOM_EMOJI_RE.sub("", t)
    t = _MENTION_RE.sub(r"\1さん", t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def truncate(text, limit=MAX_TEXT):
    if len(text) <= limit:
        return text
    return text[:limit] + f"…（以下省略。全文は{len(text)}文字です）"


def speakable_time(iso):
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(JST)
    except Exception:
        return ""
    return f"{dt.month}月{dt.day}日 {dt.hour}時{dt.minute:02d}分"


def display_name(user):
    if not user:
        return "不明なユーザー"
    return (user.get("name") or user.get("username") or "不明なユーザー").strip()


def _attachment_summary(note):
    files = note.get("files") or []
    if not files:
        return ""
    images = sum(1 for f in files if (f.get("type") or "").startswith("image/"))
    videos = sum(1 for f in files if (f.get("type") or "").startswith("video/"))
    audio = sum(1 for f in files if (f.get("type") or "").startswith("audio/"))
    parts = []
    if images:
        parts.append(f"画像{images}枚")
    if videos:
        parts.append(f"動画{videos}件")
    if audio:
        parts.append(f"音声{audio}件")
    other = len(files) - images - videos - audio
    if other:
        parts.append(f"ファイル{other}件")
    return "添付：" + "・".join(parts) if parts else ""


def _reaction_summary(note):
    reactions = note.get("reactions") or {}
    total = sum(reactions.values())
    if not total:
        return ""
    top = sorted(reactions.items(), key=lambda kv: -kv[1])[:3]
    detail = "、".join(f"{emoji}{count}" for emoji, count in top)
    return f"リアクション合計{total}件（{detail}）"


def format_note(note, index=None):
    user = note.get("user") or {}
    who = display_name(user)
    when = speakable_time(note.get("createdAt", ""))
    head = f"{who}さん"
    if when:
        head += f"（{when}）"
    prefix = f"{index}. " if index is not None else ""
    renote = note.get("renote")
    body_text = clean_text(note.get("text") or "")
    lines = []
    if renote and not body_text:
        orig_user = renote.get("user") or {}
        lines.append(f"{prefix}{head}が、{display_name(orig_user)}さんの投稿をリノートしました。")
        lines.append("元の投稿：" + truncate(clean_text(renote.get("text") or "（本文なし）")))
        sub = _attachment_summary(renote)
        if sub:
            lines.append(sub)
    else:
        kind = ""
        if note.get("replyId"):
            kind = "の返信"
        if note.get("cw"):
            lines.append(f"{prefix}{head}{kind}。注意書き：{clean_text(note['cw'])}（本文は折りたたまれています）")
            lines.append("本文：" + truncate(body_text or "（本文なし）"))
        else:
            lines.append(f"{prefix}{head}{kind}：{truncate(body_text or '（本文なし）')}")
        if renote and body_text:
            orig_user = renote.get("user") or {}
            lines.append(f"（引用元：{display_name(orig_user)}さんの投稿「{truncate(clean_text(renote.get('text') or ''), 80)}」）")
        sub = _attachment_summary(note)
        if sub:
            lines.append(sub)
    rs = _reaction_summary(note)
    if rs:
        lines.append(rs)
    lines.append(f"［ノートID: {note.get('id')}］")
    return "\n".join(lines)


def format_notes(notes):
    if not notes:
        return "投稿はありませんでした。"
    blocks = [format_note(n, i + 1) for i, n in enumerate(notes)]
    return f"{len(notes)}件の投稿があります。\n\n" + "\n\n".join(blocks)


_NOTIFICATION_TEMPLATES = {
    "follow": "{who}さんにフォローされました。",
    "mention": "{who}さんからメンションが届きました。",
    "reply": "{who}さんから返信が届きました。",
    "renote": "{who}さんがあなたの投稿をリノートしました。",
    "quote": "{who}さんがあなたの投稿を引用しました。",
    "reaction": "{who}さんがあなたの投稿に{reaction}でリアクションしました。",
    "pollEnded": "あなたが参加したアンケートの結果が出ました。",
    "receiveFollowRequest": "{who}さんからフォローリクエストが届きました。",
    "followRequestAccepted": "{who}さんへのフォローリクエストが承認されました。",
    "achievementEarned": "実績を獲得しました。",
    "app": "アプリからの通知です。",
    "test": "テスト通知です。",
}


def format_notification(notif, index=None):
    ntype = notif.get("type") or ""
    user = notif.get("user") or {}
    who = display_name(user)
    when = speakable_time(notif.get("createdAt", ""))
    prefix = f"{index}. " if index is not None else ""
    template = _NOTIFICATION_TEMPLATES.get(ntype, "通知：{type}")
    text = template.format(who=who, reaction=notif.get("reaction") or "絵文字", type=ntype)
    lines = [f"{prefix}{text}" + (f"（{when}）" if when else "")]
    note = notif.get("note")
    if note and ntype in ("mention", "reply", "quote"):
        lines.append("内容：" + truncate(clean_text(note.get("text") or "")))
        lines.append(f"［ノートID: {note.get('id')}］")
    return "\n".join(lines)


def format_notifications(notifs):
    if not notifs:
        return "新しい通知はありませんでした。"
    blocks = [format_notification(n, i + 1) for i, n in enumerate(notifs)]
    return f"{len(notifs)}件の通知があります。\n\n" + "\n\n".join(blocks)


# --------------------------------------------------------------------------
# MCP tools
# --------------------------------------------------------------------------

mcp = FastMCP("aeru-voice")


def _err(e):
    return f"エラーが発生しました：{e}"


@mcp.tool(name="whoami")
def whoami_tool() -> str:
    """接続中のAERUアカウントを確認します（名前とユーザー名を返します）。"""
    try:
        me = whoami()
    except Exception as e:
        return _err(e)
    name = me.get("name") or me.get("username")
    return f"{name}さん（@{me.get('username')}）として接続しています。"


@mcp.tool()
def get_home_timeline(limit: int = 10) -> str:
    """ホームタイムラインの新しい投稿を取得します。読み上げ向けに、発言者名・時刻・本文を整形して返します。「最近の投稿をまとめて」と頼まれたときに使います。"""
    try:
        notes = home_timeline(limit=max(1, min(limit, 30)))
    except Exception as e:
        return _err(e)
    return format_notes(notes)


@mcp.tool()
def get_notifications(limit: int = 10) -> str:
    """通知（返信・メンション・リアクション・フォローなど）を取得します。読み上げ向けに整形して返します。"""
    try:
        notifs = notifications(limit=max(1, min(limit, 30)))
    except Exception as e:
        return _err(e)
    return format_notifications(notifs)


@mcp.tool()
def get_user_notes(username: str, limit: int = 5) -> str:
    """指定したユーザーの最近の投稿を取得します。usernameは @ を除いた英数字のIDです。"""
    try:
        notes = user_notes(username.lstrip("@"), limit=max(1, min(limit, 20)))
    except Exception as e:
        return _err(e)
    return format_notes(notes)


@mcp.tool(name="get_note")
def get_note_tool(note_id: str) -> str:
    """ノートIDを指定して1件の投稿を取得します。タイムライン結果に付いているノートIDで、特定の投稿を聞き直すときに使います。"""
    try:
        note = get_note(note_id)
    except Exception as e:
        return _err(e)
    return format_note(note)


@mcp.tool()
def post_note(text: str) -> str:
    """AERUに新しい投稿（ノート）を公開します。実行前に、必ず投稿文を読み上げて本人の確認を取ってください。"""
    try:
        note = create_note(text)
    except Exception as e:
        return _err(e)
    return "投稿しました。\n" + format_note(note)


@mcp.tool()
def reply_to_note(note_id: str, text: str) -> str:
    """指定したノートに返信します。実行前に、必ず返信文を読み上げて本人の確認を取ってください。"""
    try:
        note = create_note(text, reply_id=note_id)
    except Exception as e:
        return _err(e)
    return "返信しました。\n" + format_note(note)


@mcp.tool()
def react_to_note(note_id: str, reaction: str = "❤️") -> str:
    """指定したノートにリアクション（いいね相当）を付けます。reactionは絵文字1つです。"""
    try:
        create_reaction(note_id, reaction)
    except Exception as e:
        return _err(e)
    return f"ノート {note_id} に {reaction} でリアクションしました。"


if __name__ == "__main__":
    mcp.run()
