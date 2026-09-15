#!/bin/sh
set -eu

# 取得文書ekde20260814 (2026-08-14〜2026-09-14) 用の 6 サイト取得。
# 2026-07-01〜08-13 は前フォルダ 取得文書ekde20260401 との重複区間で、前回実行後に
# 公開された記事の回収と既存データとの突合に使う。出力は 取得文書ekde20260814_staging/ に
# 置き、URL 単位で既存コーパスと重複除去してから各フォルダへ振り分ける。
# Pola Retradio はユーザー方針により除外 (誤字脱字が多く整形が大変なため)。

qsub jobs/qsub_elpopola_20260701_20260914_8w.sh
qsub jobs/qsub_global_voices_eo_20260701_20260914_8w.sh
qsub jobs/qsub_monato_20260701_20260914_8w.sh
qsub jobs/qsub_scivolemo_20260701_20260914_8w.sh
qsub jobs/qsub_uea_facila_20260701_20260914_8w.sh
qsub jobs/qsub_libera_folio_20260701_20260914_8w.sh

echo "Submitted 6 jobs (8 workers each, Pola Retradio excluded). Output: 取得文書ekde20260814_staging/"
echo "Use 'qstat' to monitor. Logs in logs/*20260701_20260914*."
