# Raspberry Pi デモ用シンプル実行ディレクトリ

ラズベリーパイ上で最小構成（Pi5 単独、または Pi5 をメインに Pi4 を補助）でデモを行う際のスクリプトと手順をまとめる。

## 目的
- Streamlit を起動せずに、CLI から **入力 → 匿名化 → 評価** を一気通貫で実行できるようにする。
- `webapp/app.py` や `evaluate.py` のロジックをそのまま利用しつつ、デモ確認に必要な最小限のパラメータだけを扱う。

## ファイル構成
| ファイル | 説明 |
| --- | --- |
| `run_once.py` | フォーム初期値＋任意の上書きを使って匿名化し、その結果を即座に評価する CLI スクリプト。 |

## デモ手順
1. `rp3` (Raspberry Pi 5/8GB) で `uv sync` を実行して依存パッケージを揃える。  
2. `UV_CACHE_DIR=webapp/outputs/.uv-cache uv run python webapp/demo_simple/run_once.py --algorithm main` を実行すると、Bi 読み込み→匿名化→評価→結果表示が 1 コマンドで完了する。  
3. 任意で `--entry-json overrides.json` を渡すと、JSON に記述した列名・値でフォーム入力を上書きできる。  
4. 評価結果サマリは標準出力へ表示され、詳細は従来通り `webapp/outputs/` 配下に保存される。

## 注意点
- 本ディレクトリはデモ専用のため、実運用時は `webapp/app.py` + Streamlit を使用する。  
- 2 台構成の高度な切り替えは行わず、評価も同一マシンで実行する。重い処理を別ノードに逃がしたい場合は `webapp/raspi-deployment` の設計に従って拡張すること。  
- `run_once.py` の実行は既存モジュール (`anonymize.py`, `evaluate.py`) をラップするだけなので、ロジック変更はそちらで管理する。
