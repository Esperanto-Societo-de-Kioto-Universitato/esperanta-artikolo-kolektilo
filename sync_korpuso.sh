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
for d in 取得文書*/; do
  [ -d "$d" ] || continue
  echo "同期: $d -> $KORPUSO_DIR/$d"
  rsync -a --delete "$d" "$KORPUSO_DIR/$d"
done

cd "$KORPUSO_DIR"
git add -A
if git diff --cached --quiet; then
  echo "変更なし (コーパスは最新)"
  exit 0
fi
git commit -m "sync: $(date +%Y-%m-%d) $(git -C "$SCRIPT_DIR" rev-parse --short HEAD 2>/dev/null || echo '')"
git push origin main
echo "コーパスを同期・push しました"
