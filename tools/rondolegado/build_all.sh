#!/bin/sh
# 輪読候補一式を作り直す: 一覧・抽出 md → 注釈ルビ → 見出し付け → 配置・zip
# 使い方: build_all.sh <kolektilo の作業フォルダ> <注釈ツールの Esperanto-Kanji-Ruby-JA フォルダ> <出力フォルダ> [--no-place]
#   PYTHON           build_rinlist.py・finish_ruby.py を動かす Python (既定 python3。標準ライブラリだけで動く)
#   ANNOTATOR_PYTHON 注釈ツールの requirements を入れた Python (既定 python3)
# 出力フォルダは作業用で、消さずに使い回す (ruby_raw/ は入力の md が変わった記事だけ変換し直す)。
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
WD=$1
APP=$2
OUT=$3
PLACE=${4:-}
PY=${PYTHON:-python3}
APY=${ANNOTATOR_PYTHON:-python3}
N=rondolegado_kandidatoj_202609
mkdir -p "$OUT"
OUT=$(cd "$OUT" && pwd)
"$PY" "$HERE/build_rinlist.py" --wd "$WD" --out "$OUT" --dropped "$OUT/dropped_paragraphs.json"
"$APY" "$HERE/annotate.py" "$APP" "$OUT/$N" "$OUT/ruby_raw"
"$PY" "$HERE/finish_ruby.py" "$OUT"
if [ "$PLACE" != "--no-place" ]; then
  sh "$HERE/place_kandidatoj.sh" "$OUT" "$WD"
fi
