#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UEA Facila の記事収集を複数プロセスで分割実行し、最後に結合して書き出す CLI。
Monato 版の並列実装に合わせ、まず URL を一括収集してから URL をワーカー間で分割し、
本文取得を並列化します。
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from dataclasses import replace
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Tuple

# 親ディレクトリから shared lib を import できるようにする
HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from retradio_lib import ScrapeConfig, Article, export_all  # noqa: E402
from Uea_Facila.uea_facila_lib import (  # noqa: E402
    COLLECT_ERRORS,
    collect_urls,
    fetch_article,
    shared_session as _session,
    set_progress_callback,
)

DEFAULT_BASE_URL = "https://uea.facila.org"
SOURCE_LABEL = "UEA Facila (uea.facila.org)"
PREFIX = "uea_facila"


@dataclass
class WorkerArgs:
    index: int
    cfg: ScrapeConfig
    urls: List[str]


@dataclass
class WorkerResult:
    index: int
    processed_urls: List[str]
    articles: List[Article]
    failures: List[str]
    timer_fetch: float
    skipped_out_of_range: List[str]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="UEA Facila 期間指定スクレイパー (並列版)")
    p.add_argument("--start", help="開始日 YYYY-MM-DD")
    p.add_argument("--end", help="終了日 YYYY-MM-DD")
    p.add_argument(
        "--days",
        type=int,
        help="終了日から遡った直近N日間を収集（--end 未指定時は今日を終了日にします）",
    )
    p.add_argument(
        "--workers",
        type=int,
        default=4,
        help="並列実行するワーカー数（1以上）",
    )
    p.add_argument(
        "--out",
        default="output",
        help="書き出し先ディレクトリ",
    )
    p.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="対象サイトのベース URL",
    )
    p.add_argument(
        "--throttle",
        type=float,
        default=0.5,
        help="1リクエスト毎の遅延秒数（並列数に応じて適宜調整してください）",
    )
    p.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="活動ストリーム・カテゴリ一覧の最大ページ数（省略・0 は 50。2020 年以前まで遡るときは 400 などを指定）",
    )
    p.add_argument(
        "--no-cache",
        action="store_true",
        help="requests-cache を使わない（並列実行時は自動で無効化されます）",
    )
    p.add_argument(
        "--split-by",
        choices=["none", "year", "month"],
        default="none",
        help="最終的な出力ファイルを年単位または月単位で分割",
    )
    return p.parse_args()


def _parse_day(s: str, name: str) -> date:
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise SystemExit(f"{name} は YYYY-MM-DD 形式で指定してください。") from None


def resolve_date_range(args: argparse.Namespace) -> Tuple[date, date]:
    if args.start is None and args.days is None:
        raise SystemExit("--start もしくは --days の指定が必要です。")
    if args.days is not None and args.start:
        raise SystemExit("--start と --days は同時に指定できません。どちらか一方を使ってください。")
    if args.start:
        if not args.end:
            raise SystemExit("--start を指定する場合は --end も指定してください。")
        start_d = _parse_day(args.start, "--start")
        end_d = _parse_day(args.end, "--end")
    else:
        end_raw = args.end or date.today().isoformat()
        end_d = _parse_day(end_raw, "--end")
        days = args.days if args.days is not None else 30
        if days <= 0:
            raise SystemExit("--days は正の整数で指定してください。")
        start_d = end_d - timedelta(days=days - 1)
    if end_d < start_d:
        raise SystemExit("終了日は開始日以降である必要があります。")
    return start_d, end_d


def _sort_articles(articles: Iterable[Article]) -> List[Article]:
    def sort_key(article: Article):
        if article.published:
            pub_naive = (
                article.published.replace(tzinfo=None)
                if article.published.tzinfo
                else article.published
            )
            return (pub_naive, article.url)
        return (datetime.max, article.url)

    return sorted(articles, key=sort_key)


def _chunk_urls(data: List[str], chunks: int) -> List[List[str]]:
    if chunks <= 1 or len(data) <= 1:
        return [data]
    size, remainder = divmod(len(data), chunks)
    out: List[List[str]] = []
    start = 0
    for idx in range(chunks):
        extra = 1 if idx < remainder else 0
        end = start + size + extra
        out.append(data[start:end])
        start = end
    return [chunk for chunk in out if chunk]


def worker_task(args: WorkerArgs) -> WorkerResult:
    cfg = args.cfg
    cfg.normalize()

    session = _session(cfg)
    articles: List[Article] = []
    failures: List[str] = []
    skipped_out_of_range: List[str] = []

    timer_start = time.perf_counter()
    for url in args.urls:
        try:
            article = fetch_article(url, cfg, session)
            if article.published and not (cfg.start_date <= article.published.date() <= cfg.end_date):
                skipped_out_of_range.append(f"{url} ({article.published.date()})")
                continue
            articles.append(article)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{url} ({exc})")
        finally:
            if cfg.throttle_sec > 0:
                time.sleep(cfg.throttle_sec)
    timer_after_fetch = time.perf_counter()

    return WorkerResult(
        index=args.index,
        processed_urls=args.urls,
        articles=articles,
        failures=failures,
        timer_fetch=timer_after_fetch - timer_start,
        skipped_out_of_range=skipped_out_of_range,
    )


def main() -> None:
    args = parse_args()
    start_d, end_d = resolve_date_range(args)

    if args.workers <= 0:
        raise SystemExit("--workers には 1 以上の整数を指定してください。")

    cfg_base = ScrapeConfig(
        base_url=args.base_url,
        start_date=start_d,
        end_date=end_d,
        throttle_sec=args.throttle,
        max_pages=args.max_pages,
        timeout_sec=60,
        max_retries=5,
        method="feed",  # dummy (not used by uea_facila_lib)
        include_audio_links=True,
        use_cache=not args.no_cache,
        source_label=SOURCE_LABEL,
    )

    set_progress_callback(None)

    timer_collect_start = time.perf_counter()
    try:
        url_result = collect_urls(cfg_base)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] URL 収集に失敗しました: {exc}", file=sys.stderr)
        sys.exit(1)
    collect_errors = list(COLLECT_ERRORS)
    if collect_errors:
        print("[WARN] 一部の一覧ページから記事 URL を集められませんでした (URL が欠けている可能性があります):", file=sys.stderr)
        for err in collect_errors:
            print(f"  - {err}", file=sys.stderr)
    total_collect = time.perf_counter() - timer_collect_start
    urls = url_result.urls
    total_urls = len(urls)
    skipped_out_of_range: List[str] = []

    if total_urls == 0:
        print(
            f"[INFO] 並列スクレイプ開始: {start_d} ～ {end_d} (workers=0)"
        )
        print("[INFO] URL が見つかりませんでした。")
        all_articles: List[Article] = []
        overall_failures: List[str] = []
        total_fetch = 0.0
    else:
        actual_workers = min(args.workers, total_urls)
        if actual_workers < args.workers:
            print(f"[INFO] 取得件数に合わせてワーカー数を {actual_workers} に調整しました。")
        if actual_workers > 1 and cfg_base.use_cache:
            cfg_base.use_cache = False
            print("[INFO] 並列実行では requests-cache を無効化しました（SQLite のロック競合回避）。")

        print(
            f"[INFO] 並列スクレイプ開始: {start_d} ～ {end_d} (workers={actual_workers})"
        )

        chunks = _chunk_urls(urls, actual_workers)
        workers: List[WorkerArgs] = [
            WorkerArgs(index=i, cfg=cfg_base, urls=chunk) for i, chunk in enumerate(chunks, start=1)
        ]

        results: List[WorkerResult] = []
        total_fetch = 0.0
        overall_failures: List[str] = []

        if actual_workers == 1:
            results.append(worker_task(workers[0]))
        else:
            with ProcessPoolExecutor(max_workers=actual_workers) as executor:
                future_map = {executor.submit(worker_task, worker): worker for worker in workers}
                for future in as_completed(future_map):
                    worker = future_map[future]
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as exc:  # noqa: BLE001
                        # 1 ワーカーの異常終了で他のワーカーの取得分まで捨てない。担当 URL はすべて失敗として扱う
                        print(f"[ERROR] ワーカー #{worker.index} が失敗: {exc}", file=sys.stderr)
                        overall_failures.extend(
                            f"{url} (ワーカー #{worker.index} が異常終了: {exc})" for url in worker.urls
                        )

        results.sort(key=lambda r: r.index)
        all_articles = []
        for result in results:
            total_fetch += result.timer_fetch
            overall_failures.extend(result.failures)
            all_articles.extend(result.articles)
            skipped_out_of_range.extend(result.skipped_out_of_range)
            print(
                f"[INFO] ワーカー #{result.index}: URL {len(result.processed_urls)} 件 | 本文 {len(result.articles)} 本 | "
                f"期間外 {len(result.skipped_out_of_range)} 本 | "
                f"本文取得 {result.timer_fetch:.1f}s"
            )

    all_articles = _sort_articles(all_articles)
    print(f"[INFO] 抽出完了: {len(all_articles)} 本")
    if url_result.earliest_date and url_result.latest_date:
        print(
            f"[INFO] URL 範囲（推定公開日）: {url_result.earliest_date} ～ {url_result.latest_date}"
        )
    print(
        f"[INFO] 累計時間: URL収集 {total_collect:.1f}s / 本文取得 {total_fetch:.1f}s"
    )
    print(f"[INFO] 本文取得後に期間外で除外: 合計 {len(skipped_out_of_range)} 本")
    for item in skipped_out_of_range:
        print(f"  - {item}")
    if total_urls > 0 and overall_failures:
        print("[WARN] 取得失敗一覧:", file=sys.stderr)
        for fail in overall_failures:
            print(f"  - {fail}", file=sys.stderr)

    # 出力
    def _group_articles(articles: Iterable[Article], mode: str):
        if mode == "none":
            return [("all", list(articles))]
        from collections import OrderedDict
        groups: Dict[str, List[Article]] = OrderedDict()
        for art in articles:
            if art.published:
                d = art.published.date()
                key = f"{d.year}" if mode == "year" else f"{d.year}-{d.month:02d}"
            else:
                key = "unknown"
            groups.setdefault(key, []).append(art)
        return list(groups.items())

    groups = _group_articles(all_articles, args.split_by)
    os.makedirs(args.out, exist_ok=True)
    for label, subset in groups:
        if not subset:
            continue
        dates = [a.published.date() for a in subset if a.published]
        chunk_start = min(dates) if dates else start_d
        chunk_end = max(dates) if dates else end_d
        # none のときの md の time_range は、scraper.py・アプリと同じく指定期間にする
        cfg_chunk = cfg_base if args.split_by == "none" else replace(cfg_base, start_date=chunk_start, end_date=chunk_end)
        if args.split_by == "none":
            # ファイル名は指定期間から決める。取得できた記事の min/max 日付を使うと
            # 再実行のたびに別名ファイルが増え、同じ記事が重複して残る。
            basename = f"{PREFIX}_{start_d.isoformat()}_{end_d.isoformat()}"
        else:
            safe_label = label.replace("/", "-")
            basename = f"{PREFIX}_{safe_label}"
        paths = export_all(subset, cfg_chunk, args.out, basename=basename)
        for kind, path in paths.items():
            if args.split_by == "none":
                print(f"[DONE] {kind.upper()}: {path}")
            else:
                print(f"[DONE] {label} {kind.upper()}: {path}")

    if overall_failures or collect_errors:
        written = "取得できた分だけ書き出しました。" if all_articles else "本文を 1 本も取得できなかったため、ファイルは書き出していません。"
        print(
            f"[ERROR] 失敗あり (本文 {len(overall_failures)} 件 / 一覧ページ {len(collect_errors)} 件)。{written}",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
