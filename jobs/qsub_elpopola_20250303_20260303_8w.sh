#!/bin/sh
#$ -S /bin/sh
#$ -cwd
#$ -V
#$ -q all.q
#$ -pe openmpi8 8
#$ -N elpopola_1y_8w
#$ -o logs/elpopola_qsub_20250303_20260303_8w.out
#$ -e logs/elpopola_qsub_20250303_20260303_8w.err

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
LOG_PREFIX="logs/elpopola_parallel_20250303_20260303_8w"
mkdir -p "$OUT_DIR" "$(dirname "$LOG_PREFIX")"

"$PYTHON_BIN" "El Popola Ĉinio/parallel_scraper.py" \
  --start "$START" \
  --end "$END" \
  --workers 8 \
  --method feed \
  --throttle 1.0 \
  --split-by month \
  --out "$OUT_DIR" \
  > "${LOG_PREFIX}.out" 2> "${LOG_PREFIX}.err"
