#!/bin/sh
#$ -S /bin/sh
#$ -cwd
#$ -V
#$ -q all.q
#$ -pe openmpi8 8
#$ -N uea_facila_apr_8w
#$ -o logs/uea_facila_qsub_20260401_20260813_8w.out
#$ -e logs/uea_facila_qsub_20260401_20260813_8w.err

ulimit -s unlimited
export OMP_NUM_THREADS=8
cd "$SGE_O_WORKDIR" || exit 1
PYTHON_BIN="./.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="$(command -v python3)"
fi
START="2026-04-01"
END="2026-08-13"

OUT_DIR="取得文書ekde20260401"
LOG_PREFIX="logs/uea_facila_parallel_20260401_20260813_8w"
mkdir -p "$OUT_DIR" "$(dirname "$LOG_PREFIX")"

# UEA Facila: --method と --include-audio は非対応
"$PYTHON_BIN" "Uea_Facila/parallel_scraper.py" \
  --start "$START" \
  --end "$END" \
  --workers 8 \
  --throttle 0.5 \
  --split-by month \
  --out "$OUT_DIR" \
  > "${LOG_PREFIX}.out" 2> "${LOG_PREFIX}.err"
