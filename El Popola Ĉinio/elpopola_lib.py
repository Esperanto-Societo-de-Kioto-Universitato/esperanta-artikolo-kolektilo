# -*- coding: utf-8 -*-
"""
elpopola_lib.py

Custom scraper helpers for El Popola Ĉinio (esperanto.china.org.cn).
The site predates WordPress and exposes lists via numerous `node_*.htm`
pages. Articles live at URLs like `/YYYY-MM/DD/content_<id>.htm`.
"""
from __future__ import annotations

import logging
import copy
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from retradio_lib import (  # type: ignore
    Article,
    FetchError,
    ScrapeConfig,
    URLCollectionError,
    URLCollectionResult,
    _WS_RUN_RE,
    _clean_text as base_clean_text,
    _get as retry_get,
    _session as shared_session,
    set_progress_callback,
)

try:
    from retradio_lib import _norm_title  # type: ignore
except ImportError:  # 共通ライブラリが古いとき
    def _norm_title(t: str) -> str:
        return _WS_RUN_RE.sub(" ", t).strip()

USER_AGENT = "Mozilla/5.0 (compatible; ElPopolaScraper/1.0; +http://esperanto.china.org.cn)"
DEFAULT_NODE_IDS = [
    "7117770",  # Plej freŝaj
    "7117772",  # Novaĵoj
    "7117773",
    "7117774",
    "7117775",
    "7117776",
    "7117777",
    "7117778",
    "7117779",
    "7117780",
    "7117782",
    "7117783",
    "7117784",
    "7117785",
    "7117786",
    "7117787",
    "7117788",
    "7117969",
    "8007437",
    "8019218",
    "8019350",
]
MAX_NODE_PAGES = 20

# 最新記事を節に関係なく並べる集約一覧 (Plej Freŝaj・Novaĵoj・Aktuala temo・新闻中心)。記事の分類を表さない
AGGREGATE_NODE_IDS = {"7117770", "7117772", "7117776", "7122182"}
LATEST_NODE_ID = "7117770"
VIDEO_NODE_ID = "7117771"
# サイトの一覧はノードあたり 10 ページで古い記事から消える。最終ページの日付は厳密な降順ではないので余裕を見る
LIST_DEPTH_MARGIN_DAYS = 14

EPC_META: Dict[str, Dict[str, object]] = {}


@dataclass
class _CollectedEntry:
    url: str
    title: str
    published: Optional[datetime]
    section: Optional[str]
    node_id: str = ""
    # (節名, node ID) を読んだ順に重複なしで持つ
    sections: List[Tuple[str, str]] = field(default_factory=list)


@dataclass
class _NodeResult:
    entries: List[_CollectedEntry] = field(default_factory=list)
    failures: List[Tuple[str, BaseException]] = field(default_factory=list)
    loaded: bool = False
    # 404 かリンク無しで一覧の終わりに達したか、とその直前のページの最古日
    reached_end: bool = False
    last_page_oldest: Optional[date] = None
    # 期間内の他ホストの記事 (url, 題名, node ID)
    other_host: List[Tuple[str, str, str]] = field(default_factory=list)


def _normalize_base(base_url: str) -> str:
    base = base_url.strip()
    if not base.startswith(("http://", "https://")):
        base = "http://" + base
    return base.rstrip("/")


def _session(cfg: ScrapeConfig) -> requests.Session:
    s = shared_session(cfg)
    s.headers.update({"User-Agent": USER_AGENT})
    return s


def _parse_date_from_url(url: str) -> Optional[datetime]:
    m = re.search(r"/(20\d{2})-(\d{2})/(\d{2})/", url)
    if not m:
        return None
    year, month, day = map(int, m.groups())
    try:
        return datetime(year, month, day)
    except ValueError:
        return None


# 一覧ページの <title> は「節名-esperanto.china.org.cn」(区切りの前後に空白なし)。節名自体にも「-」がある (E-movado・UK-oj)
_SECTION_SUFFIX_RE = re.compile(
    r"\s*(?:-\s*(?:esperanto\.china\.org\.cn|El Popola Ĉinio)|_\s*China\.org\.cn)\s*$", re.I
)


def _extract_section_name(soup: BeautifulSoup) -> Optional[str]:
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
        return _SECTION_SUFFIX_RE.sub("", title).strip() or title
    heading = soup.find(["h1", "h2"])
    if heading:
        return heading.get_text(" ", strip=True)
    return None


@dataclass
class EPCURLCollectionResult(URLCollectionResult):
    # 読み込めなかった一覧ページ。その先の記事は URL 候補にも本文の失敗一覧にも出ないので、CLI が失敗として報告する
    load_failures: List[str] = field(default_factory=list)
    # load_failures と同じページを例外のまま (表示言語に合わせて説明を作るため)
    load_errors: List[Tuple[str, BaseException]] = field(default_factory=list)
    # 失敗ではないが結果が不完全かもしれないことの注意
    warnings: List[str] = field(default_factory=list)
    # 期間内だが他ホスト (espero.chinareports.org.cn など) にあるため集めなかった記事。動画ページと本ホストの複製は除く
    skipped_other_host: List[str] = field(default_factory=list)


def _collect_from_node(
    node_id: str,
    cfg: ScrapeConfig,
    session: requests.Session,
    base_url: str,
    base_host: str,
) -> _NodeResult:
    result = _NodeResult()
    seen_on_node: set[str] = set()
    seen_other: set[str] = set()
    prev_page_links: Dict[str, date] = {}
    max_pages = cfg.max_pages or MAX_NODE_PAGES

    for page in range(1, max_pages + 1):
        if page == 1:
            page_url = f"{base_url}/node_{node_id}.htm"
        else:
            page_url = f"{base_url}/node_{node_id}_{page}.htm"
        try:
            resp = retry_get(session, page_url, cfg)
        except Exception as exc:  # noqa: BLE001
            logging.getLogger(__name__).warning("failed to load node page %s: %s", page_url, exc)
            result.failures.append((page_url, exc))
            break
        # 最終ページの次のページは 404 になる (正常な終わり)
        if resp.status_code == 404:
            result.reached_end = True
            break
        if resp.status_code != 200:
            result.failures.append((page_url, FetchError(f"HTTP {resp.status_code}", page_url, resp.status_code)))
            break
        result.loaded = True
        soup = BeautifulSoup(resp.content, "lxml")
        section_name = _extract_section_name(soup)
        links = soup.select("a[href*='content_']")
        if not links:
            result.reached_end = True
            break

        # 記事リンクとその日付 (他ホスト・期間外・既出を含む。Videoj の一覧は他ホストのリンクだけ)
        page_links: Dict[str, date] = {}
        page_added = False

        for link in links:
            href = link.get("href")
            if not href:
                continue
            url = urljoin(base_url + "/", href)
            parsed = urlparse(url)
            other_host = bool(parsed.netloc and parsed.netloc != base_host)
            dt = _parse_date_from_url(url)
            if dt:
                page_links[url] = dt.date()
            if not other_host and url in seen_on_node:
                continue
            if dt:
                if dt.date() > cfg.end_date:
                    continue
                if dt.date() < cfg.start_date:
                    continue
            else:
                # Skip items that do not follow the standard pattern.
                continue

            title = _norm_title(link.get_text(" ", strip=True))
            if other_host:
                if url not in seen_other or title:
                    result.other_host.append((url, title, node_id))
                    seen_other.add(url)
                continue
            if not title:
                continue

            result.entries.append(_CollectedEntry(url=url, title=title, published=dt, section=section_name,
                                                  node_id=node_id))
            seen_on_node.add(url)
            page_added = True

        # どのページにも同じ新着欄 (最新記事) と固定記事 (古い記事) が載る。前のページにもあったリンクを除いた
        # 残りが一覧の本体。1 ページ目では見分けられないので、打ち切りは 2 ページ目から判定する
        list_dates = [d for u, d in page_links.items() if u not in prev_page_links]
        if list_dates:
            result.last_page_oldest = min(list_dates)
        if page > 1 and not page_added and list_dates and max(list_dates) < cfg.start_date:
            break
        prev_page_links = page_links

    return result


_NODE_PATH_RE = re.compile(r"^/node_(\d+)\.htm$")


def _discover_nodes(
    cfg: ScrapeConfig, session: requests.Session, base_url: str
) -> Tuple[List[str], Optional[Tuple[str, BaseException]]]:
    """(node ID の一覧, トップページを読めなかったときはその URL と例外) を返す。"""
    nodes = set(DEFAULT_NODE_IDS)
    failure: Optional[Tuple[str, BaseException]] = None
    base_host = urlparse(base_url).netloc
    try:
        resp = retry_get(session, base_url, cfg)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        # 他ホスト (www.espero.com.cn など) の node ID は本ホストでは 404。iframe で読み込む本ホストのノードもある
        for tag, attr in (("a", "href"), ("iframe", "src")):
            for el in soup.find_all(tag, **{attr: True}):
                parsed = urlparse(urljoin(base_url + "/", el[attr].strip()))
                m = _NODE_PATH_RE.match(parsed.path)
                if m and parsed.netloc == base_host:
                    nodes.add(m.group(1))
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).warning("failed to discover nodes dynamically", exc_info=True)
        failure = (base_url, exc)
    return sorted(nodes), failure


def _title_key(title: str) -> str:
    return _norm_title(title).lstrip("•· ").strip().casefold()


def collect_urls(cfg: ScrapeConfig) -> EPCURLCollectionResult:
    cfg.normalize()
    base_url = _normalize_base(cfg.base_url)
    session = _session(cfg)

    aggregated: Dict[str, _CollectedEntry] = {}
    nodes, discover_failure = _discover_nodes(cfg, session, base_url)
    base_host = urlparse(base_url).netloc
    load_errors: List[Tuple[str, BaseException]] = [discover_failure] if discover_failure else []
    loaded_any = False
    other_host: Dict[str, Tuple[List[str], List[str]]] = {}
    warnings: List[str] = []

    for node_id in nodes:
        node = _collect_from_node(node_id, cfg, session, base_url, base_host)
        load_errors.extend(node.failures)
        loaded_any = loaded_any or node.loaded
        # サイト全体に接続できないときに、残りの全ノードで再試行を繰り返さない
        if not loaded_any and len(load_errors) >= 3:
            break
        if (node_id == LATEST_NODE_ID and node.reached_end and node.last_page_oldest
                and cfg.start_date < node.last_page_oldest - timedelta(days=LIST_DEPTH_MARGIN_DAYS)):
            warnings.append(
                f"El Popola Ĉinio: {node.last_page_oldest.isoformat()} より前はトピック別ノードに載った記事しか"
                "一覧から見つからない (不完全)"
            )
        for entry in node.entries:
            existing = aggregated.get(entry.url)
            if existing is None:
                entry.sections = [(entry.section, entry.node_id)] if entry.section else []
                aggregated[entry.url] = entry
                continue
            if entry.section and all(name != entry.section for name, _ in existing.sections):
                existing.sections.append((entry.section, entry.node_id))
        for url, title, node_id_ in node.other_host:
            titles, node_ids = other_host.setdefault(url, ([], []))
            if title:
                titles.append(title)
            node_ids.append(node_id_)

    load_failures = [f"{page_url} ({exc})" for page_url, exc in load_errors]
    if not loaded_any:
        # 0 件で返すと「期間内に記事なし」と区別できないため、例外にして CLI・アプリに失敗として伝える
        if not load_errors:
            load_errors = [(base_url, FetchError("どのノードページも 404 (サイトの構成が変わった可能性)", base_url, 404))]
        detail = "; ".join(f"{page_url} ({exc})" for page_url, exc in load_errors[:3])
        raise URLCollectionError(f"El Popola Ĉinio の一覧ページを 1 つも読み込めませんでした: {detail}", load_errors[:3])

    # 他ホストの記事は大半が動画ページ (Videoj に載り、UK-oj などにも載ることがある) か本ホスト記事の複製なので、
    # それ以外だけを知らせる
    own_titles = {_title_key(e.title) for e in aggregated.values()}
    skipped_other_host: List[str] = []
    for url, (titles, node_ids) in sorted(other_host.items()):
        if VIDEO_NODE_ID in node_ids:
            continue
        if any(_title_key(t) in own_titles for t in titles):
            continue
        logging.getLogger(__name__).warning("skipped article on another host: %s", url)
        skipped_other_host.append(url)

    urls = []
    earliest: Optional[date] = None
    latest: Optional[date] = None
    EPC_META.clear()

    for url, entry in sorted(
        aggregated.items(),
        key=lambda item: ((item[1].published or datetime.max).date(), item[0]),
    ):
        urls.append(url)
        EPC_META[url] = {
            "published": entry.published,
            "section": entry.section,
            "sections": [name for name, _ in entry.sections],
            "section_nodes": [nid for _, nid in entry.sections],
            "title": entry.title,
        }
        if entry.published:
            d = entry.published.date()
            if earliest is None or d < earliest:
                earliest = d
            if latest is None or d > latest:
                latest = d

    total = len(urls)
    return EPCURLCollectionResult(
        urls=urls,
        feed_initial=total,
        archive_initial=0,
        rest_initial=0,
        feed_used=total,
        archive_used=0,
        rest_used=0,
        duplicates_removed=0,
        out_of_range_skipped=0,
        earliest_date=earliest,
        latest_date=latest,
        load_failures=load_failures,
        load_errors=load_errors,
        warnings=warnings,
        skipped_other_host=skipped_other_host,
    )


# ページ下部のフォロー欄と動画プレーヤーの定型行。本文中で WeChat などに触れた行を捨てないよう、行全体で照合する
NOISE_LINES = {
    "视频播放位置",
    "下载安装Flash播放器",
    "Ĉina Fokuso / China Focus - Esperanto",
}
NOISE_LINE_RE = re.compile(
    r"^(?:Facebook|Twitter|WeChat)\s*[:：]\s*(?:Ĉina Fokuso|China Focus|El Popola|Skani la du-dimensian kodon|$)"
)

FALLBACK_SELECTORS = (
    "#content",
    "#contentArea",
    "#main",
    "#center",
    ".content",
    ".article",
    ".article-content",
    ".main",
    "article",
)

DATE_PATTERNS = [
    re.compile(r"(20\d{2})-(\d{2})-(\d{2})"),
    re.compile(r"(20\d{2})/(\d{2})/(\d{2})"),
]


def _clean_paragraphs(lines: Iterable[str]) -> List[str]:
    cleaned: List[str] = []
    for line in lines:
        text = line.strip()
        if not text:
            continue
        # フォロー欄は NBSP 区切りのページと通常の空白のページがあるので、空白を揃えて照合する
        probe = re.sub(r"\s+", " ", text)
        if probe in NOISE_LINES or NOISE_LINE_RE.match(probe):
            continue
        cleaned.append(base_clean_text(text))
    return cleaned


# 署名行。Tradukis・Esperantigis・Redaktoro は翻訳者・編集者なので author にしない
_AUTHOR_PATTERNS = [
    re.compile(r"^(?:Verkis|Raportis)(?:\s+kaj\s+fot(?:is|oj))?(?:\s*\([^()]*\))?\s*[:：]\s*(.+)$"),
    # コロンのない「Verkis Bui Hai Mung」。本文の文 (「Verkis li ...」) を拾わないよう、大文字で始まり文末記号のないものに限る
    re.compile(r"^(?:Verkis|Raportis)(?:\s+kaj\s+fot(?:is|oj))?\s+([A-ZĈĜĤĴŜŬ][^.!?]*)$"),
    re.compile(r"^(?:Verkita|Raportita)\s+de\s+(.+)$"),
    re.compile(r"^(?:Verkinto|Aŭtoro|Teksto(?:\s+kaj\s+fotoj)?)\s*[:：]\s*(.+)$"),
]
# 寄稿記事の冒頭の右寄せ署名「de Anthony Moretti*」「de Guo Qingyang kaj Chai Ying」(* は文末の著者紹介への印) と
# 「John Magesa (Tanzanio)」。本文の小見出し「De Britio al Pekino」を拾わないよう、1 段落目の大文字で始まる語の並びに限る
_LEAD_AUTHOR_PATTERNS = [
    re.compile(r"^[dD]e\s+(?:d-ro\s+)?([A-ZĈĜĤĴŜŬ][^\s,:.!?*]*(?:(?:,\s*|\s+kaj\s+|\s+)[A-ZĈĜĤĴŜŬ][^\s,:.!?*]*)*)\*?$"),
    re.compile(r"^([A-ZĈĜĤĴŜŬ][^\s:.!?()]*(?:\s+[A-ZĈĜĤĴŜŬ][^\s:.!?()]*){1,3}\s*\([A-ZĈĜĤĴŜŬ][^():.!?]{1,40}\))$"),
]


def _clean_author(raw: str) -> Optional[str]:
    author = re.split(r"[,;]?\s*\b(?:Tradukis|Esperantigis|Redaktis|Redaktoro|Fotis|Fotoj|Foto)\s*[:：]", raw)[0]
    # 名前の後の肩書き「(Profesoro de ... Universitato)」は除く。「(Jado)」のような 1 語の別名や国名は残す
    author = re.sub(r"\s*\([^()]*\s[^()]*\)$", "", author.strip()).strip(" ,;.")
    if author and len(author) <= 60:
        return author
    return None


def _extract_author(paragraphs: List[str]) -> Optional[str]:
    # 署名は本文の末尾 (まれに冒頭) の独立した行にある。本文中の文を拾わないよう、両端の数行の短い行だけを見る
    n = len(paragraphs)
    candidates = list(range(n - 1, max(n - 4, -1), -1)) + list(range(min(3, n)))
    for i in dict.fromkeys(candidates):
        line = re.sub(r"\s+", " ", paragraphs[i]).strip()
        if len(line) > 200:
            continue
        for pattern in _AUTHOR_PATTERNS:
            m = pattern.match(line)
            if not m:
                continue
            author = _clean_author(m.group(1))
            if author:
                return author
    if n:
        line = re.sub(r"\s+", " ", paragraphs[0]).strip()
        for pattern in _LEAD_AUTHOR_PATTERNS:
            m = pattern.match(line)
            if m:
                author = _clean_author(m.group(1))
                if author:
                    return author
    return None


_PARA_BREAK = "\u2029"
_BLOCK_TAGS = ["p", "div", "br", "h1", "h2", "h3", "h4", "h5", "h6", "li", "ul", "ol", "table", "tr", "td", "th",
               "blockquote", "section", "article", "center", "figure", "figcaption", "dd", "dt"]


def _block_lines(node: BeautifulSoup) -> List[str]:
    # get_text("\n") はインライン要素 (<span>・<em>・<strong> など) の境目でも改行するため、段落の途中に
    # 装飾があると 1 段落が細切れになる。ブロック要素と <br> の境目だけで区切り、ソース中の改行は空白として扱う
    work = copy.copy(node)
    for el in work.find_all(_BLOCK_TAGS):
        if el.name == "br":
            el.replace_with(_PARA_BREAK)
        else:
            el.insert_before(_PARA_BREAK)
            el.insert_after(_PARA_BREAK)
    # _WS_RUN_RE が段落区切り文字を空白に畳むことがあるので、区切ってから正規化する
    return [_WS_RUN_RE.sub(" ", part) for part in work.get_text("").split(_PARA_BREAK)]


def _strip_embedded_markup(node: BeautifulSoup) -> None:
    # 他ページの HTML ごと貼り込まれた記事では本文セル内に <title>/<style> があり、
    # 関連記事のタイトル (エスケープ済みの <span> タグ付き) が本文末尾に混入する
    for bad in node.find_all(["title", "style", "script", "noscript"]):
        bad.decompose()


def fetch_article(url: str, cfg: ScrapeConfig, session: Optional[requests.Session] = None) -> Article:
    cfg.normalize()
    s = session or _session(cfg)
    resp = retry_get(s, url, cfg)
    resp.raise_for_status()
    html = resp.text
    soup = BeautifulSoup(html, "lxml")

    meta = EPC_META.get(url, {})
    published = meta.get("published")

    legacy = _extract_legacy_article(soup)
    if legacy:
        title, date_str, content_node = legacy
        if not published:
            published = _parse_explicit_date(date_str) or _parse_date_from_url(url)
        _strip_embedded_markup(content_node)
        raw_lines = _block_lines(content_node)
        paragraphs = _clean_paragraphs(raw_lines)
        if not paragraphs:
            # 動画・写真特設ページは本文セルが Flash 案内などのノイズだけで空になる。
            # 全文フォールバックはナビゲーションを本文として拾ってしまうため行わず、
            # 警告を出して空のまま出力する (実例: 2025-09-26 動画ページ等)。
            logging.getLogger(__name__).warning(
                "本文が空のまま出力します (動画・写真のみのページ?): %s", url)
    else:
        title = base_clean_text(meta.get("title") or _fallback_title(soup)) or url
        if not published:
            published = _extract_date_from_document(soup) or _parse_date_from_url(url)
        content_node = _fallback_article_root(soup)
        _strip_embedded_markup(content_node)
        raw_lines = _block_lines(content_node)
        paragraphs = _clean_paragraphs(raw_lines)
        if not paragraphs:
            paragraphs = [base_clean_text(content_node.get_text(" ", strip=True))]

    content_text = "\n\n".join(paragraphs)

    author = _extract_author(paragraphs)
    title = _norm_title(title)
    categories = _categories_from_meta(meta)

    return Article(
        url=url,
        title=title or meta.get("title", url),
        published=published,
        content_text=content_text,
        author=author,
        categories=categories,
        audio_links=None,
    )


def _categories_from_meta(meta: Dict[str, object]) -> Optional[List[str]]:
    names = meta.get("sections")
    if names is None:
        names = [meta["section"]] if meta.get("section") else []
    node_ids = list(meta.get("section_nodes") or [])
    pairs = [(base_clean_text(str(name)), node_ids[i] if i < len(node_ids) else "") for i, name in enumerate(names)]
    pairs = [(name, nid) for name, nid in pairs if name]
    specific = [name for name, nid in pairs if nid not in AGGREGATE_NODE_IDS]
    categories = specific or [name for name, _ in pairs]
    return categories or None


def _extract_legacy_article(soup: BeautifulSoup) -> Optional[tuple[str, str, BeautifulSoup]]:
    first_table = soup.find("table")
    if not first_table:
        return None
    rows = first_table.find_all("tr")
    if len(rows) < 2:
        return None
    title = base_clean_text(_norm_title(rows[0].get_text(" ", strip=True)))
    date_str = rows[1].get_text(" ", strip=True)
    content_td = rows[3].find("td") if len(rows) > 3 else rows[-1].find("td")
    if not content_td:
        content_td = first_table
    return title, date_str, content_td


def _parse_explicit_date(value: str) -> Optional[datetime]:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d")
    except Exception:
        match = DATE_PATTERNS[0].search(text)
        if match:
            year, month, day = map(int, match.groups())
            try:
                return datetime(year, month, day)
            except ValueError:
                return None
    return None


def _fallback_article_root(soup: BeautifulSoup) -> BeautifulSoup:
    for selector in FALLBACK_SELECTORS:
        node = soup.select_one(selector)
        if node:
            for bad in node.select("script, style, nav, header, footer, aside, noscript"):
                bad.decompose()
            return node
    body = soup.body or soup
    for bad in body.select("script, style, nav, header, footer, aside, noscript"):
        bad.decompose()
    return body


def _fallback_title(soup: BeautifulSoup) -> str:
    h1 = soup.find("h1")
    if h1:
        return _norm_title(h1.get_text(" ", strip=True))
    if soup.title:
        return _norm_title(soup.title.get_text(" ", strip=True))
    return ""


def _extract_date_from_document(soup: BeautifulSoup) -> Optional[datetime]:
    for selector in ["time", ".publish-time", ".pubtime", ".date", ".info"]:
        node = soup.select_one(selector)
        if not node:
            continue
        candidate = node.get("datetime") or node.get_text(" ", strip=True)
        parsed = _parse_explicit_date(candidate or "")
        if parsed:
            return parsed
    text_sample = soup.get_text(" ", strip=True)
    for pattern in DATE_PATTERNS:
        match = pattern.search(text_sample)
        if match:
            year, month, day = map(int, match.groups())
            try:
                return datetime(year, month, day)
            except ValueError:
                continue
    return None


__all__ = [
    "collect_urls",
    "fetch_article",
    "shared_session",
    "set_progress_callback",
]
