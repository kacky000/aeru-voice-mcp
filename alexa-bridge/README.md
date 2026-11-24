# ミューズ ブリッジ（Alexaスキル試作）

Echoに話した内容を、利用者のMuseのメールアドレスへ橋渡しする
Alexaスキルの試作一式です。受け取り側のMuseの処理ルールは
リポジトリ直下の `BRIDGE_PROTOCOL.md` を見てください。

## 構成

- `skill/interaction-model.ja.json` — 対話モデル（日本語）
  呼び出し名「ミューズ ブリッジ」
- `lambda/lambda_function.py` — バックエンド（ASK SDKなし、SESで送信）
- `lambda/test_lambda.py` — ローカルテスト（AWSなしで実行可）

## 開発コンソールでの作り方（Alexa-hosted）

1. https://developer.amazon.com/alexa/console/ask にAmazonアカウントで
   サインインし、「スキルを作成」：
   - 名前：ミューズ ブリッジ
   - 言語：日本語（日本）
   - モデル：カスタム
   - ホスティング：Alexa-Hosted (Python)
2. 「ビルド」→「JSONエディター」に `interaction-model.ja.json` の内容を
   貼って保存し、「モデルをビルド」
3. 「コード」に `lambda_function.py` の内容を貼る
   （Alexa-hostedのエントリポイントは lambda_function.py）
4. 設定値を決める。Alexa-hostedには環境変数の編集画面がないため、
   試作ではコード先頭の `CONFIG` に3つのアドレスを直接書く：
   - `BRIDGE_TO`：受け取り側Museのメールアドレス
   - `BRIDGE_FROM`：SESで検証済みの送信元アドレス
   - `REPLY_TO`：利用者本人のメールアドレス（Museの返信先）
5. SESの準備（AWSコンソール、リージョンは任意）：
   - 送信元アドレス（BRIDGE_FROM）を検証する
   - サンドボックスの間は、宛先（BRIDGE_TO）も検証が必要
6. 「テスト」タブでスキルを有効化し、シミュレーターで
   「ミューズブリッジを開いて」→「最近の投稿を読んでって頼んで」
   と発話して、メールが届くか確認する
7. 実機テストは「ベータテスト」で協力者のAmazonアカウントの
   メールアドレスを招待して行う

## 安全のための注意

- このスキルは公開せず、ベータ（招待制）の範囲でのみ使う
- 橋メールの送信元は固定し、受け取り側はその送信元以外からの
  橋メールを実行しない（BRIDGE_PROTOCOL.md 参照）
- やのっち本人のEcho・Alexaアカウントでは実験しない。
  必ず協力者の環境で検証してから移す
