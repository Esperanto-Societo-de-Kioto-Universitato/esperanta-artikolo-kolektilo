#!/bin/sh
#$ -S /bin/sh
#$ -cwd
#$ -V
#$ -q all.q
#$ -pe openmpi8 8
#$ -N libera_folio_1y_8w
#$ -o logs/libera_folio_qsub_20250303_20260303_8w.out
#$ -e logs/libera_folio_qsub_20250303_20260303_8w.err

ulimit -s unlimited
export OMP_NUM_THREADS=8
cd "$SGE_O_WORKDIR" || exit 1
PYTHON_BIN="./.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="$(command -v python3)"
fi
START="2025-03-03"
END="2026-03-03"

OUT_DIR="取得文書ekde20260303"
LOG_PREFIX="logs/libera_folio_parallel_20250303_20260303_8w"
mkdir -p "$OUT_DIR" "$(dirname "$LOG_PREFIX")"

# Libera Folio: --include-audio は非対応
"$PYTHON_BIN" "Libera Folio/parallel_scraper.py" \
  --start "$START" \
  --end "$END" \
  --workers 8 \
  --method rest \
  --throttle 0.5 \
  --split-by month \
  --out "$OUT_DIR" \
  > "${LOG_PREFIX}.out" 2> "${LOG_PREFIX}.err"
