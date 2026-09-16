#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Libera Folio（https://www.liberafolio.org）の記事収集を複数プロセスで分割実行し、最後に結合して書き出す CLI。
WordPress REST API / RSS / アーカイブを retradio_lib の汎用実装で利用します。
"""

import argparse
import os
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from typing import Iterable, List, Tuple

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from retradio_lib import (  # noqa: E402
    ScrapeConfig,
    URLCollectionResult,
    Article,
    collect_urls,
    export_all,
    fetch_article,
    set_progress_callback,
    _session,
)


def _group_articles(articles, mode: str):
    from collections import OrderedDict
    if mode == "none":
        return [("all", articles)]
    groups = OrderedDict()
    for art in articles:
        if art.published:
            d = art.published.date()
            key = f"{d.year}" if mode == "year" else f"{d.year}-{d.month:02d}"
        else:
            key = "unknown"
        groups.setdefault(key, []).append(art)
    return list(groups.items())


DEFAULT_BASE_URL = "https://www.liberafolio.org"
SOURCE_LABEL = "Libera Folio (liberafolio.org)"
PREFIX = "libera_folio"


@dataclass
class WorkerArgs:
    index: int
    cfg: ScrapeConfig


@dataclass
class WorkerResult:
    index: int
    start_date: date
    end_date: date
    urls: URLCollectionResult
    articles: List[Article]
    failures: List[str]
    timer_collect: float
    timer_fetch: float


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Libera Folio 期間指定スクレイパー (並列版)")
    p.add_argument("--start", help="開始日 YYYY-MM-DD")
    p.add_argument("--end", help="終了日 YYYY-MM-DD")
    p.add_argument("--days", type=int, help="終了日から遡った直近N日間を収集（--end 未指定時は今日を終了日にします）")
    p.add_argument("--workers", type=int, default=4, help="並列実行ワーカー数（1以上）")
    p.add_argument("--out", default="output", help="書き出し先ディレクトリ")
    p.add_argument("--base-url", default=DEFAULT_BASE_URL, help="対象サイトのベース URL")
    p.add_argument(
        "--method",
        default="rest",
        choices=["auto", "rest", "both", "feed", "archive"],
        help="URL収集方法（WordPress REST 推奨）",
    )
    p.add_argument("--throttle", type=float, default=0.5, help="1リクエスト毎の遅延秒数")
    p.add_argument("--max-pages", type=int, default=None, help="フィード/月別アーカイブのページ送り上限（省略時: フィード 200、アーカイブ無制限。REST では無効）")
    p.add_argument("--no-cache", action="store_true", help="requests-cache を使わない")
    p.add_argument("--feed-url", help="RSS/Atom フィード URL を直接指定（必要時）")
    p.add_argument("--split-by", choices=["none", "year", "month"], default="none", help="出力を年/月で分割")
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


def split_date_range(start: date, end: date, segments: int) -> List[Tuple[date, date]]:
    total_days = (end - start).days + 1
    segments = max(1, min(segments, total_days))
    base_span = total_days // segments
    remainder = total_days % segments
    result: List[Tuple[date, date]] = []
    current = start
    for idx in range(segments):
        span_days = base_span + (1 if idx < remainder else 0)
        if span_days <= 0:
            continue
        chunk_end = current + timedelta(days=span_days - 1)
        result.append((current, min(chunk_end, end)))
        current = chunk_end + timedelta(days=1)
        if current > end:
            break
    return result


@dataclass
class WorkerArgs:
    index: int
    cfg: ScrapeConfig


def worker_task(args: WorkerArgs):
    cfg = args.cfg
    cfg.normalize()
    timer_start = time.perf_counter()
    urls = collect_urls(cfg)
    timer_after_collect = time.perf_counter()

    session = _session(cfg)
    articles: List[Article] = []
    failures: List[str] = []
    skipped_out_of_range: List[str] = []
    for url in urls.urls:
        try:
            article = fetch_article(url, cfg, session)
            if article.published:
                d = article.published.date()
                if d < cfg.start_date or d > cfg.end_date:
                    skipped_out_of_range.append(f"{url} ({d})")
                    continue
            articles.append(article)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{url} ({exc})")
        finally:
            if cfg.throttle_sec > 0:
                time.sleep(cfg.throttle_sec)

    timer_after_fetch = time.perf_counter()
    return dict(
        index=args.index,
        start_date=cfg.start_date,
        end_date=cfg.end_date,
        urls=urls,
        articles=articles,
        failures=failures,
        timer_collect=timer_after_collect - timer_start,
        timer_fetch=timer_after_fetch - timer_after_collect,
        skipped_out_of_range=skipped_out_of_range,
    )


def _sort_articles(articles: Iterable[Article]) -> List[Article]:
    def sort_key(article: Article):
        if article.published:
            pub_naive = article.published.replace(tzinfo=None) if article.published.tzinfo else article.published
            return (pub_naive, article.url)
        return (datetime.max, article.url)
    return sorted(articles, key=sort_key)


def _report_worker_failure(w: WorkerArgs, exc: Exception) -> None:
    print(f"[ERROR] ワーカー #{w.index} ({w.cfg.start_date}～{w.cfg.end_date}) が失敗: {exc}", file=sys.stderr)
    traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)


def _report_failures(failed_chunks: List[Tuple[WorkerArgs, Exception]], article_failures: List[str]) -> None:
    if not failed_chunks and not article_failures:
        return
    print(f"[WARN] 失敗: 期間 {len(failed_chunks)} 件 / 記事 {len(article_failures)} 件（詳細は標準エラー出力）")
    if failed_chunks:
        print(
            "[ERROR] 次の期間は取得できませんでした（出力にこの期間の記事は入っていません）。"
            "この期間だけを別の --out に再実行して結合してください（同じ --out だと同じ月のファイルを上書きします）:",
            file=sys.stderr,
        )
        for w, exc in sorted(failed_chunks, key=lambda item: item[0].index):
            print(f"  - --start {w.cfg.start_date} --end {w.cfg.end_date}  ({type(exc).__name__}: {exc})", file=sys.stderr)
    if article_failures:
        print("[ERROR] 本文の取得に失敗した記事:", file=sys.stderr)
        for fail in article_failures:
            print(f"  - {fail}", file=sys.stderr)


def main() -> None:
    args = parse_args()
    start_d, end_d = resolve_date_range(args)
    if args.workers <= 0:
        raise SystemExit("--workers には 1 以上の整数を指定してください。")

    chunks = split_date_range(start_d, end_d, args.workers)
    actual_workers = len(chunks)
    if actual_workers < args.workers:
        print(f"[INFO] 期間が短いためワーカー数を {actual_workers} に調整しました。")

    cfg_base = ScrapeConfig(
        base_url=args.base_url,
        start_date=start_d,
        end_date=end_d,
        throttle_sec=args.throttle,
        max_pages=args.max_pages,
        method=args.method,
        include_audio_links=False,
        use_cache=not args.no_cache,
        source_label=SOURCE_LABEL,
        feed_url_override=args.feed_url,
    )
    if actual_workers > 1 and cfg_base.use_cache:
        cfg_base.use_cache = False
        print("[INFO] 並列実行では requests-cache を無効化しました（SQLite のロック競合回避）。")

    set_progress_callback(None)

    print(
        f"[INFO] 並列スクレイプ開始: {start_d} ～ {end_d} "
        f"(workers={actual_workers}, method={cfg_base.method})"
    )

    workers: List[WorkerArgs] = [
        WorkerArgs(index=i, cfg=replace(cfg_base, start_date=cs, end_date=ce))
        for i, (cs, ce) in enumerate(chunks, start=1)
    ]

    results: List[dict] = []
    total_collect = 0.0
    total_fetch = 0.0
    overall_failures: List[str] = []
    combined_stats = dict(
        feed_initial=0,
        archive_initial=0,
        rest_initial=0,
        feed_used=0,
        archive_used=0,
        rest_used=0,
        duplicates_removed=0,
        out_of_range_skipped=0,
    )
    skipped_out_of_range: List[str] = []
    earliest_dates: List[date] = []
    latest_dates: List[date] = []

    failed_chunks: List[Tuple[WorkerArgs, Exception]] = []
    if actual_workers == 1:
        try:
            results.append(worker_task(workers[0]))
        except Exception as exc:  # noqa: BLE001
            _report_worker_failure(workers[0], exc)
            failed_chunks.append((workers[0], exc))
    else:
        with ProcessPoolExecutor(max_workers=actual_workers) as executor:
            future_map = {executor.submit(worker_task, w): w for w in workers}
            for fut in as_completed(future_map):
                w = future_map[fut]
                try:
                    result = fut.result()
                    results.append(result)
                except Exception as exc:  # noqa: BLE001
                    # 1 区間の失敗で、ほかの区間で取れた記事まで捨てない。失敗した区間は最後に報告して非 0 で終える
                    _report_worker_failure(w, exc)
                    failed_chunks.append((w, exc))

    results.sort(key=lambda r: r["index"]) 

    all_articles: List[Article] = []
    for r in results:
        total_collect += r["timer_collect"]
        total_fetch += r["timer_fetch"]
        overall_failures.extend(r["failures"])
        urls = r["urls"]
        combined_stats["feed_initial"] += urls.feed_initial
        combined_stats["archive_initial"] += urls.archive_initial
        combined_stats["rest_initial"] += urls.rest_initial
        combined_stats["feed_used"] += urls.feed_used
        combined_stats["archive_used"] += urls.archive_used
        combined_stats["rest_used"] += urls.rest_used
        combined_stats["duplicates_removed"] += urls.duplicates_removed
        combined_stats["out_of_range_skipped"] += urls.out_of_range_skipped
        if urls.earliest_date:
            earliest_dates.append(urls.earliest_date)
        if urls.latest_date:
            latest_dates.append(urls.latest_date)
        all_articles.extend(r["articles"])
        skipped_out_of_range.extend(r["skipped_out_of_range"])
        print(
            f"[INFO] ワーカー #{r['index']}: {r['start_date']} ～ {r['end_date']} | "
            f"URL {len(r['urls'].urls)} 件 | 本文 {len(r['articles'])} 本 | 期間外 {len(r['skipped_out_of_range'])} 本 | "
            f"URL収集 {r['timer_collect']:.1f}s / 本文取得 {r['timer_fetch']:.1f}s"
        )

    all_articles = _sort_articles(all_articles)
    print(f"[INFO] 抽出完了: {len(all_articles)} 本")
    if earliest_dates and latest_dates:
        print(f"[INFO] URL 範囲（推定公開日）: {min(earliest_dates)} ～ {max(latest_dates)}")
    print(
        "[INFO] 集計: "
        f"feed {combined_stats['feed_used']}/{combined_stats['feed_initial']} | "
        f"archive {combined_stats['archive_used']}/{combined_stats['archive_initial']} | "
        f"rest {combined_stats['rest_used']}/{combined_stats['rest_initial']} | "
        f"duplicates removed {combined_stats['duplicates_removed']} | "
        f"out-of-range skipped {combined_stats['out_of_range_skipped']}"
    )
    print(f"[INFO] 累計時間: URL収集 {total_collect:.1f}s / 本文取得 {total_fetch:.1f}s")
    print(f"[INFO] 本文取得後に期間外で除外: 合計 {len(skipped_out_of_range)} 本")
    for item in skipped_out_of_range:
        print(f"  - {item}")

    _report_failures(failed_chunks, overall_failures)
    if not results:
        print("[ERROR] 成功したワーカーが無いため、ファイルを書き出さずに終了します。", file=sys.stderr)
        sys.exit(1)

    groups = _group_articles(all_articles, args.split_by)
    os.makedirs(args.out, exist_ok=True)
    for label, subset in groups:
        if not subset:
            continue
        dates = [a.published.date() for a in subset if a.published]
        chunk_start = min(dates) if dates else start_d
        chunk_end = max(dates) if dates else end_d
        # none のときの md の time_range は、アプリと同じく指定期間にする
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

    if failed_chunks or overall_failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
