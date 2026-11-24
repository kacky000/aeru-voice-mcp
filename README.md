# aeru-voice-mcp

AERU SNS for WA（Misskey製、https://wa-community.xsns.jp）を、
Muse（Muse）から声で操作するためのMCPサーバー。

タイムラインや通知の読み上げ、投稿・返信・リアクションを、
利用者本人のアクセストークンで、その人のMuse環境の中だけで行います。
中央サーバーは使いません。

## 使い方

- 人の手順：`GUIDE_FOR_HUMANS.md` を見てください。
- Museへのセットアップ指示：`SETUP_FOR_MUSE.md` を見てください。
  （使いたい人のMuseにこのリポジトリを渡せば、Museがセットアップします）

## ファイル

- `aeru_voice_mcp.py` — MCPサーバー本体（単一ファイル、ツール8個）
- `aeru_cli.py` — 1ツール実行用CLI
- `SETUP_FOR_MUSE.md` — 受け取り側Claudeへの指示書
- `GUIDE_FOR_HUMANS.md` — 人向けガイド

## 開発

カッキー（@kacky、AERU SNS for WA）。やのっちが声だけでAERUを
楽しめるようにするためのプロジェクトです。
