#!/bin/sh
#$ -S /bin/sh
#$ -cwd
#$ -V
#$ -q all.q
#$ -pe openmpi8 8
#$ -N monato_sep_8w
#$ -o logs/monato_qsub_20260701_20260914_8w.out
#$ -e logs/monato_qsub_20260701_20260914_8w.err

ulimit -s unlimited
export OMP_NUM_THREADS=8
cd "$SGE_O_WORKDIR" || exit 1
PYTHON_BIN="./.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="$(command -v python3)"
fi
# 取得文書ekde20260814 (2026-08-14〜09-14) 用。07-01〜08-13 は前フォルダとの重複区間で、
# 前回実行 (2026-08-13) 後に公開された記事の回収と既存データとの突合に使う。
# 出力は staging に置き、URL 単位で重複除去してから各フォルダへ振り分ける。
START="2026-07-01"
END="2026-09-14"

OUT_DIR="取得文書ekde20260814_staging"
LOG_PREFIX="logs/monato_parallel_20260701_20260914_8w"
mkdir -p "$OUT_DIR" "$(dirname "$LOG_PREFIX")"

"$PYTHON_BIN" "Monato/parallel_scraper.py" \
  --start "$START" \
  --end "$END" \
  --workers 8 \
  --method both \
  --throttle 1.0 \
  --split-by month \
  --out "$OUT_DIR" \
  > "${LOG_PREFIX}.out" 2> "${LOG_PREFIX}.err"
