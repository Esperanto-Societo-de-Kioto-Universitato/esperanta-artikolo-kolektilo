#!/bin/sh
set -eu

# Submit all 7 Esperanto site jobs for 2025-03-03 to 2026-03-03.
# All jobs use 8 cores and output to 取得文書ekde20260303/.

qsub jobs/qsub_elpopola_20250303_20260303_8w.sh
qsub jobs/qsub_global_voices_eo_20250303_20260303_8w.sh
qsub jobs/qsub_monato_20250303_20260303_8w.sh
qsub jobs/qsub_scivolemo_20250303_20260303_8w.sh
qsub jobs/qsub_pola_retradio_20250303_20260303_8w.sh
qsub jobs/qsub_uea_facila_20250303_20260303_8w.sh
qsub jobs/qsub_libera_folio_20250303_20260303_8w.sh

echo "Submitted 7 jobs (8 workers each). Output: 取得文書ekde20260303/"
echo "Use 'qstat' to monitor. Logs in logs/*20250303_20260303*."
