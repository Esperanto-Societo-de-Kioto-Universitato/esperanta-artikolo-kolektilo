"""
Streamlit アプリ（多言語対応）: エスペラント記事サイト（7媒体）を期間指定で収集し、各種フォーマットでダウンロード
起動:
    streamlit run streamlit_app.py
他言語版（薄いラッパ）:
    streamlit run streamlit_app_ko.py  # 韓国語
    streamlit run streamlit_app_eo.py  # エスペラント
"""
from __future__ import annotations

import io
import os
import sys
import time
import zipfile
import importlib.util
from datetime import date, timedelta, datetime
from typing import Dict, Any

from urllib.parse import urlparse

import pandas as pd
import requests
import streamlit as st

from retradio_lib import (
    FetchError,
    ScrapeConfig,
    URLCollectionError,
    collect_urls as retradio_collect_urls,
    fetch_article as retradio_fetch_article,
    _session as retradio_session,
    set_progress_callback as retradio_set_progress,
    to_markdown,
    to_text,
    to_csv,
    to_jsonl,
)


# ---------------------------------------------------------------------------
# i18n strings
# ---------------------------------------------------------------------------
I18N: Dict[str, Dict[str, str]] = {
    "ja": {
        "page_title": "エスペラント記事 期間収集ツール",
        "app_title": "🗞️ エスペラント記事 期間収集ツール（単独コア）",
        "select_site": "対象サイトを選択",
        "site_desc": "サイト説明",
        "base_url": "ベース URL",
        "start": "開始日",
        "end": "終了日",
        "method": "収集方法",
        "method_help": "サイトによって最適な方式が異なります。",
        "method_fixed_fmt": "収集方法: `{method}`（固定）",
        "throttle": "リクエスト間隔（秒）",
        "max_pages": "ページ送りの上限（0 = サイトごとの標準値）",
        "max_pages_help": (
            "0 のときはサイトごとの標準値を使います（El Popola Ĉinio 80、UEA Facila 400、"
            "その他はライブラリの既定でフィードのページ送りは最大 200）。REST での収集には影響しません。"
        ),
        "include_audio": "音声・埋め込みリンクも含める",
        "run": "収集を実行する",
        "language_select": "表示言語",
        "error_range": "終了日は開始日以降の日付にしてください。",
        "spinner_collect": "URL を収集中...",
        "error_collect_fmt": "URL 収集でエラーが発生しました: {exc}",
        "err_connect_fmt": "{host} に接続できません",
        "err_timeout_fmt": "{host} からの応答が時間切れになりました",
        "err_http_fmt": "HTTP {status} ({url})",
        "err_not_listing_fmt": "一覧・フィードとして読めない応答です ({url})",
        "candidates_fmt": "候補 URL: {n} 件",
        "counts_fmt": (
            "rest {rest_used}/{rest_initial}、feed {feed_used}/{feed_initial}、"
            "archive {archive_used}/{archive_initial}、重複除去 {dups} 件、"
            "期間外除外 {skipped} 件"
        ),
        "date_range_fmt": "推定公開日範囲: {earliest} ～ {latest}",
        "date_range_activity_note": "UEA Facila の候補の日付は活動ストリームの日時（読者コメントなどを含む）で、記事の公開日とは限りません。",
        "no_urls": "候補 URL が見つかりませんでした。期間や方法を変更して再度お試しください。",
        "no_urls_fixed": "候補 URL が見つかりませんでした。期間を変更して再度お試しください。",
        "progress_fetch": "本文を取得中...",
        "extracted_fmt": "抽出完了: {n} 本",
        "fetched_out_of_range_fmt": "本文の公開日が期間外のため除外: {n} 本",
        "failures": "取得できなかった URL",
        "no_arts": "期間内の記事は見つかりませんでした。",
        "no_arts_failed_fmt": "本文を 1 本も取得できませんでした（失敗 {n} 件）。「取得できなかった URL」を確認してください。",
        "no_arts_partial_failed_fmt": "期間内の本文はありませんでした（失敗 {n} 件）。「取得できなかった URL」を確認してください。",
        "col_published": "公開日",
        "col_title": "タイトル",
        "col_url": "URL",
        "col_author": "著者",
        "col_categories": "カテゴリ",
        "dl_md": "📄 Markdown をダウンロード",
        "dl_txt": "🗒️ TXT をダウンロード",
        "dl_csv": "🧾 CSV をダウンロード",
        "dl_jsonl": "🧰 JSONL をダウンロード",
        "dl_all": "📦 全フォーマットを一括ダウンロード",
        "params_changed": "入力内容が変更されています。最新の条件で再度「収集を実行する」を押してください。",
        "ready": "開始日・終了日とオプションを選び、「収集を実行する」を押してください。",
    },
    "ko": {
        "page_title": "에스페란토 기사 기간 수집 도구",
        "app_title": "🗞️ 에스페란토 기사 기간 수집 도구 (단일 코어)",
        "select_site": "대상 사이트를 선택하세요",
        "site_desc": "사이트 설명",
        "base_url": "기본 URL",
        "start": "시작일",
        "end": "종료일",
        "method": "수집 방법",
        "method_help": "사이트마다 최적의 수집 방식이 다릅니다.",
        "method_fixed_fmt": "수집 방법: `{method}` (고정)",
        "throttle": "요청 간 간격(초)",
        "max_pages": "페이지 넘김 상한 (0 = 사이트별 기본값)",
        "max_pages_help": (
            "0이면 사이트별 기본값을 사용합니다 (El Popola Ĉinio 80, UEA Facila 400, "
            "그 밖에는 라이브러리 기본값으로 피드 페이지 넘김 최대 200). REST 수집에는 영향이 없습니다."
        ),
        "include_audio": "오디오·임베드 링크도 포함",
        "run": "수집 실행하기",
        "language_select": "표시 언어",
        "error_range": "종료일은 시작일과 같거나 그 이후여야 합니다.",
        "spinner_collect": "URL을 수집하는 중입니다...",
        "error_collect_fmt": "URL 수집 중 오류가 발생했습니다: {exc}",
        "err_connect_fmt": "{host}에 연결할 수 없습니다",
        "err_timeout_fmt": "{host}의 응답 시간이 초과되었습니다",
        "err_http_fmt": "HTTP {status} ({url})",
        "err_not_listing_fmt": "목록이나 피드로 읽을 수 없는 응답입니다 ({url})",
        "candidates_fmt": "후보 URL: {n}건",
        "counts_fmt": (
            "REST {rest_used}/{rest_initial}, feed {feed_used}/{feed_initial}, "
            "archive {archive_used}/{archive_initial}, 중복 제거 {dups}, "
            "기간 외 제외 {skipped}"
        ),
        "date_range_fmt": "추정 공개일 범위: {earliest} ~ {latest}",
        "date_range_activity_note": "UEA Facila의 후보 날짜는 활동 스트림의 시각(독자 댓글 등 포함)이므로 기사 공개일과 다를 수 있습니다.",
        "no_urls": "후보 URL이 없습니다. 기간이나 방식을 바꿔 다시 시도하세요.",
        "no_urls_fixed": "후보 URL이 없습니다. 기간을 바꿔 다시 시도하세요.",
        "progress_fetch": "본문을 가져오는 중...",
        "extracted_fmt": "추출 완료: {n}건",
        "fetched_out_of_range_fmt": "본문 공개일이 기간 밖이라 제외: {n}건",
        "failures": "가져오지 못한 URL",
        "no_arts": "기간 내에 수집된 본문이 없습니다.",
        "no_arts_failed_fmt": "본문을 하나도 가져오지 못했습니다 (실패 {n}건). \"가져오지 못한 URL\"을 확인하세요.",
        "no_arts_partial_failed_fmt": "기간 내 본문이 없습니다 (실패 {n}건). \"가져오지 못한 URL\"을 확인하세요.",
        "col_published": "공개일",
        "col_title": "제목",
        "col_url": "URL",
        "col_author": "작성자",
        "col_categories": "카테고리",
        "dl_md": "📄 Markdown 다운로드",
        "dl_txt": "🗒️ TXT 다운로드",
        "dl_csv": "🧾 CSV 다운로드",
        "dl_jsonl": "🧰 JSONL 다운로드",
        "dl_all": "📦 모든 형식을 한 번에 다운로드",
        "params_changed": "입력 값이 바뀌었습니다. 최신 조건으로 다시 \"수집 실행하기\" 버튼을 눌러 주세요.",
        "ready": "시작일·종료일과 옵션을 고른 뒤 \"수집 실행하기\" 버튼을 눌러 주세요.",
    },
    "eo": {
        "page_title": "Ilo por kolekti artikolojn en Esperanto",
        "app_title": "🗞️ Ilo por kolekti artikolojn en Esperanto (unukerna)",
        "select_site": "Elektu celan retejon",
        "site_desc": "Priskribo de retejo",
        "base_url": "Baza URL",
        "start": "Komenca dato",
        "end": "Fina dato",
        "method": "Kolekta metodo",
        "method_help": "La plej taŭga metodo varias laŭ retejo.",
        "method_fixed_fmt": "Kolekta metodo: `{method}` (fiksa)",
        "throttle": "Intertempo inter petoj (sek.)",
        "max_pages": "Maks. paĝoj por paĝumo (0 = norma valoro de la retejo)",
        "max_pages_help": (
            "0 signifas la norman valoron de la retejo (El Popola Ĉinio 80, UEA Facila 400; "
            "ĉe la aliaj la defaŭlto de la biblioteko, t.e. paĝumo de fluo ĝis 200). Ne influas kolektadon per REST."
        ),
        "include_audio": "Inkluzivi ankaŭ sonajn/enkorpigitajn ligilojn",
        "run": "Lanĉi kolekton",
        "language_select": "Lingvo",
        "error_range": "La fina dato devas esti la sama aŭ posta ol la komenca dato.",
        "spinner_collect": "Kolektante URL-ojn...",
        "error_collect_fmt": "Eraro dum kolektado de URL-oj: {exc}",
        "err_connect_fmt": "Ne eblas konektiĝi al {host}",
        "err_timeout_fmt": "{host} ne respondis ene de la tempolimo",
        "err_http_fmt": "HTTP {status} ({url})",
        "err_not_listing_fmt": "La respondo ne legeblas kiel listo aŭ fluo ({url})",
        "candidates_fmt": "Kandidat-URL-oj: {n}",
        "counts_fmt": (
            "rest {rest_used}/{rest_initial}, feed {feed_used}/{feed_initial}, "
            "archive {archive_used}/{archive_initial}, forigitaj duplikatoj {dups}, "
            "ekskluditaj ekster periodo {skipped}"
        ),
        "date_range_fmt": "Proksimuma publikiga intervalo: {earliest} – {latest}",
        "date_range_activity_note": "Ĉe UEA Facila la kandidataj datoj venas el la aktiveca fluo (ankaŭ komentoj de legantoj), do ne nepre estas publikigaj datoj.",
        "no_urls": "Neniuj kandidat-URL-oj trovitaj. Ŝanĝu periodon aŭ metodon kaj reprovu.",
        "no_urls_fixed": "Neniuj kandidat-URL-oj trovitaj. Ŝanĝu la periodon kaj reprovu.",
        "progress_fetch": "Elŝutante ĉeftekstojn...",
        "extracted_fmt": "Pretigitaj artikoloj: {n}",
        "fetched_out_of_range_fmt": "Ekskluditaj pro publikiga dato ekster la periodo: {n}",
        "failures": "Ne akiritaj URL-oj",
        "no_arts": "Neniuj artikoloj trovitaj en la intervalo.",
        "no_arts_failed_fmt": "Neniu ĉefteksto akiriĝis (malsukcesoj: {n}). Vidu ‘Ne akiritaj URL-oj’.",
        "no_arts_partial_failed_fmt": "Neniu ĉefteksto en la periodo (malsukcesoj: {n}). Vidu ‘Ne akiritaj URL-oj’.",
        "col_published": "publikigita",
        "col_title": "titolo",
        "col_url": "URL",
        "col_author": "aŭtoro",
        "col_categories": "kategorioj",
        "dl_md": "📄 Elŝuti Markdown",
        "dl_txt": "🗒️ Elŝuti TXT",
        "dl_csv": "🧾 Elŝuti CSV",
        "dl_jsonl": "🧰 Elŝuti JSONL",
        "dl_all": "📦 Elŝuti ĉiujn formatojn kune",
        "params_changed": "La enigoj ŝanĝiĝis. Bonvolu re-premi ‘Lanĉi kolekton’ kun la novaj agordoj.",
        "ready": "Elektu datojn kaj opciojn, poste alklaku ‘Lanĉi kolekton’.",
    },
}


def _t(lang: str, key: str, **kwargs) -> str:
    text = I18N.get(lang, I18N["ja"]).get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


# ---------------------------------------------------------------------------
# 動的モジュールの読み込み
# ---------------------------------------------------------------------------
ROOT = os.path.abspath(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _describe_exc(lang: str, exc: BaseException) -> str:
    """ライブラリの例外 (メッセージは日本語) を表示言語で説明する。"""
    if isinstance(exc, URLCollectionError):
        return "; ".join(f"{route}: {_describe_exc(lang, err)}" for route, err in exc.errors)
    if isinstance(exc, FetchError):
        if exc.status is not None:
            return _t(lang, "err_http_fmt", status=exc.status, url=exc.url)
        return _t(lang, "err_not_listing_fmt", url=exc.url)
    if isinstance(exc, requests.exceptions.RequestException):
        req_url = getattr(getattr(exc, "request", None), "url", None) or ""
        host = urlparse(req_url).netloc or req_url or "?"
        # ConnectTimeout は ConnectionError でもあるので Timeout を先に見る
        if isinstance(exc, requests.exceptions.Timeout):
            return _t(lang, "err_timeout_fmt", host=host)
        if isinstance(exc, requests.exceptions.ConnectionError):
            return _t(lang, "err_connect_fmt", host=host)
        response = getattr(exc, "response", None)
        if response is not None:
            return _t(lang, "err_http_fmt", status=response.status_code, url=response.url)
    return f"{type(exc).__name__}: {exc}"


def load_module(module_name: str, relative_path: str):
    """アクセントや空白を含むディレクトリのモジュールを動的に読み込む。"""
    full_path = os.path.join(ROOT, relative_path)
    spec = importlib.util.spec_from_file_location(module_name, full_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Failed to load module {module_name} from {full_path}")
    module = importlib.util.module_from_spec(spec)
    # Register before exec for dataclass/type resolution
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module


DESCRIPTIONS: Dict[str, Dict[str, str]] = {
    "El Popola Ĉinio": {
        "ja": "中国政府系ポータルのエスペラント版。独自HTML構造のためカスタムスクレイパーを使用します。",
        "ko": "중국 정부계 포털의 에스페란토판입니다. 독자적인 HTML 구조 때문에 전용 스크레이퍼를 사용합니다.",
        "eo": "Esperantlingva versio de ĉina registara portalo. Pro propra HTML-strukturo ni uzas adaptitan skrapilon.",
    },
    "Global Voices en Esperanto": {
        "ja": "Global Voices のエスペラント版（WordPress）。REST API を利用できます。",
        "ko": "WordPress 기반의 Global Voices 에스페란토판입니다. REST API를 사용할 수 있습니다.",
        "eo": "Esperantlingva versio de Global Voices (WordPress). Eblas uzi la REST-API-on.",
    },
    "Monato": {
        "ja": "エスペラント月刊誌 MONATO の一般公開記事。サイト独自HTMLを解析します。",
        "ko": "에스페란토 월간지 MONATO의 공개 기사입니다. 사이트 고유 HTML을 파싱합니다.",
        "eo": "Publikaj artikoloj el la esperantlingva monata revuo MONATO. Ni analizas la propran HTML-strukturon de la retejo.",
    },
    "Scivolemo": {
        "ja": "科学読み物ブログ Scivolemo (WordPress.com)。2024 年以降ほぼ更新がなく、期間内の記事が 0 件のことが多い。",
        "ko": "과학 읽을거리 블로그 Scivolemo (WordPress.com). 2024년 이후 거의 업데이트가 없어 기간 내 글이 0건인 경우가 많습니다.",
        "eo": "Scienca blogo Scivolemo (WordPress.com). Ekde 2024 ĝi preskaŭ ne estas ĝisdatigata, do ofte estas 0 artikoloj en la periodo.",
    },
    "Pola Retradio": {
        "ja": "ポーランドのエスペラント放送『Pola Retradio』。REST/RSS/アーカイブ選択可。",
        "ko": "폴란드의 에스페란토 방송 'Pola Retradio'입니다. REST/RSS/아카이브 방식을 선택할 수 있습니다.",
        "eo": "La pola esperantlingva elsendservo 'Pola Retradio'. Elektebla inter REST/RSS/arkivo.",
    },
    "UEA Facila": {
        "ja": "UEA.facila.org の記事・動画。Invision Community ベースのカスタムスクレイパーを使用します。",
        "ko": "UEA.facila.org의 기사와 동영상입니다. Invision Community 기반이라 맞춤형 스크레이퍼를 사용합니다.",
        "eo": "Artikoloj kaj filmetoj el UEA.facila.org. Baziĝas sur Invision Community, tial ni uzas adaptitan skrapilon.",
    },
    "Libera Folio": {
        "ja": "エスペラント界のニュースサイト Libera Folio。2016年以降の WordPress 記事を REST API で収集（旧CMS 2003–2015 は対象外）。",
        "ko": "에스페란토계 뉴스 사이트 Libera Folio. 2016년 이후 WordPress 글만 REST API로 수집하며 구 CMS(2003–2015)는 제외됩니다.",
        "eo": "Novaĵretejo Libera Folio. Ni kolektas la WordPress-artikolojn ekde 2016 per REST (la malnova CMS 2003–2015 ne estas subtenata).",
    },
}


def _build_sources(lang: str):
    """サイトごとの設定辞書を構築して返す。"""
    elpopola_module = load_module("elpopola_lib", os.path.join("El Popola Ĉinio", "elpopola_lib.py"))
    from Monato.monato_lib import (
        collect_urls as monato_collect_urls,
        fetch_article as monato_fetch_article,
        shared_session as monato_session,
        set_progress_callback as monato_set_progress,
    )
    from Uea_Facila.uea_facila_lib import (
        collect_urls as uea_collect_urls,
        fetch_article as uea_fetch_article,
        shared_session as uea_session,
        set_progress_callback as uea_set_progress,
    )

    SOURCES: Dict[str, Dict[str, Any]] = {
        "El Popola Ĉinio": {
            "description": DESCRIPTIONS["El Popola Ĉinio"].get(lang, DESCRIPTIONS["El Popola Ĉinio"]["ja"]),
            "base_url": "http://esperanto.china.org.cn",
            "slug": "el_popola_cxinio",
            "collect": elpopola_module.collect_urls,
            "fetch": elpopola_module.fetch_article,
            "session": elpopola_module.shared_session,
            "set_progress": elpopola_module.set_progress_callback,
            "methods": ["feed"],
            "default_method": "feed",
            "supports_max_pages": True,
            "max_pages_default": 80,
            "include_audio_option": False,
            "throttle_default": 1.0,
            "min_date": date(2005, 1, 1),
            "source_label": "El Popola Ĉinio (esperanto.china.org.cn)",
        },
        "Global Voices en Esperanto": {
            "description": DESCRIPTIONS["Global Voices en Esperanto"].get(lang, DESCRIPTIONS["Global Voices en Esperanto"]["ja"]),
            "base_url": "https://eo.globalvoices.org",
            "slug": "global_voices_eo",
            "collect": retradio_collect_urls,
            "fetch": retradio_fetch_article,
            "session": retradio_session,
            "set_progress": retradio_set_progress,
            "methods": ["auto", "rest", "feed", "archive", "both"],
            "default_method": "auto",
            "supports_max_pages": True,
            "include_audio_option": False,
            "throttle_default": 0.5,
            "min_date": date(2006, 1, 1),
            "source_label": "Global Voices en Esperanto (eo.globalvoices.org)",
        },
        "Monato": {
            "description": DESCRIPTIONS["Monato"].get(lang, DESCRIPTIONS["Monato"]["ja"]),
            "base_url": "https://www.monato.be",
            "slug": "monato",
            "collect": monato_collect_urls,
            "fetch": monato_fetch_article,
            "session": monato_session,
            "set_progress": monato_set_progress,
            "methods": ["both", "feed", "archive"],
            "default_method": "both",
            "supports_max_pages": False,
            "include_audio_option": False,
            "throttle_default": 1.0,
            "min_date": date(2000, 1, 1),
            "source_label": "MONATO (monato.be)",
        },
        "Scivolemo": {
            "description": DESCRIPTIONS["Scivolemo"].get(lang, DESCRIPTIONS["Scivolemo"]["ja"]),
            "base_url": "https://scivolemo.wordpress.com",
            "slug": "scivolemo",
            "collect": retradio_collect_urls,
            "fetch": retradio_fetch_article,
            "session": retradio_session,
            "set_progress": retradio_set_progress,
            "methods": ["feed"],
            "default_method": "feed",
            "supports_max_pages": False,
            "include_audio_option": False,
            "throttle_default": 0.5,
            "min_date": date(2017, 1, 1),
            "source_label": "Scivolemo (scivolemo.wordpress.com)",
        },
        "Pola Retradio": {
            "description": DESCRIPTIONS["Pola Retradio"].get(lang, DESCRIPTIONS["Pola Retradio"]["ja"]),
            "base_url": "https://pola-retradio.org",
            "slug": "pola_retradio",
            "collect": retradio_collect_urls,
            "fetch": retradio_fetch_article,
            "session": retradio_session,
            "set_progress": retradio_set_progress,
            "methods": ["auto", "rest", "both", "feed", "archive"],
            "default_method": "auto",
            "supports_max_pages": True,
            "include_audio_option": True,
            "throttle_default": 1.0,
            "min_date": date(2011, 1, 1),
            "source_label": "Pola Retradio (pola-retradio.org)",
        },
        "UEA Facila": {
            "description": DESCRIPTIONS["UEA Facila"].get(lang, DESCRIPTIONS["UEA Facila"]["ja"]),
            "base_url": "https://uea.facila.org",
            "slug": "uea_facila",
            "collect": uea_collect_urls,
            "fetch": uea_fetch_article,
            "session": uea_session,
            "set_progress": uea_set_progress,
            "methods": ["feed"],
            "default_method": "feed",
            "supports_max_pages": True,
            "max_pages_default": 400,
            "include_audio_option": True,
            # 候補の日付は活動ストリームの日時 (コメントなど) で、公開日とは限らない
            "dates_from_activity": True,
            "throttle_default": 0.5,
            "min_date": date(2017, 1, 1),
            "source_label": "UEA Facila (uea.facila.org)",
        },
        "Libera Folio": {
            "description": DESCRIPTIONS["Libera Folio"].get(lang, DESCRIPTIONS["Libera Folio"]["ja"]),
            "base_url": "https://www.liberafolio.org",
            "slug": "libera_folio",
            "collect": retradio_collect_urls,
            "fetch": retradio_fetch_article,
            "session": retradio_session,
            "set_progress": retradio_set_progress,
            "methods": ["rest"],
            "default_method": "rest",
            "supports_max_pages": False,
            "include_audio_option": False,
            "throttle_default": 0.5,
            "min_date": date(2016, 1, 1),
            "source_label": "Libera Folio (liberafolio.org)",
        },
    }
    return SOURCES


def run_app(lang: str = "ja") -> None:
    """メイン UI（多言語）。lang は 'ja' | 'ko' | 'eo'。"""
    lang_order = ["ja", "ko", "eo"]
    lang_labels = {"ja": "日本語", "ko": "한국어", "eo": "Esperanto"}
    if st.session_state.get("lang") not in lang_order:
        st.session_state["lang"] = lang if lang in lang_order else "ja"
    current_lang = st.session_state["lang"]

    st.set_page_config(page_title=_t(current_lang, "page_title"), layout="wide")

    # streamlit 1.50 の slider は key があってもラベルと value でも識別され、表示言語を切り替えると既定値に戻る。
    # 言語・サイトを切り替える直前に値を控えて、次の描画で value に渡す。
    # 毎回控えると値を動かすたびに ID が変わり、続けて動かした入力が捨てられるので切替時だけにする
    def _keep_throttle() -> None:
        for key in list(st.session_state.keys()):
            if isinstance(key, str) and key.startswith("throttle_"):
                st.session_state["_throttle_keep_" + key[len("throttle_"):]] = st.session_state[key]

    qp_value = st.query_params.get("lang")
    if isinstance(qp_value, list):
        qp_lang = qp_value[0] if qp_value else None
    else:
        qp_lang = qp_value
    if qp_lang in lang_order and qp_lang != current_lang:
        st.session_state["lang"] = qp_lang
        st.rerun()
    current_lang = st.session_state["lang"]

    # 言語変更で st.rerun() すると、まだ描画していない下のウィジェットの状態が捨てられて入力が既定値に戻る。
    # コールバックで切り替え (スクリプト実行前に走る)、そのまま新しい言語で描画する
    def _on_lang_change() -> None:
        new_lang = st.session_state.get("lang_select")
        if new_lang in lang_order:
            _keep_throttle()
            st.session_state["lang"] = new_lang
            st.query_params["lang"] = new_lang

    if st.session_state.get("lang_select") != current_lang:
        st.session_state["lang_select"] = current_lang
    lang_col, _ = st.columns([1, 4])
    with lang_col:
        st.selectbox(
            _t(current_lang, "language_select"),
            options=lang_order,
            format_func=lambda code: lang_labels[code],
            key="lang_select",
            on_change=_on_lang_change,
        )

    st.title(_t(current_lang, "app_title"))

    SOURCES = _build_sources(current_lang)

    # key はラベル (表示言語で変わる) に依存させない。日付などはサイトごとに範囲が違うのでサイト別の key
    source_name = st.selectbox(
        _t(current_lang, "select_site"), list(SOURCES.keys()), key="site", on_change=_keep_throttle
    )
    source_cfg = SOURCES[source_name]

    st.markdown(f"**{_t(current_lang, 'site_desc')}**: {source_cfg['description']}")
    st.caption(f"{_t(current_lang, 'base_url')}: {source_cfg['base_url']}")

    min_supported = source_cfg.get("min_date", date(2000, 1, 1))
    today = date.today()
    default_start = max(min_supported, today - timedelta(days=14))

    col1, col2, col3 = st.columns(3)
    with col1:
        start = st.date_input(
            _t(current_lang, "start"),
            value=default_start,
            min_value=min_supported,
            max_value=today,
            key=f"start_{source_name}",
        )
    with col2:
        end = st.date_input(
            _t(current_lang, "end"),
            value=today,
            min_value=min_supported,
            max_value=today,
            key=f"end_{source_name}",
        )
    with col3:
        method_options = source_cfg["methods"]
        if len(method_options) == 1:
            method = method_options[0]
            st.write(_t(current_lang, "method_fixed_fmt", method=method))
        else:
            default_index = method_options.index(source_cfg["default_method"])
            method = st.selectbox(
                _t(current_lang, "method"),
                options=method_options,
                index=default_index,
                help=_t(current_lang, "method_help"),
                key=f"method_{source_name}",
            )

    # 控えた値 (_keep_throttle) を既定値として渡す
    throttle = st.slider(
        _t(current_lang, "throttle"),
        min_value=0.0,
        max_value=5.0,
        value=float(st.session_state.get(f"_throttle_keep_{source_name}", source_cfg["throttle_default"])),
        step=0.1,
        key=f"throttle_{source_name}",
    )

    max_pages_value = None
    if source_cfg.get("supports_max_pages", False):
        max_pages_input = st.number_input(
            _t(current_lang, "max_pages"),
            min_value=0,
            value=0,
            step=1,
            help=_t(current_lang, "max_pages_help"),
            key=f"maxpages_{source_name}",
        )
        # 0 はサイトごとの標準値。サイト設定に無ければ None でライブラリの既定に任せる
        max_pages_value = int(max_pages_input) or source_cfg.get("max_pages_default")

    include_audio = False
    if source_cfg.get("include_audio_option", False):
        include_audio = st.checkbox(_t(current_lang, "include_audio"), value=True, key=f"audio_{source_name}")

    current_signature = (
        source_name,
        start,
        end,
        method,
        float(throttle),
        max_pages_value,
        include_audio,
    )

    def render_results(state: Dict[str, Any]) -> None:
        cfg = state["cfg"]
        arts = state["arts"]

        if state.get("params_signature") and state["params_signature"] != current_signature:
            st.info(_t(current_lang, "params_changed"))

        if state["total"]:
            st.success(_t(current_lang, "candidates_fmt", n=state["total"]))
        else:
            st.info(_t(current_lang, "candidates_fmt", n=0))

        if state["has_counts"]:
            counts = state["counts"]
            st.caption(
                _t(
                    current_lang,
                    "counts_fmt",
                    rest_used=counts["rest_used"],
                    rest_initial=counts["rest_initial"],
                    feed_used=counts["feed_used"],
                    feed_initial=counts["feed_initial"],
                    archive_used=counts["archive_used"],
                    archive_initial=counts["archive_initial"],
                    dups=counts["duplicates_removed"],
                    skipped=counts["out_of_range_skipped"],
                )
            )

        if state["earliest_date"] and state["latest_date"]:
            st.caption(
                _t(
                    current_lang,
                    "date_range_fmt",
                    earliest=state["earliest_date"],
                    latest=state["latest_date"],
                )
            )
            if state.get("dates_from_activity"):
                st.caption(_t(current_lang, "date_range_activity_note"))

        if not state["total"]:
            st.warning(_t(current_lang, "no_urls_fixed" if state.get("fixed_method") else "no_urls"))
            return

        st.success(_t(current_lang, "extracted_fmt", n=len(arts)))

        if state.get("fetched_out_of_range"):
            st.caption(_t(current_lang, "fetched_out_of_range_fmt", n=state["fetched_out_of_range"]))

        if state["failures"]:
            with st.expander(_t(current_lang, "failures"), expanded=not arts):
                for url, exc in state["failures"]:
                    st.write(f"{url} ({_describe_exc(current_lang, exc)})")

        if not arts:
            if state["failures"] and state.get("fetched_out_of_range"):
                st.warning(_t(current_lang, "no_arts_partial_failed_fmt", n=len(state["failures"])))
            elif state["failures"]:
                st.warning(_t(current_lang, "no_arts_failed_fmt", n=len(state["failures"])))
            else:
                st.info(_t(current_lang, "no_arts"))
            return

        df = pd.DataFrame(
            [
                {
                    _t(current_lang, "col_published"): (a.published.strftime("%Y-%m-%d") if a.published else ""),
                    _t(current_lang, "col_title"): a.title,
                    _t(current_lang, "col_url"): a.url,
                    _t(current_lang, "col_author"): a.author or "",
                    _t(current_lang, "col_categories"): ", ".join(a.categories or []),
                }
                for a in arts
            ]
        )
        st.dataframe(df, width="stretch", hide_index=True)

        # コーパス (各 parallel_scraper.py の PREFIX) と同じ名前。正規表現で作ると Ĉ などが落ちる
        slug = state.get("slug") or "export"
        start_date = state["start"]
        end_date = state["end"]

        md = to_markdown(arts, cfg)
        txt = to_text(arts)
        csv_str = to_csv(arts)
        jsonl = to_jsonl(arts)

        st.download_button(
            _t(current_lang, "dl_md"),
            md,
            file_name=f"{slug}_{start_date}_{end_date}.md",
            mime="text/markdown",
        )
        st.download_button(
            _t(current_lang, "dl_txt"),
            txt,
            file_name=f"{slug}_{start_date}_{end_date}.txt",
            mime="text/plain",
        )
        st.download_button(
            _t(current_lang, "dl_csv"),
            csv_str,
            file_name=f"{slug}_{start_date}_{end_date}.csv",
            mime="text/csv",
        )
        st.download_button(
            _t(current_lang, "dl_jsonl"),
            jsonl,
            file_name=f"{slug}_{start_date}_{end_date}.jsonl",
            mime="application/json",
        )

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(f"{slug}_{start_date}_{end_date}.md", md.encode("utf-8"))
            archive.writestr(f"{slug}_{start_date}_{end_date}.txt", txt.encode("utf-8"))
            archive.writestr(f"{slug}_{start_date}_{end_date}.csv", csv_str.encode("utf-8"))
            archive.writestr(f"{slug}_{start_date}_{end_date}.jsonl", jsonl.encode("utf-8"))
        zip_buffer.seek(0)

        st.download_button(
            _t(current_lang, "dl_all"),
            zip_buffer.getvalue(),
            file_name=f"{slug}_{start_date}_{end_date}_all.zip",
            mime="application/zip",
        )

    run_clicked = st.button(_t(current_lang, "run"), type="primary", key="run")

    result_payload = st.session_state.get("last_result")

    if run_clicked:
        # エラーで止まったときに、前回 (別サイトのこともある) の結果が次の再描画で出ないようにする
        st.session_state.pop("last_result", None)
        if start > end:
            st.error(_t(current_lang, "error_range"))
            st.stop()

        cfg = ScrapeConfig(
            base_url=source_cfg["base_url"],
            start_date=start,
            end_date=end,
            method=method,
            throttle_sec=throttle,
            max_pages=max_pages_value,
            include_audio_links=include_audio,
            use_cache=True,
            source_label=source_cfg["source_label"],
        )

        source_cfg["set_progress"](None)

        try:
            with st.spinner(_t(current_lang, "spinner_collect")):
                result = source_cfg["collect"](cfg)
        except Exception as exc:  # noqa: BLE001
            st.error(_t(current_lang, "error_collect_fmt", exc=_describe_exc(current_lang, exc)))
            st.stop()

        urls = result.urls
        arts = []
        failures = []
        fetched_out_of_range = 0
        if urls:
            session = source_cfg["session"](cfg)
            # REST/feed で取得済みの本文や requests-cache の応答では通信しないので、実際に通信したときだけ待つ。
            # requests-cache はキャッシュ応答でも from_cache=True で response フックを呼ぶ
            http_used = []
            session.hooks["response"].append(
                lambda resp, *args, **kwargs: http_used.append(getattr(resp, "from_cache", False) is not True)
            )
            progress = st.progress(0.0, _t(current_lang, "progress_fetch"))
            for i, url in enumerate(urls, 1):
                http_used.clear()
                failed = False
                try:
                    article = source_cfg["fetch"](url, cfg, session)
                    if article.published and not (cfg.start_date <= article.published.date() <= cfg.end_date):
                        fetched_out_of_range += 1
                    else:
                        arts.append(article)
                except Exception as exc:  # noqa: BLE001
                    failures.append((url, exc))  # 表示言語を切り替えても説明を作り直せるよう例外のまま持つ
                    # 接続エラーでは応答が無くフックが呼ばれないので、失敗時は常に待つ
                    failed = True
                progress.progress(i / len(urls), f"{_t(current_lang, 'progress_fetch')} {i}/{len(urls)}")
                if failed or any(http_used):
                    time.sleep(cfg.throttle_sec)

            def sort_key(article):
                if article.published:
                    pub_naive = article.published.replace(tzinfo=None) if article.published.tzinfo else article.published
                    return (pub_naive, article.url)
                return (datetime.max, article.url)

            arts.sort(key=sort_key)

            progress.empty()

        counts = {
            "rest_used": getattr(result, "rest_used", 0),
            "rest_initial": getattr(result, "rest_initial", 0),
            "feed_used": getattr(result, "feed_used", 0),
            "feed_initial": getattr(result, "feed_initial", 0),
            "archive_used": getattr(result, "archive_used", 0),
            "archive_initial": getattr(result, "archive_initial", 0),
            "duplicates_removed": getattr(result, "duplicates_removed", 0),
            "out_of_range_skipped": getattr(result, "out_of_range_skipped", 0),
        }

        result_payload = {
            "cfg": cfg,
            "arts": arts,
            "failures": failures,
            "fetched_out_of_range": fetched_out_of_range,
            "has_counts": hasattr(result, "rest_used"),
            "counts": counts,
            "earliest_date": getattr(result, "earliest_date", None),
            "latest_date": getattr(result, "latest_date", None),
            "dates_from_activity": source_cfg.get("dates_from_activity", False),
            "total": result.total,
            "fixed_method": len(source_cfg["methods"]) == 1,
            "source_name": source_name,
            "slug": source_cfg["slug"],
            "start": start,
            "end": end,
            "params_signature": current_signature,
        }

        st.session_state["last_result"] = result_payload

    if result_payload:
        render_results(result_payload)
    else:
        st.info(_t(current_lang, "ready"))


if __name__ == "__main__":
    run_app("ja")
