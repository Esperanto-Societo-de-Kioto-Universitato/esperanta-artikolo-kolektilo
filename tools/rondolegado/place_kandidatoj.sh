#!/bin/sh
# 抽出 md・一覧 md・ルビ付き HTML (Netlify Drop 用) を <作業フォルダ>/取得文書ekde20260814/ に配置し、zip を作る
# 使い方: place_kandidatoj.sh <出力フォルダ> <kolektilo の作業フォルダ>
set -eu
OUT=$1
WD=$2
F="$WD/取得文書ekde20260814"
N=rondolegado_kandidatoj_202609
test -d "$F"
test "$(ls "$OUT/$N" | wc -l)" -eq 50
test "$(ls "$OUT/netlify" | wc -l)" -eq 51
rsync -a --delete "$OUT/$N/" "$F/$N/"
rsync -a --delete "$OUT/netlify/" "$F/${N}_ruby/"
cp "$OUT/$N.md" "$F/"
rm -f "$F/${N}_ruby.zip"
( cd "$F" && zip -q -r -X "${N}_ruby.zip" "${N}_ruby" )
echo "md $(ls "$F/$N" | wc -l) / html $(ls "$F/${N}_ruby" | wc -l) / zip $(du -h "$F/${N}_ruby.zip" | cut -f1)"
