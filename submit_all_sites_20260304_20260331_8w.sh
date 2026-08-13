#!/bin/sh
set -eu

# Submit 5 non-Monato site jobs for the 2026-03-04..2026-03-31 gap.
# (Monato's March was already fetched via jobs/qsub_monato_20260304_20260331_archive_8w.sh;
#  Pola Retradio is excluded by policy.)

qsub jobs/qsub_elpopola_20260304_20260331_8w.sh
qsub jobs/qsub_global_voices_eo_20260304_20260331_8w.sh
qsub jobs/qsub_libera_folio_20260304_20260331_8w.sh
qsub jobs/qsub_scivolemo_20260304_20260331_8w.sh
qsub jobs/qsub_uea_facila_20260304_20260331_8w.sh

echo "Submitted 5 jobs (8 workers each). Output: 取得文書ekde20260401/"
