#!/bin/sh
set -eu

# Submit 6 Esperanto site jobs for 2026-04-01 to 2026-08-13.
# Pola Retradio is intentionally excluded (誤字脱字が多く整形が大変なため除外).
# All jobs use 8 cores and output to 取得文書ekde20260401/.

qsub jobs/qsub_elpopola_20260401_20260813_8w.sh
qsub jobs/qsub_global_voices_eo_20260401_20260813_8w.sh
qsub jobs/qsub_monato_20260401_20260813_8w.sh
qsub jobs/qsub_scivolemo_20260401_20260813_8w.sh
qsub jobs/qsub_uea_facila_20260401_20260813_8w.sh
qsub jobs/qsub_libera_folio_20260401_20260813_8w.sh

echo "Submitted 6 jobs (8 workers each, Pola Retradio excluded). Output: 取得文書ekde20260401/"
echo "Use 'qstat' to monitor. Logs in logs/*20260401_20260813*."
