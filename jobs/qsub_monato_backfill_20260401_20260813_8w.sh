#!/bin/sh
#$ -S /bin/sh
#$ -cwd
#$ -V
#$ -q all.q
#$ -pe openmpi8 8
#$ -N monato_bf_8w
#$ -o logs/monato_backfill_qsub_20260401_20260813_8w.out
#$ -e logs/monato_backfill_qsub_20260401_20260813_8w.err

ulimit -s unlimited
export OMP_NUM_THREADS=8
cd "$SGE_O_WORKDIR" || exit 1
PYTHON_BIN="./.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="$(command -v python3)"
fi

# Monato の年別インデックスは 401 (購読者専用) のため、Nova! ページに載らなくなった
# publika 記事 (ID 13873–13958 の帯) を連番プローブで回収する。
# 既存の 取得文書ekde20260401/monato_*.jsonl と合流し、staging に月別ファイルを再生成。
OUT_DIR="取得文書ekde20260401_monato_staging"
LOG_PREFIX="logs/monato_backfill_20260401_20260813_8w"
mkdir -p "$OUT_DIR" "$(dirname "$LOG_PREFIX")"

"$PYTHON_BIN" "Monato/backfill_publika_probe.py" \
  --id-start 13873 \
  --id-end 14005 \
  --start "2026-04-01" \
  --end "2026-08-13" \
  --workers 8 \
  --throttle 1.0 \
  --existing "取得文書ekde20260401" \
  --out "$OUT_DIR" \
  > "${LOG_PREFIX}.out" 2> "${LOG_PREFIX}.err"
