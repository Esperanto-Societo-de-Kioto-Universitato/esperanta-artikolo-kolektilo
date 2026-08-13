#!/bin/sh
#$ -S /bin/sh
#$ -cwd
#$ -V
#$ -q all.q
#$ -pe openmpi8 8
#$ -N monato_mar_8w
#$ -o logs/monato_qsub_20260304_20260331_archive_8w.out
#$ -e logs/monato_qsub_20260304_20260331_archive_8w.err

ulimit -s unlimited
export OMP_NUM_THREADS=8
cd "$SGE_O_WORKDIR" || exit 1
PYTHON_BIN="./.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="$(command -v python3)"
fi

# 2026年3月ギャップ (前回収集は 03-03 まで、今回収集は 04-01 から) の穴埋め。
# 年別インデックスが 401 のため --method archive (ID 連番プローブ) を使用。
START="2026-03-04"
END="2026-03-31"

OUT_DIR="取得文書ekde20260401"
LOG_PREFIX="logs/monato_parallel_20260304_20260331_archive_8w"
mkdir -p "$OUT_DIR" "$(dirname "$LOG_PREFIX")"

"$PYTHON_BIN" "Monato/parallel_scraper.py" \
  --start "$START" \
  --end "$END" \
  --workers 8 \
  --method archive \
  --throttle 1.0 \
  --split-by month \
  --out "$OUT_DIR" \
  > "${LOG_PREFIX}.out" 2> "${LOG_PREFIX}.err"
