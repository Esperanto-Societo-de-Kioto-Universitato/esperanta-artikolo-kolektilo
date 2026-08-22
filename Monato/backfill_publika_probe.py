# -*- coding: utf-8 -*-
"""
backfill_publika_probe.py

MONATO の年別インデックス (/<year>/index.php?p) は購読者専用 (HTTP 401) のため、
collect_urls は実質「Nova!」ページのフォールバックだけで動いており、
長い期間を指定しても直近 2 か月程度の publika 記事しか集められない。

このスクリプトは publika 記事の URL が連番 (/publika/NNNNNNp.php) であることを
利用し、指定した ID 帯を直接プローブして取り漏らした記事を回収する。
既存の monato_*.jsonl (--existing) を読み込んで合流し、月別ファイルを
parallel_scraper.py と同一の形式 (export_all) で書き出す。

備考: 通常の期間指定収集は parallel_scraper.py --method both (既定値) が
同等のプローブを自動で行うため、本スクリプトは「ID 帯を明示して回収したい」
場合 (例: 過去年の穴埋め、検証) にのみ使えばよい。
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from datetime import date, datetime
from glob import glob
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json  # noqa: E402

import requests  # noqa: E402

from retradio_lib import Article, ScrapeConfig, export_all, _get as retry_get  # noqa: E402
from Monato.monato_lib import USER_AGENT, fetch_article  # noqa: E402

DEFAULT_BASE_URL = "https://www.monato.be"
SOURCE_LABEL = "MONATO (monato.be)"
PREFIX = "monato"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="MONATO publika 連番プローブによる穴埋め取得")
    p.add_argument("--id-start", type=int, required=True, help="プローブする publika ID の下限")
    p.add_argument("--id-end", type=int, required=True, help="プローブする publika ID の上限")
    p.add_argument("--start", required=True, help="採用する記事の開始日 YYYY-MM-DD")
    p.add_argument("--end", required=True, help="採用する記事の終了日 YYYY-MM-DD")
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--throttle", type=float, default=1.0)
    p.add_argument("--existing", default=None,
                   help="既存 monato_*.jsonl のあるディレクトリ（合流とスキップに使用）")
    p.add_argument("--include-undated", action="store_true",
                   help="新規プローブで日付を判定できなかった記事も採用する "
                        "(既定では一覧表示のみで除外。期間外の可能性があるため)")
    p.add_argument("--out", required=True, help="書き出し先ディレクトリ")
    p.add_argument("--base-url", default=DEFAULT_BASE_URL)
    return p.parse_args()


def load_existing(existing_dir: Optional[str]) -> Tuple[List[Article], set, Dict[str, str]]:
    """既存記事・既知IDに加えて、URL→出所ファイルの月ラベルの対応を返す。
    日付不明記事は手動で適切な月ファイルに配置してあることがあるため、
    マージ時に published だけで再グループ化するとその配置が巻き戻ってしまう。"""
    articles: List[Article] = []
    ids: set = set()
    origin_labels: Dict[str, str] = {}
    if not existing_dir:
        return articles, ids, origin_labels
    for path in sorted(glob(os.path.join(existing_dir, f"{PREFIX}_*.jsonl"))):
        label = os.path.basename(path)[len(PREFIX) + 1:-len(".jsonl")]
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                published = None
                if r.get("published"):
                    published = datetime.fromisoformat(r["published"])
                articles.append(
                    Article(
                        url=r["url"],
                        title=r["title"],
                        published=published,
                        content_text=r["content_text"],
                        author=r.get("author"),
                        categories=r.get("categories"),
                        audio_links=r.get("audio_links"),
                    )
                )
                m = re.search(r"/publika/(\d+)p\.php", r["url"])
                if m:
                    ids.add(int(m.group(1)))
                # 同一URLが複数ファイルにある場合は最初のファイルを優先する
                # (マージ側の seen.setdefault と同じ規則。月ファイルは unknown より
                # 先にソートされるため、手動配置済みの月ラベルが必ず勝つ)
                origin_labels.setdefault(r["url"], label)
    return articles, ids, origin_labels


def probe_one(article_id: int, cfg: ScrapeConfig) -> Tuple[int, str, Optional[Article], str]:
    """戻り値: (id, status, article, note)  status: hit / miss / error"""
    url = f"{cfg.base_url.rstrip('/')}/publika/{article_id:06d}p.php"
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    try:
        # retry_get は 5xx・例外を cfg.max_retries 回まで再試行する。
        # 一時的なサーバーエラーを「非公開・不存在 (miss)」と誤分類すると
        # 実在記事が黙って欠落するため、429・5xx は error として報告する。
        resp = retry_get(session, url, cfg)
        time.sleep(cfg.throttle_sec)
        if resp.status_code == 429 or resp.status_code >= 500:
            return article_id, "error", None, f"HTTP {resp.status_code}"
        if resp.status_code != 200:
            return article_id, "miss", None, f"HTTP {resp.status_code}"
        text = resp.text
        if "Erarpaĝo" in text or "<h1" not in text:
            return article_id, "miss", None, "ne-artikola paĝo"
        article = fetch_article(url, cfg, session)
        time.sleep(cfg.throttle_sec)
        if not article.content_text.strip():
            return article_id, "miss", None, "malplena enhavo"
        return article_id, "hit", article, ""
    except Exception as exc:  # noqa: BLE001
        return article_id, "error", None, str(exc)


def main() -> None:
    args = parse_args()
    start_d = datetime.fromisoformat(args.start).date()
    end_d = datetime.fromisoformat(args.end).date()

    cfg = ScrapeConfig(
        base_url=args.base_url,
        start_date=start_d,
        end_date=end_d,
        throttle_sec=args.throttle,
        method="feed",
        use_cache=False,
        source_label=SOURCE_LABEL,
    )
    cfg.normalize()

    existing_articles, existing_ids, origin_labels = load_existing(args.existing)
    print(f"[INFO] 既存記事: {len(existing_articles)} 本 (ID {len(existing_ids)} 個をスキップ)")

    candidates = [i for i in range(args.id_start, args.id_end + 1) if i not in existing_ids]
    print(f"[INFO] プローブ対象: ID {args.id_start}–{args.id_end} のうち {len(candidates)} 件 "
          f"(workers={args.workers}, throttle={args.throttle}s)")

    kept: List[Article] = []
    undated_hits: List[Tuple[int, Article]] = []
    out_of_range: List[Tuple[int, str, str]] = []
    misses = 0
    errors: List[Tuple[int, str]] = []

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(probe_one, i, cfg): i for i in candidates}
        for fut in as_completed(futures):
            article_id, status, article, note = fut.result()
            if status == "hit" and article is not None:
                if article.published is None:
                    # 日付不明の新規記事は期間判定ができないため無条件採用しない
                    undated_hits.append((article_id, article))
                    print(f"[HIT?] {article_id:06d} 日付不明 {article.title}")
                elif not (start_d <= article.published.date() <= end_d):
                    out_of_range.append(
                        (article_id, article.published.date().isoformat(), article.title)
                    )
                else:
                    kept.append(article)
                    print(f"[HIT ] {article_id:06d} {article.published.date().isoformat()} {article.title}")
            elif status == "miss":
                misses += 1
            else:
                errors.append((article_id, note))
                print(f"[ERR ] {article_id:06d} {note}")

    print(f"[INFO] プローブ結果: 採用 {len(kept)} / 日付不明 {len(undated_hits)} / "
          f"期間外 {len(out_of_range)} / 非公開・不存在 {misses} / エラー {len(errors)}")
    for article_id, pub, title in sorted(out_of_range):
        print(f"[SKIP] 期間外: {article_id:06d} {pub} {title}")
    if undated_hits:
        if args.include_undated:
            print(f"[INFO] --include-undated 指定のため日付不明 {len(undated_hits)} 本を採用します")
            kept.extend(article for _, article in sorted(undated_hits, key=lambda t: t[0]))
        else:
            print("[INFO] 日付不明の新規記事は採用しませんでした。前後IDの日付を確認のうえ、"
                  "採用するなら --include-undated を付けて再実行してください:")
            for article_id, article in sorted(undated_hits, key=lambda t: t[0]):
                print(f"  - {article_id:06d} {article.url} {article.title}")
    if errors:
        print("[WARN] エラーが発生した ID は取得漏れの可能性があります。同じ ID 帯で再実行してください。")

    merged = existing_articles + kept
    seen: Dict[str, Article] = {}
    for art in merged:
        seen.setdefault(art.url, art)

    def sort_key(article: Article):
        if article.published:
            pub = article.published.replace(tzinfo=None) if article.published.tzinfo else article.published
            return (pub, article.url)
        return (datetime.max, article.url)

    all_articles = sorted(seen.values(), key=sort_key)
    print(f"[INFO] 合流後合計: {len(all_articles)} 本")

    # 月別グループ化。日付不明の記事は published からラベルを決められないため、
    # 既存ファイル由来のもの (前後IDから月を判定して手動配置済み) は
    # 元ファイルの月ラベルを維持する。
    groups_map: Dict[str, List[Article]] = {}
    for art in all_articles:
        if art.published:
            d = art.published.date()
            label = f"{d.year}-{d.month:02d}"
        else:
            label = origin_labels.get(art.url, "unknown")
        groups_map.setdefault(label, []).append(art)
    groups = sorted(groups_map.items())
    os.makedirs(args.out, exist_ok=True)
    for label, subset in groups:
        if not subset:
            continue
        dates = [a.published.date() for a in subset if a.published]
        chunk_start = min(dates) if dates else start_d
        chunk_end = max(dates) if dates else end_d
        cfg_chunk = replace(cfg, start_date=chunk_start, end_date=chunk_end)
        safe_label = label.replace("/", "-")
        paths = export_all(subset, cfg_chunk, args.out, basename=f"{PREFIX}_{safe_label}")
        for kind, path in paths.items():
            print(f"[DONE] {label} {kind.upper()}: {path}")


if __name__ == "__main__":
    main()
