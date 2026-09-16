# -*- coding: utf-8 -*-
"""
uea_facila_lib.py

Helper utilities to scrape articles from uea.facila.org.
The site runs on Invision Community, so we cannot rely on the WordPress
helpers provided in retradio_lib.  Instead we scrape the public "Ĉiu aktivado"
stream (https://uea.facila.org/malkovri/) and fetch individual article pages.
"""
from __future__ import annotations

import contextlib
import json
import logging
import re
import time
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone, date
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup, Tag
import dateparser

from retradio_lib import (  # type: ignore
    Article,
    FetchError,
    ScrapeConfig,
    URLCollectionError,
    URLCollectionResult,
    _clean_text as base_clean_text,
    _has_emitted_ancestor,
    _inline_text,
    _session as shared_session,
    set_progress_callback,
)

USER_AGENT = "Mozilla/5.0 (compatible; UEAFacilaScraper/1.0; +https://uea.facila.org)"
STREAM_PATH = "/malkovri/"
VALID_PATH_SEGMENTS = (
    "/artikoloj/",
    "/filmetoj/",
    "/niaj-legantoj/",
    "/loke/",
)
CATEGORY_PATHS = VALID_PATH_SEGMENTS
# 認証情報は環境変数からのみ受け取る (ソースへの直書き禁止)。
# 未設定なら _ensure_logged_in はログインを試みず公開セッションで収集する。
LOGIN_USER = os.environ.get("UEA_FACILA_USER", "")
LOGIN_PASS = os.environ.get("UEA_FACILA_PASS", "")
_LOGGED_IN = False
_LOGIN_ATTEMPTED = False

UEA_META: Dict[str, Dict[str, object]] = {}
# 直近の collect_urls で取得できなかった、または記事を 1 件も抽出できなかった一覧ページ。
# CLI が import して終了コードの判定に使うので、再代入せず clear する
COLLECT_ERRORS: List[str] = []


class _EmptyListingError(FetchError):
    """一覧の 1 ページ目は取得できたが項目を 1 件も抽出できなかった (ページ構造の変化・メンテナンス画面など)。"""


@dataclass
class UEACollectionResult(URLCollectionResult):
    # 失敗した一覧経路 (一覧 URL, 例外)。一部の経路が落ちても候補は返るので、欠けている可能性をここで伝える。
    # 呼び出し側 (アプリ) はモジュール共有の COLLECT_ERRORS ではなくこちらを読む (同時に動く別セッションに消されない)
    errors: List[Tuple[str, BaseException]] = field(default_factory=list)


def _session(cfg: ScrapeConfig) -> requests.Session:
    sess = shared_session(cfg)
    sess.headers.update({"User-Agent": USER_AGENT})
    return sess


def _canonicalize_url(base_url: str, href: str) -> Optional[str]:
    if not href:
        return None
    url = href.split("?", 1)[0]
    url = urljoin(base_url.rstrip("/") + "/", url)
    parts = urlsplit(url)
    # Ignore fragments and queries
    url = urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))
    if not any(segment in parts.path for segment in VALID_PATH_SEGMENTS):
        return None
    return url


def _parse_timestamp(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        if value.isdigit():
            return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except Exception:  # noqa: BLE001
        logging.getLogger(__name__).debug("failed to parse timestamp %s", value, exc_info=True)
    return None


def _parse_iso_datetime(value: str) -> Optional[datetime]:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    # "+0000" 形式 (JSON-LD で使用) は fromisoformat が受け付けないので ":" を補う
    text = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", text)
    try:
        return datetime.fromisoformat(text)
    except Exception:  # noqa: BLE001
        logging.getLogger(__name__).debug("iso parse failed for %s", value, exc_info=True)
        return None


def _extract_json_ld_date(soup: BeautifulSoup) -> Optional[datetime]:
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except Exception:  # noqa: BLE001
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            for node in [item] + list(item.get("@graph") or []):
                if not isinstance(node, dict):
                    continue
                value = node.get("datePublished") or node.get("dateCreated")
                if value:
                    dt = _parse_iso_datetime(str(value))
                    if dt:
                        return dt
    return None


def _fetch_listing_page(session: requests.Session, url: str, cfg: ScrapeConfig) -> BeautifulSoup:
    attempt = 1
    while True:
        try:
            resp = session.get(url, timeout=cfg.timeout_sec)
            resp.raise_for_status()
            return BeautifulSoup(resp.content, "lxml")
        except requests.RequestException as exc:
            if attempt >= cfg.max_retries:
                raise
            backoff = min(5.0 * attempt, 30.0)
            time.sleep(backoff)
            attempt += 1


def _stream_page_urls(cfg: ScrapeConfig, session: requests.Session) -> Iterable[BeautifulSoup]:
    base = cfg.base_url.rstrip("/")
    page = 1
    max_pages = cfg.max_pages or 50

    while page <= max_pages:
        url = f"{base}{STREAM_PATH}"
        if page > 1:
            url = f"{url}?page={page}"
        soup = _fetch_listing_page(session, url, cfg)
        yield soup
        page += 1
        if cfg.throttle_sec:
            time.sleep(cfg.throttle_sec)


def _extract_listing_items(container: BeautifulSoup) -> List[tuple[str, Optional[datetime]]]:
    items: List[tuple[str, Optional[datetime]]] = []
    cards = container.select(".ipsDataItem")
    if not cards:
        cards = container.select(".ipsStreamItem")
    if not cards:
        cards = container.select("article.cCmsRecord, li.cCmsRecord")
    if not cards:
        # カテゴリ一覧: artikoloj・filmetoj は div.SG_card、loke・niaj-legantoj は article.cCmsCategoryFeaturedEntry
        cards = container.select("div.SG_card, article.cCmsCategoryFeaturedEntry")
    for card in cards:
        title_el = card.select_one(".ipsDataItem_title a, .ipsStreamItem_title a") or card.select_one("h2 a[href]")
        if not title_el or not title_el.get("href"):
            continue
        href = title_el["href"]
        dt = None
        time_el = card.find("time")
        if time_el and time_el.get("datetime"):
            dt = _parse_iso_datetime(time_el["datetime"])
        if not dt and card.has_attr("data-timestamp"):
            dt = _parse_timestamp(card["data-timestamp"])
        if not dt:
            date_el = card.select_one("[data-role='recordDate'], .cCmsRecord_meta time")
            if date_el:
                dt = dateparser.parse(date_el.get_text(" ", strip=True), languages=["eo", "en"])
        # カード全体の文字列は dateparser にかけない (著者名やコメント日時など無関係な日付を記事の日付にしてしまう)
        items.append((href, dt))
    return items


def _ensure_logged_in(session: requests.Session, cfg: ScrapeConfig) -> None:
    """
    Attempt to sign in if credentials are provided. Authentication failures
    (wrong credentials, changed login form, network errors) are non-fatal:
    we log a warning and continue with a public session.
    """
    global _LOGGED_IN, _LOGIN_ATTEMPTED
    if _LOGGED_IN or _LOGIN_ATTEMPTED:
        return
    if not LOGIN_USER or not LOGIN_PASS:
        _LOGIN_ATTEMPTED = True
        logging.warning(
            "UEA_FACILA_USER/UEA_FACILA_PASS 未設定のため匿名 (公開) セッションで収集します。"
            "会員限定記事は取得されません。")
        return
    if session.cookies.get("ips4_member_id"):
        _LOGGED_IN = True
        _LOGIN_ATTEMPTED = True
        return
    _LOGIN_ATTEMPTED = True
    login_url = urljoin(cfg.base_url.rstrip("/") + "/", "ensaluti/")
    # キャッシュ済みのログインページ (サイトの no-store は無視される) だと、csrfKey に対応するセッション cookie が無く失敗する
    no_cache = session.cache_disabled() if hasattr(session, "cache_disabled") else contextlib.nullcontext()
    with no_cache:
        try:
            resp = session.get(login_url, timeout=cfg.timeout_sec)
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            logging.warning("UEA Facila login page request failed: %s. Continuing anonymously.", exc)
            return
        soup = BeautifulSoup(resp.content, "lxml")
        csrf = soup.select_one("input[name='csrfKey']")
        if not csrf or not csrf.get("value"):
            logging.warning("UEA Facila login page did not provide csrfKey; continuing without login.")
            return
        # Invision Community は送信ボタンの _processLogin でログイン方式を選ぶ。無いとログイン処理をせずフォームを返すだけ
        submit = soup.select_one("button[name='_processLogin']")
        payload = {
            "auth": LOGIN_USER,
            "password": LOGIN_PASS,
            "remember_me": "1",
            "csrfKey": csrf["value"],
            "_processLogin": (submit.get("value") if submit else None) or "usernamepassword",
        }
        try:
            post = session.post(login_url, data=payload, timeout=cfg.timeout_sec)
            post.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            logging.warning("UEA Facila login request failed: %s. Continuing anonymously.", exc)
            return
    if session.cookies.get("ips4_member_id"):
        _LOGGED_IN = True
    else:
        logging.warning("UEA Facila login credentials were rejected; continuing with public session.")


def _collect_from_stream(cfg: ScrapeConfig, session: requests.Session, aggregated: Dict[str, datetime]) -> None:
    reached_older_than_start = False
    for page_no, soup in enumerate(_stream_page_urls(cfg, session), 1):
        stream_items = soup.select(".ipsStreamItem")
        if not stream_items:
            # 1 ページ目には期間に関係なく必ず項目が並ぶので、0 件は収集の失敗。2 ページ目以降の 0 件は終わりの合図
            if page_no == 1:
                raise _EmptyListingError(
                    "活動ストリームから項目を抽出できませんでした (ページ構造が変わった可能性があります)",
                    cfg.base_url.rstrip("/") + STREAM_PATH,
                )
            break

        min_timestamp_on_page: Optional[datetime] = None
        for href, dt in _extract_listing_items(soup):
            # コメントの項目 (…?do=findComment) の日時はコメントの投稿日時。記事の投稿項目は別に並ぶ
            if "do=findComment" in href:
                continue
            canonical = _canonicalize_url(cfg.base_url, href)
            if not canonical:
                continue
            if not dt:
                continue
            dt = dt.astimezone(timezone.utc)
            item_date = dt.date()
            if item_date > cfg.end_date:
                continue
            if min_timestamp_on_page is None or dt < min_timestamp_on_page:
                min_timestamp_on_page = dt
            if item_date < cfg.start_date:
                reached_older_than_start = True
                continue
            existing = aggregated.get(canonical)
            if existing and existing >= dt:
                continue
            aggregated[canonical] = dt
        if reached_older_than_start and min_timestamp_on_page and min_timestamp_on_page.date() < cfg.start_date:
            break


def _collect_from_category(cfg: ScrapeConfig, session: requests.Session, path: str, aggregated: Dict[str, datetime]) -> None:
    base = cfg.base_url.rstrip("/")
    max_pages = cfg.max_pages or 50
    last_page = max_pages
    seen: set = set()
    reached_older_than_start = False
    page = 1
    while page <= last_page:
        url = f"{base}{path}"
        if page > 1:
            url = f"{url}page/{page}/"
        if cfg.throttle_sec:
            time.sleep(cfg.throttle_sec)
        soup = _fetch_listing_page(session, url, cfg)
        items = _extract_listing_items(soup)
        if page == 1:
            if not items:
                # 1 ページ目には必ず記事が並ぶので、0 件は正常な「期間内 0 件」ではなく収集の失敗
                raise _EmptyListingError("カテゴリ一覧から記事を抽出できませんでした (ページ構造が変わった可能性があります)", url)
            # 範囲外のページ番号は 1 ページ目に転送され同じ記事が並ぶ (/loke/ はページ送りなし) ので、総ページ数で止める
            pagination = soup.select_one("ul.ipsPagination[data-pages]")
            pages = pagination.get("data-pages", "") if pagination else ""
            last_page = min(max_pages, int(pages)) if pages.isdigit() else 1
        new_items = [(href, dt) for href, dt in items if href not in seen]
        if not new_items:
            break
        seen.update(href for href, _ in new_items)
        min_timestamp_on_page: Optional[datetime] = None
        for href, dt in new_items:
            canonical = _canonicalize_url(cfg.base_url, href)
            if not canonical:
                continue
            if not dt:
                continue
            dt = dt.astimezone(timezone.utc)
            item_date = dt.date()
            if item_date > cfg.end_date:
                continue
            if min_timestamp_on_page is None or dt < min_timestamp_on_page:
                min_timestamp_on_page = dt
            if item_date < cfg.start_date:
                reached_older_than_start = True
                continue
            existing = aggregated.get(canonical)
            if existing and existing >= dt:
                continue
            aggregated[canonical] = dt
        if reached_older_than_start and min_timestamp_on_page and min_timestamp_on_page.date() < cfg.start_date:
            break
        page += 1


def collect_urls(cfg: ScrapeConfig) -> UEACollectionResult:
    cfg.normalize()
    session = _session(cfg)

    aggregated: Dict[str, datetime] = {}
    COLLECT_ERRORS.clear()
    _ensure_logged_in(session, cfg)
    # ストリームとカテゴリ一覧は同じ 4 区分を別経路でたどるので、一部の一覧ページが落ちても残りで集める。
    # 落ちたページと 1 ページ目から項目を抽出できなかった経路は COLLECT_ERRORS と戻り値の errors に残し、すべて失敗したときだけ例外にする
    base = cfg.base_url.rstrip("/")
    route_errors: List[Tuple[str, BaseException]] = []
    try:
        _collect_from_stream(cfg, session, aggregated)
    except (requests.RequestException, _EmptyListingError) as exc:
        COLLECT_ERRORS.append(f"{base}{STREAM_PATH} ({exc})")
        route_errors.append((f"{base}{STREAM_PATH}", exc))
    for path in CATEGORY_PATHS:
        try:
            _collect_from_category(cfg, session, path, aggregated)
        except (requests.RequestException, _EmptyListingError) as exc:
            COLLECT_ERRORS.append(f"{base}{path} ({exc})")
            route_errors.append((f"{base}{path}", exc))
    for err in COLLECT_ERRORS:
        logging.warning("UEA Facila: 一覧ページから記事 URL を集められませんでした: %s", err)
    if len(COLLECT_ERRORS) == 1 + len(CATEGORY_PATHS):
        raise URLCollectionError(
            "UEA Facila のすべての一覧ページで記事 URL を集められませんでした: " + "; ".join(COLLECT_ERRORS), route_errors
        )

    entries = sorted(aggregated.items(), key=lambda pair: (pair[1], pair[0]))

    urls = [url for url, _ in entries]
    earliest: Optional[date] = None
    latest: Optional[date] = None
    UEA_META.clear()
    for url, dt in entries:
        if dt:
            d = dt.date()
            if earliest is None or d < earliest:
                earliest = d
            if latest is None or d > latest:
                latest = d
        UEA_META[url] = {"published": dt}

    return UEACollectionResult(
        urls=urls,
        feed_initial=len(urls),
        archive_initial=0,
        rest_initial=0,
        feed_used=len(urls),
        archive_used=0,
        rest_used=0,
        duplicates_removed=0,
        out_of_range_skipped=0,
        earliest_date=earliest,
        latest_date=latest,
        errors=list(route_errors),
    )


_BODY_BLOCKS = ["p", "li", "blockquote", "h2", "h3"]
_PARAGRAPH_TAGS = _BODY_BLOCKS + ["div"]


def _wrap_loose_runs(section: Tag, article: Tag) -> None:
    """section と、その中で段落になる子孫を持つ要素について、直下のテキスト・インライン要素の並びを
    子ブロックの境目ごとに div で包む (記事要素を書き換える)。"""
    # Gmail で書いた読者投稿の <div dir="ltr">1 行目<div>2 行目</div></div> や <div><h2>見出し</h2>本文</div> では、
    # 親の直下のテキストがどの段落にも入らず黙って消える。包んだ div は下の text_divs として 1 段落になる
    containers = [section] + [
        el for el in section.find_all(True)
        if el.name not in _BODY_BLOCKS and el.find(_PARAGRAPH_TAGS) is not None
    ]
    for container in containers:
        # p・li などの内側は、その要素ごと 1 段落として出るので包まない
        if _has_emitted_ancestor(container, article, names=tuple(_BODY_BLOCKS)):
            continue
        run: list = []
        for child in list(container.children) + [None]:
            if child is not None and not (
                isinstance(child, Tag) and (child.name in _PARAGRAPH_TAGS or child.find(_PARAGRAPH_TAGS) is not None)
            ):
                run.append(child)
                continue
            if any((n.get_text() if isinstance(n, Tag) else n).strip() for n in run):
                wrapper = Tag(name="div")
                run[0].insert_before(wrapper)
                for n in run:
                    wrapper.append(n)
            run = []


def _extract_article_paragraphs(article: BeautifulSoup) -> List[str]:
    paragraphs: List[str] = []
    for iframe in article.find_all("iframe"):
        src = iframe.get("src")
        if src:
            paragraphs.append(f"[Embed] {src}")
    for section in article.select("section.ipsType_richText"):
        _wrap_loose_runs(section, article)
    # 読者投稿などは本文を <p> でなく <div dir="ltr"> だけで書くことがある (niaj-legantoj/barry-friedman-r79)。
    # 本文 section 内で段落要素も div も含まない div は、<p> と同じく 1 段落として扱う
    text_divs = {
        id(div)
        for section in article.select("section.ipsType_richText")
        for div in section.find_all("div")
        if div.find(_PARAGRAPH_TAGS) is None
    }
    for node in article.find_all(_PARAGRAPH_TAGS):
        if node.name == "div" and id(node) not in text_divs:
            continue
        if _has_emitted_ancestor(node, article):
            continue
        text = base_clean_text(_inline_text(node))
        if not text:
            continue
        paragraphs.append(text)
    return paragraphs


def _extract_categories(soup: BeautifulSoup) -> List[str]:
    # パンくず末尾の記事自身の項目はリンクを持たない。題名の <br> 以降に副題がある記事ではパンくずが 1 行目だけで
    # 題名と一致しないため、リンクの無い項目を除く
    crumbs = [
        base_clean_text(li.get_text(" ", strip=True))
        for li in soup.select("nav.ipsBreadcrumb li")
        if li.find("a", href=True)
    ]
    filtered: List[str] = []
    skip_tokens = {"Hejmo", "Ĉiu aktivado", "Artikoloj", "Artikola fluo", ""}
    title_el = soup.find("h1", class_="ipsType_pageTitle")
    title_text = base_clean_text(title_el.get_text(" ", strip=True)) if title_el else None
    for crumb in crumbs:
        if crumb in skip_tokens:
            continue
        if title_text and crumb == title_text:
            continue
        if crumb not in filtered:
            filtered.append(crumb)
    return filtered


def _extract_title(soup: BeautifulSoup, url: str) -> str:
    title_el = soup.find("h1", class_="ipsType_pageTitle")
    if not title_el:
        return base_clean_text(url)
    # h1 は「題名 <br> 副題」の 2 行のことがある (og:title とパンくずは 1 行目だけ)。2 行目は副題のこともあれば
    # 1 行目の続き (「…Universala Kongreso <br>de Esperanto en Burno」) のこともあるので、記号は足さずに空白でつなぐ
    return base_clean_text(_inline_text(title_el))


def _extract_author(soup: BeautifulSoup) -> Optional[str]:
    author_box = soup.select_one(".gastautoraj-detaloj")
    if author_box:
        primary = base_clean_text(author_box.get_text("\n", strip=True).split("\n", 1)[0])
        # 共著では紹介欄に <strong>名前</strong> 紹介… が人数分並ぶ。ただし平易化の担当者も紹介欄に載るので、
        # 本文末尾の右寄せ署名で 2 つ目以降の <strong> に入る名前 (「Simpligis la artikolon <strong>X</strong>」) は除く
        signatures = [p for p in soup.select("section p[style*='text-align']") if "right" in p.get("style", "")]
        helpers = (
            {base_clean_text(st.get_text(" ", strip=True)) for st in signatures[-1].find_all("strong")[1:]}
            if signatures else set()
        )
        names = [primary] if primary else []
        # 区切りの " " が無いと <strong>名前 <em>('Rico')</em></strong> の空白が消える
        for st in author_box.find_all("strong")[1:]:
            name = base_clean_text(st.get_text(" ", strip=True))
            if name and name not in helpers and name not in names:
                names.append(name)
        return ", ".join(names)
    meta_author = soup.select_one(".ipsType_author")
    if meta_author:
        return base_clean_text(meta_author.get_text(" ", strip=True))
    return None


_AUDIO_EXTENSIONS = (".mp3", ".m4a", ".ogg", ".oga", ".opus", ".wav")


def _extract_audio_links(article: BeautifulSoup) -> List[str]:
    links = set()
    for el in article.find_all(["audio", "source", "a"]):
        href = (el.get("src") if el.name != "a" else el.get("href")) or ""
        href = href.strip()
        if not href:
            continue
        # URL に "mp3" を含むだけの外部サイト (vinilkosmo-mp3.com) や <video><source> は音声ではない
        if el.name == "audio":
            is_audio = True
        elif el.name == "source":
            parent = el.find_parent(["audio", "video", "picture"])
            is_audio = (parent is not None and parent.name == "audio") or el.get("type", "").lower().startswith("audio/")
        else:
            is_audio = urlsplit(href).path.lower().endswith(_AUDIO_EXTENSIONS)
        if is_audio:
            links.add(href)
    return sorted(links)


def fetch_article(url: str, cfg: ScrapeConfig, session: Optional[requests.Session] = None) -> Article:
    cfg.normalize()
    sess = session or _session(cfg)
    # サイトは連続アクセスで接続を切ることがある (RemoteDisconnected)。
    # _fetch_listing_page と同様に cfg.max_retries 回まで再試行する。
    attempt = 1
    while True:
        try:
            resp = sess.get(url, timeout=cfg.timeout_sec)
            resp.raise_for_status()
            break
        except requests.RequestException:
            if attempt >= cfg.max_retries:
                raise
            time.sleep(min(5.0 * attempt, 30.0))
            attempt += 1
    soup = BeautifulSoup(resp.content, "lxml")

    title = _extract_title(soup, url)

    article_el = soup.select_one("article.artikolo") or soup.select_one("article")
    if not article_el:
        raise ValueError(f"article content not found: {url}")
    # リアクション数 (「6」「1」等の数字だけの行) と filmetoj の難易度投票欄は
    # 記事要素の内側にあるため、本文として拾わないよう先に取り除く
    for widget in article_el.select(".ipsItemControls, .ipsItemControls_right, .ipsReact, .filmeto-taksado"):
        widget.decompose()
    # 練習問題への案内 <p class="edukado"> は閉じタグが無いことがあり、lxml では記事本体の
    # <section> がこの段落の中に入れ子になって本文が二重に抽出される。枠だけ外し、案内文は本文にしない
    for edukado in article_el.select("p.edukado"):
        edukado.unwrap()

    paragraphs = _extract_article_paragraphs(article_el)
    content_text = "\n\n".join(paragraphs)
    if not content_text:
        fallback = base_clean_text(_inline_text(article_el))
        content_text = fallback

    # JSON-LD (Article.datePublished) は全ページにある。filmetoj・loke・niaj-legantoj は見出しに <time> が無く、
    # ページ内の <time> はコメント欄 (.ipsComment) の投稿日時なので使わない
    published: Optional[datetime] = _extract_json_ld_date(soup)
    if not published:
        meta_time = next(
            (t for t in soup.find_all("time") if t.get("datetime") and not t.find_parent(class_=re.compile(r"ipsComment"))),
            None,
        )
        if meta_time:
            published = _parse_iso_datetime(meta_time["datetime"])
    if not published:
        cached = UEA_META.get(url, {}).get("published")
        if isinstance(cached, datetime):
            published = cached

    author = _extract_author(soup)
    categories = _extract_categories(soup) or None
    audio_links = _extract_audio_links(article_el) if cfg.include_audio_links else []

    return Article(
        url=url,
        title=title,
        published=published,
        content_text=content_text,
        author=author,
        categories=categories,
        audio_links=audio_links or None,
    )


__all__ = [
    "collect_urls",
    "fetch_article",
    "shared_session",
    "set_progress_callback",
]
