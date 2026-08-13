#!/bin/sh
#$ -S /bin/sh
#$ -cwd
#$ -V
#$ -q all.q
#$ -pe openmpi8 8
#$ -N monato_bf25_8w
#$ -o logs/monato_backfill_qsub_20250303_20260303_8w.out
#$ -e logs/monato_backfill_qsub_20250303_20260303_8w.err

ulimit -s unlimited
export OMP_NUM_THREADS=8
cd "$SGE_O_WORKDIR" || exit 1
PYTHON_BIN="./.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="$(command -v python3)"
fi

# 旧コーパス (取得文書ekde20260303, 2025-03-03〜2026-03-03) の Monato 欠落分を回収する。
# 事前サンプリングによる帯マップ: 13700=2025-03-27, 13830=2025-11-28, 13850=2026-01-29。
# 下限は adapto 日付の非単調性への余裕を見て 13550 (2024-05-31) とする。
# 既存の monato_2026-01/02 (21 ID) は --existing で自動スキップ・合流される。
OUT_DIR="取得文書ekde20260303_monato_staging"
LOG_PREFIX="logs/monato_backfill_20250303_20260303_8w"
mkdir -p "$OUT_DIR" "$(dirname "$LOG_PREFIX")"

"$PYTHON_BIN" "Monato/backfill_publika_probe.py" \
  --id-start 13550 \
  --id-end 13872 \
  --start "2025-03-03" \
  --end "2026-03-03" \
  --workers 8 \
  --throttle 1.0 \
  --existing "取得文書ekde20260303" \
  --out "$OUT_DIR" \
  > "${LOG_PREFIX}.out" 2> "${LOG_PREFIX}.err"
