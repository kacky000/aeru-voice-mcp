# AERU音声操作セットアップ指示書（受け取り側のMuseへ）

あなたは受け取り側のClaude（Muse）です。この文書は、AERU SNS
（https://wa-community.xsns.jp、Misskey製）を声で操作できる仕組みを、
あなたの環境にセットアップするための指示書です。

## 大原則

- 利用者は画面操作が難しい方です。技術作業はすべてあなたが担ってください。
- 利用者（または同席の支援者）に頼んでよいのは、次の2点だけです。
  1. AERUの設定画面でアクセストークンをコピーすること
  2. あなたが出す安全な入力カード（Secure Vault）にトークンを貼ること
- アクセストークンをチャット本文に貼るよう求めてはいけません。
  トークンをファイル・ログ・メモリに書き写してもいけません。
- 投稿・返信は、実行前に必ず文面を利用者に読み上げ、確認を取ってください。

## 構成ファイル（このリポジトリの中身）

- `aeru_voice_mcp.py` — MCPサーバー本体（単一ファイル）。ツール8個：
  whoami / get_home_timeline / get_notifications / get_user_notes /
  get_note / post_note / reply_to_note / react_to_note
- `aeru_cli.py` — サーバーを起動して1ツールだけ実行するCLI（動作確認と日常利用に使う）
- `SETUP_FOR_MUSE.md` — この文書

## セットアップ手順

### 1. 配置と依存関係

ワークスペースに `aeru-voice-mcp` フォルダを作り、リポジトリの
`aeru_voice_mcp.py` と `aeru_cli.py` を置く。そのフォルダで：

```text
python3 -m venv .venv
.venv/bin/pip install "mcp<2"
```

（mcp 2.xではFastMCPのAPIが変わっているため、必ず `mcp<2` を指定する。）

### 2. コネクタドキュメントの作成

`~/workspace/custom-connectors/custom.aeru-misskey/connector.yaml`：

```yaml
id: "custom.aeru-misskey"
title: "AERU SNS (Misskey)"
description: "Use the AERU SNS for WA Misskey API through its registered access token: read timelines and notifications, post, reply and react."
include_in_prompt: false
require_auth: true
aliases: ["Aeru", "AERU SNS for WA", "wa-community"]
```

`~/workspace/custom-connectors/custom.aeru-misskey/CONNECTOR.md` には、
接続登録情報（下記3のJSON）、認証は登録済みコネクション経由の
サロゲートで行うこと、トークンを文書やコードに書かないことを明記する。

### 3. アクセストークンの登録（安全な入力カード経由）

`credentials.request_api_access` を次の内容で呼ぶ：

```json
{
  "provider": "aeru-misskey",
  "auth_scheme": "api_key",
  "placement": "bearer_header",
  "api_hosts": ["wa-community.xsns.jp"]
}
```

利用者への案内（この通りに伝える）：
- AERUにログイン → 設定 → API（直接開くなら https://wa-community.xsns.jp/settings/api ）
- 「アクセストークン」の文字列をコピーする。**「再生成」ボタンは押さない**
  （押すと既存の連携が切れることがある）
- カードの入力欄に貼る。貼った後、欄に文字が入ったかと送信ボタンが
  有効になったかを確認してもらう

既知のトラブル：チャット内のコネクターカードが「This connection link is
invalid」になることがある。その場合は、別のチャット（メイン等）の
セッションでリンクを発行し直すと通ることがある（実績あり）。

### 4. 動作確認

登録が完了したら、読み取りだけをこの順で確認し、結果を利用者に報告する：

```text
.venv/bin/python aeru_cli.py whoami
.venv/bin/python aeru_cli.py get_home_timeline --limit 3
.venv/bin/python aeru_cli.py get_notifications --limit 3
```

- whoamiで利用者本人のアカウント名が返れば認証OK。
- 401/403のときは、まず登録が完了しているかを確認する。それでも
  解消しない場合のみ、再登録（reconnect）を案内する。

### 5. 日常の使い方

利用者から声やチャットで頼まれたら、`aeru_cli.py` 経由でツールを実行する：

- 「最近の投稿を読んで」→ `get_home_timeline --limit 10`（長い場合は数件ずつ）
- 「通知ある？」→ `get_notifications --limit 10`
- 「○○さんの投稿」→ `get_user_notes --username <ID> --limit 5`
- 「これ投稿して」→ 文面を読み上げて確認 → `post_note --text "…"`
- 「返信して」→ 対象のノートIDと文面を確認 → `reply_to_note --note-id <ID> --text "…"`
- 「いいねして」→ `react_to_note --note-id <ID>`（既定のリアクションは ❤️）

MCPサーバーとして常駐させる場合は `aeru_voice_mcp.py` がstdioサーバーに
なる。クライアントが子プロセスとして起動する際は、環境変数（ネットワーク
や認証ヘルパーが依存するもの）を子プロセスへ渡すこと。渡し忘れると
接続エラー（SSL系）になる。

## 注意事項

- このサーバーの接続先は wa-community.xsns.jp のみ。リダイレクトは無効化済み。
- 書き込み系は自動リトライしない（二重投稿防止）。読み取り系は接続断のみ
  最大3回まで自動リトライする。
- AERUは連合のない閉じたサーバーなので、投稿は localOnly で作成される。
- うまくいかないことがあれば、開発者のカッキーに連絡するよう利用者に伝える。
