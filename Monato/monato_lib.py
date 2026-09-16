# -*- coding: utf-8 -*-
"""
monato_lib.py

Utility helpers tailored to the MONATO website. The site predates WordPress, so
we cannot reuse the generic REST/feed/archive collectors. Instead we gather
article URLs from the public "Nova!" page plus historic yearly indexes, and
normalize the result into retradio_lib's data structures so that the existing
CLI flow keeps working.
"""
from __future__ import annotations

import copy
import re
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

from retradio_lib import (  # type: ignore
    Article,
    ScrapeConfig,
    URLCollectionResult,
    _INLINE_BLOCKS,
    _clean_text as base_clean_text,
    _get as retry_get,
    _has_emitted_ancestor,
    _inline_text,
    _session as shared_session,
    set_progress_callback,
)

USER_AGENT = "Mozilla/5.0 (compatible; MonatoScraper/1.0; +https://www.monato.be)"
WAYBACK_CDX_ENDPOINT = "https://web.archive.org/cdx/search/cdx"
WAYBACK_SNAPSHOT_URL = "https://web.archive.org/web/{timestamp}/{original}"

# publika 記事は /publika/NNNNNNp.php の連番。年別インデックス (/<year>/index.php?p) は
# 2024 年以前は公開だが直近約 2 年分は購読者専用 (HTTP 401) のため、その期間は
# Nova! ページ (直近掲載分のみ) + ID 連番プローブ (--method archive / both) で補完する。
PROBE_STOP_OLDER = 15    # 実効下限(-余裕)より古い日付付きページがこの数連続したら走査終了
PROBE_MARGIN_DAYS = 30   # 「Lasta adapto」日付が号内で前後する非単調性への余裕
# ID は投稿時に振られ、ページの日付はそれより数か月遅れることがある (帯域下端から
# 200 ID 以上下で期間内の日付を持つ記事が実在した)。この幅は打ち切りの数を数えずに走査する
PROBE_MIN_SPAN = 300
PROBE_MAX_PAGES = 500    # 走査ページ数の安全上限
PROBE_MAX_ERRORS = 5     # ネットワークエラーがこの数連続したら走査中断

_PUBLIKA_ID_RE = re.compile(r"/publika/(\d+)p\.php$")

MONATO_META: Dict[str, Dict[str, Optional[datetime]]] = {}


@dataclass
class _CollectedEntry:
    url: str
    title: str
    published: Optional[datetime]
    category: Optional[str]
    section: Optional[str]
    author_hint: Optional[str]
    source: str = "feed"  # "feed"=年別インデックス・Nova! / "archive"=IDプローブ


@dataclass
class MonatoCollectionResult(URLCollectionResult):
    # 取りこぼしにつながる収集の失敗。0 件は正常なこともあるため、失敗はここで区別する
    # (CLI はこれが空でなければ終了コードを非 0 にする)
    errors: List[str] = field(default_factory=list)


def _clean_space(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\b([A-Z])\s+([A-Z]{2,})\b", r"\1\2", text)
    return text.strip()


def _parse_issue_date(raw: str) -> Optional[datetime]:
    if not raw:
        return None
    m = re.search(r"(\d{4})/(\d{2})(?:-(\d{2}))?", raw)
    if not m:
        return None
    year = int(m.group(1))
    month = int(m.group(2))
    try:
        return datetime(year, month, 1)
    except ValueError:
        return None


def _parse_issue_hint_from_text(node: Tag) -> Optional[datetime]:
    text = _clean_space(node.get_text(" ", strip=True))
    m = re.search(r"(20\d{2})/(0[1-9]|1[0-2])", text)
    if not m:
        return None
    year = int(m.group(1))
    month = int(m.group(2))
    try:
        return datetime(year, month, 1)
    except ValueError:
        return None


def _iter_prefix_text(li: Tag) -> str:
    pieces: List[str] = []
    for child in li.children:
        if isinstance(child, Tag) and child.name == "a":
            break
        if isinstance(child, Tag):
            pieces.append(child.get_text(" ", strip=True))
        else:
            pieces.append(str(child))
    return _clean_space("".join(pieces))


def _collect_from_year(
    year: int, cfg: ScrapeConfig, session: requests.Session
) -> Tuple[List[_CollectedEntry], int, str]:
    """
    年別インデックスから収集する。
    戻り値: (エントリ, 期間外スキップ数, 状態 "ok" | "unauthorized" | "unavailable")
    """
    base = cfg.base_url.rstrip("/")
    url = f"{base}/{year}/index.php?p"
    try:
        resp = retry_get(session, url, cfg)
    except Exception as exc:  # noqa: BLE001
        logging.warning("MONATO: la jarindekso %s ne atingebla: %s", url, exc)
        return [], 0, "unavailable"
    finally:
        if cfg.throttle_sec > 0:
            time.sleep(cfg.throttle_sec)
    if resp.status_code == 401:
        logging.warning(
            "MONATO: la jarindekso %s postulas abonon (HTTP 401). "
            "La indeksoj de la lastaj ĉ. 2 jaroj ne estas publikaj.",
            url,
        )
        return [], 0, "unauthorized"
    if resp.status_code != 200 or "Erarpaĝo" in resp.text:
        logging.warning(
            "MONATO: la jarindekso %s nedisponebla (HTTP %s); la jaro povas manki.",
            url,
            resp.status_code,
        )
        return [], 0, "unavailable"

    soup = BeautifulSoup(resp.content, "lxml")
    entries: List[_CollectedEntry] = []
    out_of_range = 0
    # 号日付は YYYY/MM を月初に正規化した月粒度なので、開始側も月初で比較する
    # (日粒度で比較すると開始日が月の2日以降のとき開始月が丸ごと落ちる)。
    start_floor = cfg.start_date.replace(day=1)

    for header in soup.find_all("h3"):
        section = _clean_space(header.get_text(" ", strip=True))
        ul = _following_section_ul(header)
        while ul and ul.name == "ul":
            for li in ul.find_all("li", recursive=False):
                anchors = li.find_all("a", href=True)
                if not anchors:
                    continue
                link = anchors[0]
                href = urljoin(f"{base}/{year}/", link["href"])
                title = _clean_space(link.get_text(" ", strip=True))
                prefix = _iter_prefix_text(li)
                author_hint = None
                category = None
                parts = [seg.strip() for seg in prefix.split(":") if seg.strip()]
                if parts:
                    author_hint = parts[0]
                if len(parts) > 1:
                    category = parts[1]
                issue_text = ""
                if len(anchors) > 1:
                    issue_text = anchors[-1].get_text(" ", strip=True)
                else:
                    tail = li.get_text(" ", strip=True)
                    match = re.search(r"\(\s*([^)]+)\)", tail)
                    if match:
                        issue_text = match.group(1)
                published = _parse_issue_date(issue_text)
                if published and (published.date() < start_floor or published.date() > cfg.end_date):
                    out_of_range += 1
                    continue
                entries.append(
                    _CollectedEntry(
                        url=href,
                        title=title,
                        published=published,
                        category=_clean_space(category) if category else None,
                        section=section or None,
                        author_hint=_clean_space(author_hint) if author_hint else None,
                    )
                )
            ul = _following_section_ul(ul)
    return entries, out_of_range, "ok"


def _following_section_ul(node: Tag) -> Optional[Tag]:
    # 見出し (h3) または ul の次の兄弟から、次の h3 (次セクション) を越えない
    # 範囲で ul を返す。find_next_sibling("ul") は h3 を飛び越えてしまうため、
    # 空見出しの直後に次セクションの ul を誤って拾う・全セクション×全 ul の
    # 重複収集になる、という2つの問題をこのガードで防ぐ。
    nxt = node.find_next_sibling(["ul", "h3"])
    if nxt is not None and nxt.name == "ul":
        return nxt
    return None


def _collect_from_current(cfg: ScrapeConfig, session: requests.Session) -> List[_CollectedEntry]:
    base = cfg.base_url.rstrip("/")
    url = f"{base}/index.php"
    try:
        # Nova! ページはプローブのアンカー ID 供給源でもあるため、リトライ後も
        # 失敗する場合は例外を伝播させ、無音で2年分欠落するのを避ける。
        resp = retry_get(session, url, cfg)
    finally:
        if cfg.throttle_sec > 0:
            time.sleep(cfg.throttle_sec)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, "lxml")
    entries: List[_CollectedEntry] = []

    for header in soup.find_all("h3"):
        section = _clean_space(header.get_text(" ", strip=True))
        ul = _following_section_ul(header)
        while ul and ul.name == "ul":
            for li in ul.find_all("li", recursive=False):
                anchor = li.find("a", href=True)
                if not anchor:
                    continue
                href = urljoin(base + "/", anchor["href"])
                if "/publika/" not in href:
                    continue
                title = _clean_space(anchor.get_text(" ", strip=True))
                prefix = _iter_prefix_text(li)
                author_hint = None
                category = None
                parts = [seg.strip() for seg in prefix.split(":") if seg.strip()]
                if parts:
                    author_hint = parts[0]
                if len(parts) > 1:
                    category = parts[1]
                published = _parse_issue_hint_from_text(li)
                entries.append(
                    _CollectedEntry(
                        url=href,
                        title=title,
                        published=published,
                        category=_clean_space(category) if category else None,
                        section=section or None,
                        author_hint=_clean_space(author_hint) if author_hint else None,
                    )
                )
            ul = _following_section_ul(ul)
    return entries


def _publika_ids(urls: Iterable[str]) -> List[int]:
    ids: List[int] = []
    for url in urls:
        m = _PUBLIKA_ID_RE.search(url)
        if m:
            ids.append(int(m.group(1)))
    return ids


def _probe_article(
    article_id: int, cfg: ScrapeConfig, session: requests.Session
) -> Tuple[str, Optional[_CollectedEntry]]:
    """
    1 つの publika ID を取得し ("hit"|"miss"|"error", entry) を返す。
    retry_get が 5xx・例外を cfg.max_retries 回まで再試行するため、
    "error" はリトライ枯渇後のネットワーク障害を意味する ("miss" と区別)。
    """
    url = f"{cfg.base_url.rstrip('/')}/publika/{article_id:06d}p.php"
    try:
        resp = retry_get(session, url, cfg)
    except Exception as exc:  # noqa: BLE001
        logging.warning("MONATO probo %s: %s", url, exc)
        return "error", None
    if resp.status_code != 200:
        return "miss", None
    if "Erarpaĝo" in resp.text or "<h1" not in resp.text:
        return "miss", None
    soup = BeautifulSoup(resp.content, "lxml")
    h1 = soup.find("h1")
    title = _inline_text(h1) if h1 else url
    published = _extract_last_adapto(soup)
    return "hit", _CollectedEntry(
        url=url,
        title=title,
        published=published,
        category=None,
        section=None,
        author_hint=None,
        source="archive",
    )


def _collect_from_probe(
    cfg: ScrapeConfig,
    session: requests.Session,
    anchor_ids: List[int],
    probe_floor: Optional[date] = None,
) -> Tuple[List[_CollectedEntry], int, int, Optional[str]]:
    """
    Nova! ページ最大 ID から連番を降順に走査し、期間内の publika 記事を集める。
    直近約 2 年の年別インデックスが HTTP 401 (購読者専用) のときの補完経路。

    - anchor_ids (Nova! で取得済みの ID) はスキップしつつ帯域内の非掲載ページ
      (Nova! に一度も載らない書評等が実在する) も拾う。
    - 打ち切り: 実効下限 (開始日と probe_floor = 公開年別インデックスで取得済みの
      翌年初、の大きい方) より PROBE_MARGIN_DAYS 以上古い日付付きページが
      PROBE_STOP_OLDER 回連続したら終了。ID より日付が数か月遅れるページがあるため、
      カウントは走査位置が Nova! 帯域下端 (min(anchor_ids)) から PROBE_MIN_SPAN を
      下回ってから行う。これより古い ID で日付の遅い記事は取れない
      (backfill_publika_probe.py で ID 帯を走査して補う)。
    - 日付なしページ: 直近に見た日付付きページが期間±余裕内にある場合のみ収集
      (published は空のまま出力の unknown グループに現れるので人手で確認する)。
    - ネットワーク障害: PROBE_MAX_ERRORS 回連続で走査中断 (収集は不完全になる)。
      連続に届かない散発的な失敗も、その ID が期間内の記事だった可能性があるので
      不完全として報告する。
    - PROBE_MAX_PAGES に達して実効下限まで届かなかったときも収集は不完全。

    戻り値: (収集エントリ, 期間外スキップ数, 日付なしスキップ数, 走査が不完全に終わったときのエラー文)
    """
    if not anchor_ids:
        logging.warning(
            "MONATO probo: ne estas ankra ID (ĉu la Nova!-paĝo malplenas?); probado ne eblas."
        )
        return [], 0, 0, None
    anchor_set = set(anchor_ids)
    min_anchor = min(anchor_set)
    floor_date = max(cfg.start_date, probe_floor) if probe_floor else cfg.start_date
    stop_threshold = floor_date - timedelta(days=PROBE_MARGIN_DAYS)
    margin = timedelta(days=PROBE_MARGIN_DAYS)
    entries: List[_CollectedEntry] = []
    consecutive_older = 0
    consecutive_errors = 0
    failed_ids: List[int] = []
    out_of_range = 0
    skipped_undated = 0
    probed = 0
    last_dated: Optional[date] = None
    article_id = max(anchor_set) - 1
    while (
        article_id >= 1
        and probed < PROBE_MAX_PAGES
        and consecutive_older < PROBE_STOP_OLDER
        and consecutive_errors < PROBE_MAX_ERRORS
    ):
        if article_id in anchor_set:
            article_id -= 1
            continue
        status, entry = _probe_article(article_id, cfg, session)
        probed += 1
        if cfg.throttle_sec > 0:
            time.sleep(cfg.throttle_sec)
        consecutive_errors = consecutive_errors + 1 if status == "error" else 0
        if status == "error":
            failed_ids.append(article_id)
        if status == "hit" and entry is not None:
            if entry.published:
                pub = entry.published.date()
                last_dated = pub
                if article_id < min_anchor - PROBE_MIN_SPAN:
                    consecutive_older = consecutive_older + 1 if pub < stop_threshold else 0
                if cfg.start_date <= pub <= cfg.end_date:
                    entries.append(entry)
                else:
                    out_of_range += 1
            else:
                near_period = (
                    last_dated is not None
                    and cfg.start_date - margin <= last_dated <= cfg.end_date + margin
                ) or (
                    last_dated is None
                    and cfg.end_date >= date.today() - margin
                )
                if near_period:
                    logging.warning(
                        "MONATO probo: paĝo sen dato inkluzivita (kontrolu la daton permane): %s",
                        entry.url,
                    )
                    entries.append(entry)
                else:
                    skipped_undated += 1
                    logging.info(
                        "MONATO probo: paĝo sen dato ekster la periodo-ĉirkaŭaĵo: %s",
                        entry.url,
                    )
        article_id -= 1
    error: Optional[str] = None
    if consecutive_errors >= PROBE_MAX_ERRORS:
        # 中断直前の連続失敗は中断のエラー文で報告される
        failed_ids = failed_ids[:-consecutive_errors]
        error = (
            f"MONATO probo ĉesigita ĉe ID {article_id + 1:06d} post {PROBE_MAX_ERRORS} sinsekvaj "
            "retaj eraroj; la kolektado estas nekompleta."
        )
        logging.warning(error)
    elif probed >= PROBE_MAX_PAGES and consecutive_older < PROBE_STOP_OLDER:
        if last_dated is None or last_dated >= stop_threshold:
            # 実効下限 - 余裕まで届いていない (期間の始まり側が丸ごと欠け得る)
            error = (
                f"MONATO probo: atingis PROBE_MAX_PAGES={PROBE_MAX_PAGES} ĉe ID {article_id + 1:06d}, "
                f"sed la plej frua probita dato estas {last_dated or 'nekonata'} (bezonata: antaŭ "
                f"{stop_threshold}); artikoloj de {floor_date} ĝis tiam povas manki; "
                "la kolektado estas nekompleta."
            )
            logging.warning(error)
        else:
            logging.warning(
                "MONATO probo: atingis PROBE_MAX_PAGES=%s post %s; la komenco de la periodo "
                "verŝajne estas kovrita, sed ne konfirmita.",
                PROBE_MAX_PAGES,
                last_dated,
            )
    if failed_ids:
        examples = ", ".join(f"{i:06d}" for i in failed_ids[:10])
        if len(failed_ids) > 10:
            examples += " …"
        scattered = (
            f"MONATO probo: {len(failed_ids)} {'ID-o' if len(failed_ids) == 1 else 'ID-oj'} "
            "ne atingeblis pro retaj eraroj "
            f"(ekz. {examples}); la kolektado eble estas nekompleta."
        )
        logging.warning(scattered)
        error = f"{error} {scattered}" if error else scattered
    logging.info(
        "MONATO probo: %s paĝoj probitaj, %s artikoloj en la periodo, "
        "%s ekster ĝi, %s sen dato preterlasitaj.",
        probed,
        len(entries),
        out_of_range,
        skipped_undated,
    )
    return entries, out_of_range, skipped_undated, error


def collect_urls(cfg: ScrapeConfig) -> URLCollectionResult:
    cfg.normalize()
    session = shared_session(cfg)
    session.headers.update({"User-Agent": USER_AGENT})
    method = (cfg.method or "auto").lower()

    year_start = cfg.start_date.year
    year_end = cfg.end_date.year

    aggregated: List[_CollectedEntry] = []
    fallback_needed = False
    out_of_range_skipped = 0
    last_ok_year: Optional[int] = None
    errors: List[str] = []
    # 年別インデックスが読めなかった年と、その状態 ("unauthorized" | "unavailable")
    missing_years: List[Tuple[int, str]] = []

    for year in range(year_start, year_end + 1):
        batch, year_skipped, status = _collect_from_year(year, cfg, session)
        out_of_range_skipped += year_skipped
        if status == "ok":
            last_ok_year = year
            aggregated.extend(batch)
        else:
            missing_years.append((year, status))
        # 購読者専用 (401) の範囲は年とともに後ろへずれるので、401 は年を問わず
        # Nova! / プローブへフォールバックする。直近年は障害や空ページでも補う。
        if status == "unauthorized" or (
            year >= date.today().year - 1
            and (status != "ok" or (not batch and year_skipped == 0))
        ):
            fallback_needed = True

    probe_entries: List[_CollectedEntry] = []
    probe_ran = False
    probe_floor: Optional[date] = None
    if fallback_needed:
        current_entries = _collect_from_current(cfg, session)
        if not current_entries:
            # Nova! は常に直近の約 20 本を載せるので、0 件は取得・解析の失敗 (プローブの起点もなくなる)
            errors.append(
                "MONATO: neniu artikolo trovita en la Nova!-paĝo; ĉu la paĝa strukturo ŝanĝiĝis?"
            )
        # アンカー ID はフィルタ前の全 Nova! エントリから取る (要求期間が古く
        # 全件期間外でも、プローブの起点は必要)。
        anchor_ids = _publika_ids(entry.url for entry in current_entries)
        # Nova! の号ヒントも月初正規化された月粒度なので月初で比較する。
        start_floor = cfg.start_date.replace(day=1)
        for entry in current_entries:
            if entry.published and (
                entry.published.date() < start_floor or entry.published.date() > cfg.end_date
            ):
                out_of_range_skipped += 1
            else:
                aggregated.append(entry)
        if method in ("archive", "both"):
            probe_ran = True
            probe_floor = date(last_ok_year + 1, 1, 1) if last_ok_year else None
            probe_entries, probe_skipped, _undated_skipped, probe_error = _collect_from_probe(
                cfg, session, anchor_ids, probe_floor
            )
            out_of_range_skipped += probe_skipped
            aggregated.extend(probe_entries)
            if probe_error:
                errors.append(probe_error)
        else:
            # Nova! ページはおよそ直近 2 か月の publika 記事しか載せないため、
            # それより前に及ぶ範囲指定では取りこぼしが起こり得る。
            logging.warning(
                "MONATO: la jarindeksoj de la lastaj jaroj postulas abonon (HTTP 401) "
                "kaj la Nova!-paĝo listigas nur lastatempajn artikolojn. "
                "Peto ekde %s povas maltrafi artikolojn — uzu --method archive aŭ both "
                "por ID-proba kolektado.",
                cfg.start_date,
            )

    for year, status in missing_years:
        # プローブの範囲内なら補えている (打ち切り・中断は probe_error で報告済み)。
        # 直近年は購読者専用・未作成が普通で、Nova! で補う (method feed/auto は警告のみ)。
        # それ以外は 1 年分が丸ごと欠ける
        if probe_ran and (probe_floor is None or year >= probe_floor.year):
            continue
        if fallback_needed and year >= date.today().year - 1:
            continue
        if status == "unauthorized":
            hint = "" if probe_ran else " (uzu --method archive aŭ both)"
            errors.append(
                f"MONATO: la jarindekso {year} postulas abonon (HTTP 401) kaj la ID-probo ne kovris "
                f"ĝin; artikoloj de {year} mankas{hint}."
            )
        else:
            errors.append(f"MONATO: la jarindekso {year} ne atingeblis; artikoloj de {year} mankas.")

    unique: Dict[str, _CollectedEntry] = {}
    for entry in aggregated:
        if entry.url not in unique:
            unique[entry.url] = entry
    duplicates_removed = len(aggregated) - len(unique)

    urls: List[str] = []
    earliest: Optional[date] = None
    latest: Optional[date] = None

    MONATO_META.clear()

    def sort_key(item: _CollectedEntry) -> Tuple[datetime, str]:
        if item.published:
            return (item.published, item.url)
        far_future = datetime.max.replace(tzinfo=None)
        return (far_future, item.url)

    sorted_entries = sorted(unique.values(), key=sort_key)

    for entry in sorted_entries:
        urls.append(entry.url)
        MONATO_META[entry.url] = {
            "published": entry.published,
            "category": entry.category,
            "section": entry.section,
            "author_hint": entry.author_hint,
            "title_hint": entry.title,
        }
        if entry.published:
            pub_date = entry.published.date()
            if earliest is None or pub_date < earliest:
                earliest = pub_date
            if latest is None or pub_date > latest:
                latest = pub_date

    # *_initial は dedup 前の生収集数、*_used は dedup を生き残ったエントリの
    # 出所 (source) で数える (URL 集合照合だと first-wins dedup と食い違う)。
    archive_used = sum(1 for entry in sorted_entries if entry.source == "archive")
    feed_used = len(sorted_entries) - archive_used

    return MonatoCollectionResult(
        urls=urls,
        feed_initial=len(aggregated) - len(probe_entries),
        archive_initial=len(probe_entries),
        rest_initial=0,
        feed_used=feed_used,
        archive_used=archive_used,
        rest_used=0,
        duplicates_removed=duplicates_removed,
        out_of_range_skipped=out_of_range_skipped,
        earliest_date=earliest,
        latest_date=latest,
        errors=errors,
    )


def _inside(node: Tag, container: Tag) -> bool:
    return any(parent is container for parent in node.parents)


_BODY_BLOCKS = ("p", "h3", "h4", "h5", "h6")


def _run_text(nodes: List[object]) -> str:
    # 元の木は筆者・日付の抽出にも使うので動かさず、写しを 1 つの要素にまとめて _inline_text にかける
    wrapper = BeautifulSoup("", "lxml").new_tag("span")
    for node in nodes:
        wrapper.append(copy.copy(node))
    return _inline_text(wrapper)


def _extract_paragraphs(container: Tag) -> List[str]:
    h1 = container.find("h1")
    texts: List[str] = []
    if h1 is not None:
        # h1 より前の h3 は欄名 (Politiko など)。本文の小見出し (h3〜h6) は h1 以降に p と並ぶので文書順に読む。
        # 導入段落が p で包まれず容器直下に <b> などで書かれたページがあるので、容器直下の文字列・
        # インライン要素の連なりもブロック要素で区切って 1 段落にする。右寄せの筆者 div は読まない
        run: List[object] = []

        def flush() -> None:
            if run:
                texts.append(_run_text(run))
                run.clear()

        for node in h1.next_elements:
            if not _inside(node, container):
                break
            if isinstance(node, Tag) and node.name in _BODY_BLOCKS:
                if not _has_emitted_ancestor(node, container, names=_BODY_BLOCKS):
                    flush()
                    texts.append(_inline_text(node))
                continue
            if node.parent is not container:
                continue
            if type(node) is NavigableString or (
                isinstance(node, Tag)
                and node.name not in _INLINE_BLOCKS
                and node.find(_BODY_BLOCKS) is None
            ):
                run.append(node)
            elif isinstance(node, Tag):
                flush()
        flush()
    else:
        texts = [
            _inline_text(block)
            for block in container.find_all("p")
            if not _has_emitted_ancestor(block, container, names=("p", "h3", "h4"))
        ]
    paragraphs: List[str] = []
    for text in texts:
        if not text:
            continue
        paragraphs.append(text)
        if "sekcio por abonantoj" in text.lower():
            break
    if not paragraphs:
        text = _inline_text(container)
        if text:
            paragraphs.append(text)
    return [base_clean_text(p) for p in paragraphs if p]


def _extract_categories(container: Tag, meta: Dict[str, Optional[object]]) -> List[str]:
    # ページの欄名 (h1 直前の h3) と主題 (h2.tem) を先に置き、収集経路 (Nova!・年別インデックス・
    # プローブ) で並びが変わらないようにする。h1 以降の h3 は本文の小見出しなので使わない。
    # Nova! の主題ラベルはページの h2 と大小文字だけ違うことがある (RELIGIO / Religio) ので大小文字を無視して重複を除く
    h1 = container.find("h1")
    if h1 is not None:
        heads = [el for el in h1.find_all_previous(["h2", "h3"]) if _inside(el, container)]
        h3 = next((el for el in heads if el.name == "h3"), None)
        h2 = next((el for el in heads if el.name == "h2"), None)
    else:
        h3 = container.find("h3")
        h2 = container.find("h2")
    categories: List[str] = []
    seen = set()
    for candidate in [
        _inline_text(h3) if h3 else None,
        _inline_text(h2) if h2 else None,
        meta.get("section"),
        meta.get("category"),
    ]:
        cleaned = str(candidate).strip() if candidate else ""
        if cleaned and cleaned.casefold() not in seen:
            seen.add(cleaned.casefold())
            categories.append(cleaned)
    return categories


def _find_article_container(soup: BeautifulSoup) -> Tag:
    h1 = soup.find("h1")
    node: Optional[Tag] = h1
    while node and node.name != "td":
        node = node.parent  # type: ignore[assignment]
    return node or soup.body or soup


def fetch_article(
    url: str,
    cfg: ScrapeConfig,
    session: Optional[requests.Session] = None,
    resp: Optional[requests.Response] = None,
) -> Article:
    """resp (url を取得済みの応答) を渡すと再取得せずに解析する。その場合 404 でも
    Wayback には退避しない (プローブで不存在の ID をアーカイブ版で拾わないため)。"""
    cfg.normalize()
    if resp is None:
        s = session or shared_session(cfg)
        s.headers.update({"User-Agent": USER_AGENT})
        # 収集系と同じく retry_get で一時的な 5xx・切断を再試行する
        # (単発 s.get だと一過性エラーの記事がそのまま欠落する)
        resp = retry_get(s, url, cfg)
        if resp.status_code == 404:
            archived = _fetch_archived_copy(url, s, cfg.timeout_sec)
            if archived is not None:
                resp = archived
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, "lxml")

    container = _find_article_container(soup)
    title_tag = container.find("h1") or soup.find("h1")
    title = base_clean_text(_inline_text(title_tag) if title_tag else url)

    meta = MONATO_META.get(url, {})
    published_dt = meta.get("published")
    author_hint = meta.get("author_hint")

    # \\s と二重エスケープすると「リテラル \ + s*」の意味になり一切マッチしない
    # (author が常に author_hint 頼みになる) ので、\s* が正しい。
    footer_divs = container.find_all(
        "div", attrs={"style": re.compile(r"text-align\s*:\s*right", re.I)}
    )
    # 筆者写真のある記事は最初の右寄せ div が <img> だけなので、文字のある最初の div を筆者名とする。
    # 姓は小型大文字 B<span class="mm">AK</span> で書かれるため、_inline_text で境目に空白を入れずにつなぐ
    author: Optional[str] = None
    for div in footer_divs:
        text = _inline_text(div)
        if text:
            author = text
            break
    if not author and author_hint:
        author = author_hint

    categories = _extract_categories(container, meta)

    body_paragraphs = _extract_paragraphs(container)
    content_text = "\n\n".join(body_paragraphs)

    if not published_dt:
        fallback = _extract_last_adapto(soup)
        if fallback:
            published_dt = fallback

    return Article(
        url=url,
        title=title,
        published=published_dt,
        content_text=content_text,
        author=author,
        categories=categories or None,
        audio_links=None,
    )


def _extract_last_adapto(soup: Optional[Tag]) -> Optional[datetime]:
    # publika ページでは最初の table (外枠) にあるが、年別インデックス由来の
    # /YYYY/NNNNNN.php?p では最初の table が掲載号の注記で、2 つ目以降にある
    if not soup:
        return None
    for table in soup.find_all("table"):
        text = table.get_text(" ", strip=True)
        match = re.search(r"Lasta adapto de tiu ĉi paĝo:\s*(\d{4}-\d{2}-\d{2})", text)
        if not match:
            continue
        try:
            return datetime.strptime(match.group(1), "%Y-%m-%d")
        except ValueError:
            return None
    return None


def _fetch_archived_copy(url: str, session: requests.Session, timeout: int) -> Optional[requests.Response]:
    """
    Fetch a snapshot from the Internet Archive when the live article is gone.
    """
    params = {
        "url": url,
        "output": "json",
        "filter": "statuscode:200",
        "collapse": "digest",
        "limit": "50",
    }
    data = None
    for attempt in range(3):
        try:
            resp = session.get(WAYBACK_CDX_ENDPOINT, params=params, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            break
        except Exception as exc:  # noqa: BLE001
            logging.warning("Wayback lookup failed for %s (attempt %s/3): %s", url, attempt + 1, exc)
            if attempt == 2:
                return None
            time.sleep(1 + attempt)
    entries = data[1:] if isinstance(data, list) and len(data) > 1 else []
    if not entries:
        return None
    # Pick the most recent snapshot (last row).
    timestamp = entries[-1][1]
    snapshot_url = WAYBACK_SNAPSHOT_URL.format(timestamp=timestamp, original=url)
    for attempt in range(3):
        try:
            snap = session.get(snapshot_url, timeout=timeout)
            if snap.status_code == 200:
                logging.info("Served %s via Wayback snapshot %s", url, timestamp)
                return snap
        except Exception as exc:  # noqa: BLE001
            logging.warning("Wayback snapshot fetch failed for %s (attempt %s/3): %s", url, attempt + 1, exc)
        time.sleep(1 + attempt)
    return None


__all__ = [
    "collect_urls",
    "fetch_article",
    "shared_session",
    "set_progress_callback",
]
