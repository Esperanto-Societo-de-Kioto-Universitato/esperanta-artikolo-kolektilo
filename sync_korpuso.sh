#!/bin/sh
set -eu

# 取得文書フォルダをプライベートのコーパスリポジトリへ同期し、commit & push する。
# コーパスリポジトリ: git@github.com:Esperanto-Societo-de-Kioto-Universitato/esperanta-artikolo-korpuso.git
# (記事本文は著作権保護のため公開リポジトリには置かない。詳細は README の「リポジトリの方針」参照)

KORPUSO_DIR="${KORPUSO_DIR:-$HOME/esperanta-artikolo-korpuso}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ ! -d "$KORPUSO_DIR/.git" ]; then
  echo "エラー: $KORPUSO_DIR が git リポジトリではありません" >&2
  exit 1
fi

cd "$SCRIPT_DIR"
synced=0
for d in 取得文書*/; do
  [ -d "$d" ] || continue
  case "$d" in
    *_staging/) echo "スキップ (作業用staging): $d"; continue ;;
  esac
  echo "同期: $d -> $KORPUSO_DIR/$d"
  rsync -a --delete "$d" "$KORPUSO_DIR/$d"
  synced=$((synced + 1))
done

# ローカルで削除・改名されたフォルダを korpuso 側からも取り除く
# (ローカルに1つも無い場合は誤爆防止のためスキップ)
if [ "$synced" -gt 0 ]; then
  for kd in "$KORPUSO_DIR"/取得文書*/; do
    [ -d "$kd" ] || continue
    name="$(basename "$kd")"
    if [ ! -d "$SCRIPT_DIR/$name" ]; then
      echo "削除 (ローカルに存在しない): $name"
      rm -rf "$kd"
    fi
  done
fi

cd "$KORPUSO_DIR"
git add -A
if git diff --cached --quiet; then
  # 新しい変更が無くても、過去に push へ失敗したコミットが残っていれば送る
  git push origin main
  echo "変更なし (未pushコミットの反映のみ確認)"
  exit 0
fi
git commit -m "sync: $(date +%Y-%m-%d) $(git -C "$SCRIPT_DIR" rev-parse --short HEAD 2>/dev/null || echo '')"
git push origin main
echo "コーパスを同期・push しました"
