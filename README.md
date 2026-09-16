# エスペラント記事収集ツール - Streamlit アプリケーション

## 概要

このプロジェクトは、エスペラント語で書かれた記事を複数のウェブサイトから期間指定で収集し、様々なフォーマット（Markdown、テキスト、CSV、JSONL）でダウンロードできるStreamlitベースのWebアプリケーションです。

### 対応サイト

このツールは、以下のエスペラント関連ウェブサイトからの記事収集をサポートしています：

1. **El Popola Ĉinio** (esperanto.china.org.cn) - 中国政府系ポータルのエスペラント版
2. **Global Voices en Esperanto** (eo.globalvoices.org) - 多言語市民メディアのエスペラント版
3. **Monato** (monato.be) - エスペラント月刊誌の公開記事
4. **Scivolemo** (scivolemo.wordpress.com) - 科学読み物ブログ Scivolemo (WordPress.com)。2024 年以降ほぼ更新がなく、期間内の記事が 0 件のことが多い
5. **Pola Retradio** (pola-retradio.org) - ポーランドのエスペラント放送 (アプリ・CLI では収集できるが、記事コーパスへの新規収集は方針により行っていない。「記事コレクションの運用記録」参照)
6. **UEA Facila** (uea.facila.org) - 世界エスペラント協会の記事・動画プラットフォーム
7. **Libera Folio** (liberafolio.org) - エスペラント界のニュースサイト

---

## Streamlit アプリケーション

### 3つのアプリケーションファイル

このプロジェクトには、3つの言語に対応したStreamlitアプリケーションが用意されています：

| ファイル名 | 対応言語 | 起動コマンド |
|-----------|---------|------------|
| [`streamlit_app.py`](streamlit_app.py) | 日本語（デフォルト） | `streamlit run streamlit_app.py` |
| [`streamlit_app_ko.py`](streamlit_app_ko.py) | 韓国語 | `streamlit run streamlit_app_ko.py` |
| [`streamlit_app_eo.py`](streamlit_app_eo.py) | エスペラント | `streamlit run streamlit_app_eo.py` |

**注意**: `streamlit_app_ko.py` と `streamlit_app_eo.py` は、`streamlit_app.py` の薄いラッパーです。メインロジックはすべて `streamlit_app.py` に実装されており、言語固有のラッパーはUIの表示言語を切り替えるだけです。

---

## 主要機能

### 1. 多言語対応UI

アプリケーションは3つの言語で完全にローカライズされています：

- **日本語 (ja)**: デフォルト言語
- **韓国語 (ko)**: 韓国語話者向け
- **エスペラント (eo)**: エスペラント話者向け

UIの言語は、アプリケーション内のセレクトボックスで動的に切り替えることができ、選択した言語はURLクエリパラメータ（`?lang=ja`など）に反映されます。

### 2. サイト選択

ドロップダウンメニューから収集対象のサイトを選択できます。各サイトには以下の情報が表示されます：

- **サイト説明**: サイトの概要と特徴
- **ベースURL**: サイトのベースアドレス
- **対応収集方法**: サイトごとに最適な収集方式

### 3. 期間指定

カレンダーUIで、記事の収集期間を指定できます：

- **開始日**: 収集開始日（各サイトで最小サポート日が異なります）
- **終了日**: 収集終了日（通常は今日まで）
- **サイト別の最小日付**:
  - El Popola Ĉinio: 2005年1月1日以降（ただしサイトの一覧 `node_*.htm` は各ノード 10 ページまでで、Plej Freŝaj でさかのぼれるのは約 11 か月。それより古い期間はトピック別ノードに載った記事しか見つからず不完全。このときは警告が出る）
  - Global Voices: 2006年1月1日以降
  - Monato: 2000年1月1日以降
  - Scivolemo: 2017年1月1日以降
  - Pola Retradio: 2011年1月1日以降
  - UEA Facila: 2017年1月1日以降
  - Libera Folio: 2016年1月1日以降（WordPress 版のみ対応。旧CMS 2003–2015 は取得対象外）

### 4. 収集方法の選択

サイトによって、以下の収集方法が選択可能です：

| 収集方法 | 説明 |
|---------|------|
| `auto` | REST API を試し、使えなければ Feed と Archive を併用（Global Voices・Pola Retradio） |
| `rest` | WordPress REST API を使用（高速・正確） |
| `feed` | RSS/Atom フィードから収集（Monato では Nova! ページのみ） |
| `archive` | 月別アーカイブページをクロール（Monato では publika 記事の ID 連番プローブ） |
| `both` | Feed と Archive を併用（Monato では Nova! ページ + ID 連番プローブ） |

アプリでサイトごとに選べる方法と既定値:

| サイト | 選べる方法 | 既定 |
|-------|-----------|------|
| Global Voices | `auto` / `rest` / `feed` / `archive` / `both` | `auto` |
| Pola Retradio | `auto` / `rest` / `both` / `feed` / `archive` | `auto` |
| Monato | `both` / `feed` / `archive` | `both` |
| Libera Folio | `rest` のみ | `rest` |
| Scivolemo | `feed` のみ | `feed` |
| El Popola Ĉinio | `feed` のみ（独自の node_*.htm ページ収集） | `feed` |
| UEA Facila | `feed` のみ（独自の活動ストリーム収集） | `feed` |

**注意**: Monato の年別インデックス（`/<年>/index.php?p`）は 2024 年以前だけ公開で、直近約 2 年分は購読者専用（HTTP 401）です。そのため直近の Monato は Nova! ページ + ID 連番プローブで集めます。`feed` を選ぶと Nova! ページだけになり、直近約 2 か月より前の記事を取りこぼします（「Monato 収集の仕様と対策」参照）。

### 5. 詳細オプション

#### リクエスト間隔（Throttle）

サーバーへの負荷を軽減するため、リクエスト間の待機時間を0.0〜5.0秒の範囲で設定できます。各サイトにはデフォルト値が設定されています：

- El Popola Ĉinio: 1.0秒
- Global Voices: 0.5秒
- Libera Folio: 0.5秒
- Monato: 1.0秒
- Scivolemo: 1.0秒
- Pola Retradio: 1.0秒
- UEA Facila: 0.5秒

#### ページ送りの上限

一覧ページ（フィード・月別アーカイブ・El Popola Ĉinio のノードページ・UEA Facila の活動ストリーム）を何ページまでたどるかを制限できます：

- **0 = サイトごとの標準値**: El Popola Ĉinio は 80 ページ（ノードごと）、UEA Facila は 400 ページ。Global Voices・Pola Retradio はライブラリの既定（フィードのページ送りは最大 200 ページ、月別アーカイブは上限なし）。無制限ではありません
- 1以上を指定すると、その回数までページをクロール（テストで少なくしたいときなど）
- 入力欄の初期値はどのサイトも 0（= 上記のサイトごとの標準値）
- REST API での収集（`rest`、および `auto` で REST が使えたとき）にはこの設定は効きません
- CLI（`parallel_scraper.py` の `--max-pages`）を省いたときはライブラリの既定（フィード最大 200 ページ、El Popola Ĉinio はノードごと 20 ページ、UEA Facila は 50 ページ）
- El Popola Ĉinio はサイト側の一覧が各ノード 10 ページまでなので、80 や 20 を指定しても実際にたどるのは 10 ページまで。Plej Freŝaj で約 11 か月分より古い期間は、トピック別ノードに載った記事しか見つからず不完全です（開始日がそれより古いと警告が出ます）

**対応サイト**: Global Voices、Pola Retradio、UEA Facila、El Popola Ĉinio（Libera Folio・Monato・Scivolemo では入力欄は出ません。Libera Folio は REST API のみ、Monato は独自の収集方式のため。Scivolemo は Global Voices などと同じ retradio_lib のフィード収集ですが、記事が少ないのでライブラリの既定〔フィード最大 200 ページ〕で固定です）

#### 音声・埋め込みリンクの取得

一部のサイトでは、記事内の音声ファイル（MP3など）や埋め込みコンテンツのリンクを抽出できます：

- **対応サイト**: Pola Retradio、UEA Facila

### 6. 収集実行

「収集を実行する」ボタンをクリックすると、以下の処理が実行されます：

1. **URL収集フェーズ**:
   - 指定された収集方法で記事URLを収集
   - 進捗状況がスピナーで表示
   - 収集統計（REST/Feed/Archive別の初期取得数と最終使用数、重複除去数、範囲外除外数）を表示

2. **本文取得フェーズ**:
   - 収集したURLから記事本文を取得
   - プログレスバーで進捗を表示（例: `本文を取得中... 15/42`）
   - 取得失敗したURLは別途記録

3. **結果表示**:
   - 取得成功した記事数を表示
   - 取得失敗したURLリスト（展開可能）
   - 記事一覧をDataFrame形式で表示（公開日、タイトル、URL、著者、カテゴリ）

### 7. エクスポート機能

収集した記事は、以下の4つのフォーマットで個別にダウンロードできます：

#### Markdown形式 (`.md`)

```markdown
---
source: "サイト名"
generated_at: "2025-10-31T12:34:56+00:00"
generator: "retradio_lib.py"
time_range: "2025-01-01 – 2025-01-31"
---


# 記事タイトル

**Published:** 2025-01-15

**URL:** https://example.com/article

**Author:** 著者名

**Categories:** カテゴリ1, カテゴリ2

**Audio:** https://example.com/audio1.mp3

記事本文...


---
```

**Published**・**Author**・**Categories**・**Audio** の行は、値があるときだけ出ます。記事が複数あるときは、`---` の後に空行を 1 行はさんで次の記事の `# 題名` が続きます。

#### テキスト形式 (`.txt`)

```
記事タイトル
[2025-01-15]
https://example.com/article

記事本文...

--------------------------------------------------------------------------------
```

#### CSV形式 (`.csv`)

| url | title | published | author | categories | audio_links |
|-----|-------|-----------|--------|------------|-------------|
| https://... | タイトル | 2025-01-15T10:00:00+01:00 | 著者 | cat1,cat2 | url1,url2 |

categories と audio_links は `,` でつないだだけの文字列です。カテゴリ名そのものにコンマを含むことがあり (El Popola Ĉinio の「Kulturo,Scienco kaj Sporto」)、CSV からは元の配列を復元できません。配列として使うときは JSONL を使ってください。

#### JSONL形式 (`.jsonl`)

```jsonl
{"url": "https://...", "title": "タイトル", "published": "2025-01-15 10:00:00+01:00", "content_text": "...", "author": "著者", "categories": ["cat1", "cat2"], "audio_links": null}
```

**published の書式**: JSONL は `str(datetime)` なので日付と時刻の間が空白、CSV は `isoformat()` なので `T` です。UTC オフセット（`+01:00` など）が付くかどうかは、サイトではなく日付の取り方で決まります。

- retradio_lib のサイト（Global Voices・Libera Folio・Pola Retradio・Scivolemo）: REST API と RSS フィードから取った日付には付きます。記事ページから取った日付も、ページに `<time datetime>` か `<meta property="article:published_time">` があれば時刻・オフセット付きで読みます（Libera Folio・Scivolemo・Global Voices）。これらが無いページ（Pola Retradio）の表示日付や、URL から推定した日付には付きません（例: `2025-01-15 00:00:00`）。そのため `feed`・`archive`・`both` で集めたときや、`auto` で REST が使えなかったときは、付くものと付かないものが混ざることがあります
- REST から取ったオフセットは、WordPress の `date` と `date_gmt` の差から求めたサイト本来の値です。Libera Folio と Pola Retradio はどちらも通年 UTC+1（WordPress の gmt_offset=1）なので、夏でも `+01:00` になります
- UEA Facila: 記事ページの JSON-LD `datePublished`（無ければコメント欄の外の `<time datetime>`、それも無ければ一覧の日付）を使い、オフセット付きです
- El Popola Ĉinio・Monato: 日付しか取らないので付きません
- Monato の published は印刷版の号の日付や初出日とは限りません。Nova! ページと ID プローブで集めた記事（現在のコーパスはすべてこれ）では、ページ末尾の「Lasta adapto de tiu ĉi paĝo」（ページの最終更新日）で、ID の位置より何か月も後の日付のことがあります。2024 年以前の年別インデックスで集めた記事では、号の月の 1 日です。合併号（例: 2024/08-09）は最初の月の号として扱います

現在のコーパスでは Global Voices・Libera Folio・Pola Retradio・UEA Facila に付き（Libera Folio・Pola Retradio はすべて `+01:00`）、El Popola Ĉinio・Monato には付いていません。日付が取れなかった記事は JSONL で `null`、CSV で空欄です。

#### 一括ダウンロード

「全フォーマットを一括ダウンロード」ボタンをクリックすると、上記4つのフォーマットすべてを含むZIPファイルがダウンロードされます。

---

## アーキテクチャ

### ファイル構成

```
.
├── streamlit_app.py           # メインアプリケーション（日本語）
├── streamlit_app_ko.py        # 韓国語ラッパー
├── streamlit_app_eo.py        # エスペラントラッパー
├── retradio_lib.py            # 共通スクレイピングライブラリ
├── requirements.txt           # Python依存パッケージ
├── gen_manifest.py            # 取得文書フォルダの MANIFEST.md を生成
├── sync_korpuso.sh            # 取得文書フォルダをコーパスリポジトリへ同期
├── prompt_輪読素材選定.md       # 記事収集・輪読素材選定のランブック（AI エージェント向け）
├── submit_all_sites_*.sh      # 全サイトのジョブを qsub で一括投入
├── jobs/                      # サイト×期間ごとの qsub ジョブ
├── logs/                      # qsub ジョブのログ（中身は git 管理外）
├── El Popola Ĉinio/
│   ├── elpopola_lib.py       # El Popola Ĉinio専用スクレイパー
│   └── parallel_scraper.py, scraper.py
├── Monato/
│   ├── monato_lib.py         # Monato専用スクレイパー
│   ├── backfill_publika_probe.py  # 任意の ID 帯を直接プローブ
│   └── parallel_scraper.py, scraper.py
├── Uea_Facila/
│   ├── uea_facila_lib.py     # UEA Facila専用スクレイパー
│   └── parallel_scraper.py, scraper.py
├── Global Voices en Esperanto/  # parallel_scraper.py, scraper.py（retradio_libを使用）
├── Scivolemo/                   # parallel_scraper.py, scraper.py（retradio_libを使用）
├── Pola Retradio/               # parallel_scraper.py, scraper.py（retradio_libを使用）
├── Libera Folio/                # parallel_scraper.py（retradio_libを使用）
├── cri_esperanto/               # CRI Esperanto（中国国際放送）用の別系統スクレイパー（アプリ非対応）
└── 取得文書ekde*/                # 収集した記事（git 管理外。コーパスリポジトリに同期）
```

各サイトの `parallel_scraper.py` は並列取得の CLI（Global Voices・Scivolemo・Pola Retradio・Libera Folio は期間を分割、Monato・El Popola Ĉinio・UEA Facila は URL を一括収集してから本文取得をワーカーで分担）、`scraper.py` は単体版です。日付引数 `--start`/`--end` は `YYYY-MM-DD` 形式だけを受け付けます。

### コア技術スタック

#### フロントエンド
- **Streamlit** (v1.50.0+): インタラクティブなWebアプリケーションフレームワーク
- **Pandas** (v2.2.2+): データ表示とDataFrame操作

#### バックエンド
- **Requests** (v2.31.0+): HTTP通信
- **Requests-Cache** (v1.2.0+): HTTPキャッシュ（オプション、12時間有効）
- **BeautifulSoup4** (v4.12.3+): HTML解析
- **lxml** (v5.2.2+): 高速HTMLパーサー
- **FeedParser** (v6.0.11+): RSS/Atom フィード解析
- **DateParser** (v1.2.0+): 多言語日付解析
- **python-dateutil** (v2.9.0+): 日付・時刻処理
- **tqdm** (v4.66.4+): CLIプログレスバー（CLI使用時）

### 主要コンポーネント

#### 1. `streamlit_app.py` - メインアプリケーション

**責務**:
- 多言語UI（日本語、韓国語、エスペラント）の提供
- ユーザー入力の受付と検証
- 7つのサイト設定の管理
- スクレイピングプロセスのオーケストレーション
- 結果の表示とエクスポート

**主要関数**:

- `run_app(lang: str)`: メインUIループ
  - 言語選択とクエリパラメータ同期
  - サイト選択と設定UI
  - 収集実行とプログレス表示
  - 結果レンダリング

- `_build_sources(lang: str)`: サイト設定辞書の構築
  - 各サイトの動的モジュール読み込み
  - サイト固有の設定（URL、収集方法、オプション）

- `render_results(state: Dict)`: 収集結果の表示
  - 統計情報の表示
  - DataFrameテーブルのレンダリング
  - ダウンロードボタンの生成

- `load_module(module_name: str, relative_path: str)`: 動的モジュール読み込み
  - アクセント文字や空白を含むディレクトリ名に対応
  - `importlib.util` を使用した安全な読み込み

**多言語化の実装**:

```python
I18N: Dict[str, Dict[str, str]] = {
    "ja": {"app_title": "🗞️ エスペラント記事 期間収集ツール", ...},
    "ko": {"app_title": "🗞️ 에스페란토 기사 기간 수집 도구", ...},
    "eo": {"app_title": "🗞️ Ilo por kolekti artikolojn en Esperanto", ...},
}

def _t(lang: str, key: str, **kwargs) -> str:
    """翻訳テキストを取得し、必要に応じてフォーマット"""
    text = I18N.get(lang, I18N["ja"]).get(key, key)
    return text.format(**kwargs) if kwargs else text
```

**セッション状態管理**:

```python
st.session_state["lang"]         # 現在の表示言語
st.session_state["last_result"]  # 最後の収集結果（再描画時に再利用）
```

#### 2. `retradio_lib.py` - 共通スクレイピングライブラリ

**責務**:
- WordPress系サイト（Global Voices、Scivolemo、Pola Retradio、Libera Folio）の汎用スクレイパー
- 3つの収集方法（REST API、Feed、Archive）の実装
- 記事本文の抽出とクリーニング
- エクスポート機能（Markdown、TXT、CSV、JSONL）

**主要データクラス**:

```python
@dataclass
class ScrapeConfig:
    base_url: str                      # サイトのベースURL
    start_date: date                   # 収集開始日
    end_date: date                     # 収集終了日
    throttle_sec: float                # リクエスト間隔（秒）
    max_pages: Optional[int]           # ページ送り上限（None は既定: フィード 200 ページまで・アーカイブは無制限。REST では不使用）
    method: str                        # "auto" | "rest" | "feed" | "archive" | "both"
    categories: Optional[List[str]]    # カテゴリフィルタ（現在未使用、将来の拡張用）
    timezone: str                      # タイムゾーン（デフォルト: "Europe/Warsaw"）
    use_cache: bool                    # HTTPキャッシュ使用（requests-cache）
    timeout_sec: int                   # HTTPタイムアウト（秒）
    max_retries: int                   # HTTPリトライ回数
    respect_robots: bool               # robots.txt遵守フラグ
    include_audio_links: bool          # 音声リンク取得
    source_label: Optional[str]        # エクスポート時のソースラベル
    feed_url_override: Optional[str]   # フィードURL上書き（自動検出を無効化）

@dataclass
class Article:
    url: str                           # 記事URL
    title: str                         # タイトル
    published: Optional[datetime]      # 公開日時
    content_text: str                  # 本文テキスト
    author: Optional[str]              # 著者
    categories: Optional[List[str]]    # カテゴリ
    audio_links: Optional[List[str]]   # 音声リンク

@dataclass
class URLCollectionResult:
    urls: List[str]                    # 収集したURL（重複除去・範囲フィルタ後）
    feed_initial: int                  # Feed収集の初期取得数
    archive_initial: int               # Archive収集の初期取得数
    rest_initial: int                  # REST API収集の初期取得数
    feed_used: int                     # Feed経由の最終使用数（重複除去・範囲フィルタ後）
    archive_used: int                  # Archive経由の最終使用数（重複除去・範囲フィルタ後）
    rest_used: int                     # REST API経由の最終使用数（重複除去・範囲フィルタ後）
    duplicates_removed: int            # 重複除去数
    out_of_range_skipped: int          # 範囲外除外数
    earliest_date: Optional[date]      # 最も古い公開日
    latest_date: Optional[date]        # 最も新しい公開日

    @property
    def total(self) -> int:            # 総URL数（len(urls)と同じ）
        return len(self.urls)
```

**主要関数**:

- `collect_urls(cfg: ScrapeConfig) -> URLCollectionResult`
  - 設定に基づき最適な収集方法を実行
  - 重複除去とソース優先度管理（REST > Feed > Archive）
  - 日付範囲フィルタリング

- `collect_from_rest(cfg: ScrapeConfig, s: Optional[requests.Session] = None) -> List[Tuple[str, Optional[datetime]]]`
  - WordPress REST API (`/wp-json/wp/v2/posts`) から記事一覧を取得
  - ページネーション対応（100件/ページ）
  - 埋め込みデータ（著者、カテゴリ）の取得
  - 日付範囲クエリによる高速フィルタリング

- `collect_from_feed(cfg: ScrapeConfig, s: Optional[requests.Session] = None) -> List[Tuple[str, Optional[datetime]]]`
  - RSS/Atom フィードの自動検出
  - フィードのページネーション対応
  - FeedEntryDataをキャッシュして後で再利用

- `collect_from_archives(cfg: ScrapeConfig, s: Optional[requests.Session] = None) -> List[Tuple[str, Optional[datetime]]]`
  - `/YYYY/MM/` 形式の月別アーカイブをクロール
  - 月ごとのページ送り対応
  - URLパターンマッチング（WordPress標準構造）

- `fetch_article(url: str, cfg: ScrapeConfig, s: Optional[requests.Session] = None) -> Article`
  - キャッシュからメタデータを取得（可能な場合）
  - HTMLページのスクレイピング
  - タイトル、公開日、本文、著者、カテゴリの抽出
  - 音声リンクの検出（オプション）

**日付解析**:

```python
def _parse_date_any(s: str) -> Optional[datetime]:
    """エスペラント、英語、ポーランド語などの日付を解析"""
    # DateParserで多言語対応
    return dateparser.parse(
        s,
        languages=["eo", "en", "pl", "de", "fr", "es", "it"],
        settings={"DATE_ORDER": "DMY"},
    )
```

**フィード自動検出**:

```python
def _discover_feed_url(cfg, s) -> Optional[str]:
    """
    1. <link rel="alternate" type="application/rss+xml">を検索
    2. フォールバックパス（/feed/, /?feed=rss2, など）を試行
    3. Content-Typeとファイル内容を検証
    """
```

#### 3. サイト固有スクレイパー

##### `elpopola_lib.py` - El Popola Ĉinio

**特徴**:
- 独自HTMLフォーマット（WordPress以前）
- `node_*.htm` ページからURLリストを取得
- 記事URL形式: `/YYYY-MM/DD/content_<id>.htm`

**主要関数**:
- `collect_urls(cfg)`: 複数の `node_*` ページからURLを収集
- `fetch_article(url, cfg, session)`: カスタムHTML構造から記事を抽出

##### `monato_lib.py` - Monato

**特徴**:
- 独自CMS（WordPress以前）
- 年別インデックス（`/YYYY/index.php?p`）は 2024 年以前だけ公開。直近約 2 年分は購読者専用（HTTP 401）なので、Nova! ページと publika 記事の ID 連番プローブ（`/publika/NNNNNNp.php` を降順に走査）で集める（「Monato 収集の仕様と対策」参照）
- セクション別の記事リスト

**主要関数**:
- `_collect_from_year(year, cfg, session)`: 年別インデックスから記事一覧を取得（公開されている年のみ）
- `_collect_from_current(cfg, session)`: Nova! ページ（直近約 2 か月の publika 記事）から記事一覧を取得
- `_collect_from_probe(cfg, session, anchor_ids, probe_floor)`: ID 連番プローブ（`archive` / `both` のときだけ）
- `collect_urls(cfg)`: 期間内の年別インデックスを走査し、読めない直近の年は Nova! ページ（`archive` / `both` ではプローブも）で補う。`feed` / `auto` は Nova! ページのみ
- `fetch_article(url, cfg, session)`: Monato固有のHTML構造を解析

##### `uea_facila_lib.py` - UEA Facila

**特徴**:
- Invision Community プラットフォーム
- 活動ストリーム (`/malkovri/`) からスクレイピング
- 記事とビデオを含む

**主要関数**:
- `_stream_page_urls(cfg, session)`: ストリームページをページネーション
- `collect_urls(cfg)`: 有効なコンテンツパスをフィルタリング
- `fetch_article(url, cfg, session)`: Invision Community のHTML構造を解析

---

## 使用方法

### インストール

1. **リポジトリのクローン**:
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. **依存パッケージのインストール**:
   ```bash
   pip install -r requirements.txt
   ```

### アプリケーションの起動

#### 日本語UI

```bash
streamlit run streamlit_app.py
```

#### 韓国語UI

```bash
streamlit run streamlit_app_ko.py
```

#### エスペラントUI

```bash
streamlit run streamlit_app_eo.py
```

アプリケーションが起動すると、ブラウザが自動的に開き（通常は `http://localhost:8501`）、UIが表示されます。

### 基本的なワークフロー

1. **言語選択**: UIの左上で表示言語を選択（日本語/한국어/Esperanto）

2. **サイト選択**: ドロップダウンメニューから収集対象サイトを選択

3. **期間設定**:
   - 開始日をカレンダーで選択
   - 終了日をカレンダーで選択

4. **収集方法の選択**（サイトによって選択肢と既定値が異なります。通常は既定のままでよい。「4. 収集方法の選択」の表参照）:
   - `auto`: REST API を優先し、使えなければ Feed+Archive（Global Voices・Pola Retradio のみ。両サイトの既定）
   - `rest`: REST API（高速。Libera Folio はこれのみ）
   - `feed`: RSS/Atomフィード（Monato では Nova! ページのみで、直近約 2 か月分しか取れない）
   - `archive`: 月別アーカイブ
   - `both`: FeedとArchiveを併用（Monato の既定）

5. **オプション設定**:
   - **リクエスト間隔**: サーバー負荷を考慮して調整（デフォルト推奨）
   - **ページ送り上限**: 必要に応じて制限（0 = サイトごとの標準値。無制限ではない）
   - **音声リンク取得**: 必要な場合はチェック（Pola Retradio、UEA Facila のみ）

6. **収集実行**: 「収集を実行する」ボタンをクリック

7. **結果確認**:
   - 収集統計を確認
   - 記事一覧テーブルをレビュー
   - 失敗URLがあれば展開して確認

8. **ダウンロード**:
   - 個別フォーマット（Markdown、TXT、CSV、JSONL）をダウンロード
   - または、一括ZIPダウンロード

### 使用例

#### 例1: Global Voicesから2025年1月の記事を収集

1. サイト選択: **Global Voices en Esperanto**
2. 開始日: `2025-01-01`
3. 終了日: `2025-01-31`
4. 収集方法: `auto`（既定。REST API を優先し、使えなければ Feed+Archive）
5. リクエスト間隔: `0.5` 秒（デフォルト）
6. 「収集を実行する」をクリック
7. 結果をMarkdown形式でダウンロード

#### 例2: Pola Retradioから音声リンク付きで最近2週間の記事を収集

1. サイト選択: **Pola Retradio**
2. 開始日: `2025-10-17`（今日の2週間前）
3. 終了日: `2025-10-31`（今日）
4. 収集方法: `auto`
5. リクエスト間隔: `1.0` 秒
6. **音声・埋め込みリンクも含める**: ✓（チェック）
7. 「収集を実行する」をクリック
8. JSONL形式でダウンロード（音声リンクを含む）

#### 例3: 複数フォーマットでバックアップ

1. 任意のサイトと期間を選択
2. 収集を実行
3. 「全フォーマットを一括ダウンロード」をクリック
4. ZIPファイルをダウンロード（.md, .txt, .csv, .jsonl を含む）

---

## 技術詳細

### HTMLコンテンツ抽出戦略

#### WordPress系サイト（retradio_lib）

```python
def _extract_main_content(soup: BeautifulSoup) -> str:
    """
    優先順位付きCSSセレクタで本文コンテナを検出:
    1. .entry-content
    2. .post-content
    3. article .entry-content / article .post-content
    4. .et_pb_post_content / .et_pb_text_inner (Divi/Elegant Themes)
    5. #left-area
    6. .post .entry / .entry-container .entry (Global Voices)
    7. article タグ (どれにも当たらなければ body。article か body に落ちて 200 字未満なら警告)
    """
    # 不要要素の除去: script, style, nav, header, footer, aside, 共有欄・関連記事・コメント欄,
    #   video/audio/iframe/object/embed の代替テキスト, Instagram 埋め込み (blockquote.instagram-media)
    # 子を文書順に見て、ブロック要素の境目ごとに段落にする (_iter_text_blocks。REST・フィードの本文断片も同じ)
    #   - <p> の外に直接書かれたテキストや div 直書きの本文、h1〜h6、写真の説明文 (figcaption) も段落になる
    #   - blockquote は中に段落があれば段落ごとに分け、無ければ全体を 1 段落
    #   - li は入れ子のリストを除いた部分を 1 段落にし、入れ子の項目は別段落
```

題名は `h1.entry-title` → `h1.post-title` → `article h1` → `h1` → `h2.post-title` の順で文字のある最初の要素、無ければ `og:title`、最後に `<title>` からサイト名を除いたもの。公開日は `<time datetime>` → `<meta property="article:published_time">` → Divi の日付表示の順に読みます。

#### El Popola Ĉinio

```python
# 最初の <table> を行の順番で読む (クラス名は使わない):
# - 1 行目: タイトル
# - 2 行目: 日付 YYYY-MM-DD (一覧ページから日付が取れなかったときだけ使う)
# - 4 行目の <td>: 本文 (他ページから貼り込まれた <title>/<style> は除く)
# - 著者: 専用の欄は無い。本文の末尾・冒頭の署名行 (Verkis: / Raportis: / Verkita de … / 冒頭の「de 名前」など) から取る
# - <table> が無いページ: #content などの汎用セレクタで読む
# categories は記事が載っている節 (node_*.htm) の一覧。Plej Freŝaj などの集約一覧は、ほかの節があれば除く
```

#### Monato

```python
# publika ページの構造:
# - h1 の前の <h3>: 欄 (Politiko など)      ┐ categories
# - <h2 class="tem">: 主題                  ┘
# - <h1>: タイトル
# - h1 以降の <p> と <h3>〜<h6>: 本文 (文書順)
# - 右寄せの <div style="text-align: right">: 署名 (author)
# - table.fina の「Lasta adapto de tiu ĉi paĝo: YYYY-MM-DD」: published (年別インデックス経由では号の月の 1 日)
```

#### UEA Facila

```python
# Invision Community構造:
# - .ipsType_pageTitle: タイトル
# - JSON-LD の datePublished: 公開日時 (無ければコメント欄 .ipsComment の外の time[datetime]、それも無ければ一覧の日付)
#   コメント欄の <time> はコメントの投稿日時なので公開日に使わない
# - article.artikolo (無ければ article): 本文
# - 著者: 紹介欄の名前 (共著者は ", " でつなぐ。本文末尾の右寄せ署名にある平易化の担当者は含めない)
```

### 日付解析の優先順位

1. **構造化データ**:
   - `<time datetime="...">` 属性
   - REST API の `date_gmt` / `date` フィールド
   - Feed の `<published>` / `<updated>` タグ

2. **URL推定**:
   - `/2025/01/15/article-slug/` → 2025-01-15

3. **テキスト解析**:
   - `DateParser` で多言語対応（エスペラント、英語、ポーランド語など）
   - エスペラント月名: "januaro", "februaro", "marto", ...

4. **フォールバック**:
   - 日付が取得できない場合は `None`
   - 範囲フィルタリング時に除外されない

### キャッシュ戦略

#### HTTP キャッシュ（`requests-cache`）

- **有効期間**: 12時間
- **バックエンド**: SQLite。保存先は OS の一時フォルダ (Linux では `/tmp/retradio_cache_<ユーザー名>.sqlite`)。環境変数 `RETRADIO_CACHE_DIR` で変更できる
- **対象**: 全てのHTTP GET リクエスト (並列実行時の本文取得ワーカーはキャッシュを使わない)
- **メリット**: 開発時の再実行が高速、サーバー負荷軽減
- **注意**: 作業フォルダ (クラスタでは共有ディスク) には置かないこと。別ノードで同時に走る各サイトのジョブが同じ SQLite を読み書きすると、ロック競合や破損読み出し (`database disk image is malformed`) でジョブが落ちる (2026-09-15 に UEA Facila で発生し、保存先を一時フォルダへ移した)

#### メタデータキャッシュ（インメモリ）

```python
_FEED_ENTRY_CACHE: Dict[str, FeedEntryData] = {}
```

- **用途**: Feed/REST APIから取得したメタデータを保持
- **利点**: `fetch_article()` 時にHTMLを再パースせずメタデータを再利用
- **スコープ**: 各 `collect_urls()` 呼び出しでクリア

### 重複除去とソース優先度

```python
SOURCE_PRIORITY = {"rest": 3, "feed": 2, "archive": 1}
```

同じURLが複数のソースから見つかった場合：

1. **ソース優先度**: REST > Feed > Archive
2. **日付優先**: 同じソースなら、より古い公開日を優先
3. **URL正規化**: 末尾スラッシュの有無を統一

### エラーハンドリング

#### リトライロジック

```python
def _get(s: requests.Session, url: str, cfg: ScrapeConfig) -> requests.Response:
    for i in range(cfg.max_retries):  # デフォルト3回
        try:
            resp = s.get(url, timeout=cfg.timeout_sec)
            if resp.status_code >= 500:
                time.sleep(min(cfg.throttle_sec * (i + 1), 5))
                continue
            return resp
        except Exception as e:
            last_exc = e
            time.sleep(min(cfg.throttle_sec * (i + 1), 5))
    raise last_exc
```

#### Streamlit UI でのエラー表示

```python
try:
    result = source_cfg["collect"](cfg)
except Exception as exc:
    # ライブラリの例外は日本語なので、FetchError・URLCollectionError・requests の例外を表示言語で説明し直す
    st.error(_t(current_lang, "error_collect_fmt", exc=_describe_exc(current_lang, exc)))
    st.stop()
```

### プログレス通知

```python
def set_progress_callback(func: Optional[Callable[[str], None]]) -> None:
    """進捗通知コールバックを登録"""

def _progress(msg: str) -> None:
    """登録されたコールバックに進捗を通知"""
    if _PROGRESS_CB:
        _PROGRESS_CB(msg)
```

Streamlitアプリでは、このコールバックを使用してリアルタイムに進捗を表示できます（現在の実装ではプログレスバーを使用）。

---

## カスタマイズとメンテナンス

### 新しいサイトの追加

新しいエスペラントサイトを追加する手順：

1. **サイト固有ライブラリの作成**（必要な場合）:

   ```python
   # new_site/new_site_lib.py
   from retradio_lib import Article, ScrapeConfig, URLCollectionResult

   def collect_urls(cfg: ScrapeConfig) -> URLCollectionResult:
       # URL収集ロジック
       pass

   def fetch_article(url: str, cfg: ScrapeConfig, session) -> Article:
       # 記事抽出ロジック
       pass

   def shared_session(cfg: ScrapeConfig):
       # セッション作成
       pass

   def set_progress_callback(func):
       # プログレスコールバック設定
       pass
   ```

2. **`streamlit_app.py` の `_build_sources()` に追加**:

   ```python
   def _build_sources(lang: str):
       # 既存のインポート...

       from new_site.new_site_lib import (
           collect_urls as new_collect_urls,
           fetch_article as new_fetch_article,
           shared_session as new_session,
           set_progress_callback as new_set_progress,
       )

       SOURCES["New Site Name"] = {
           "description": DESCRIPTIONS["New Site Name"].get(lang, "..."),
           "base_url": "https://newsite.example.com",
           "collect": new_collect_urls,
           "fetch": new_fetch_article,
           "session": new_session,
           "set_progress": new_set_progress,
           "methods": ["feed"],  # 対応する収集方法
           "default_method": "feed",
           "supports_max_pages": True,
           "include_audio_option": False,
           "throttle_default": 0.5,
           "min_date": date(2020, 1, 1),
           "source_label": "New Site Name (newsite.example.com)",
       }

       return SOURCES
   ```

3. **多言語説明の追加**:

   ```python
   DESCRIPTIONS: Dict[str, Dict[str, str]] = {
       "New Site Name": {
           "ja": "日本語の説明",
           "ko": "韓国語の説明",
           "eo": "エスペラント語の説明",
       },
       # ...
   }
   ```

### UI文言の変更

`streamlit_app.py` の `I18N` 辞書を編集：

```python
I18N: Dict[str, Dict[str, str]] = {
    "ja": {
        "app_title": "新しいタイトル",
        "new_key": "新しい文言",
        # ...
    },
    "ko": {
        "app_title": "새 제목",
        "new_key": "새 문구",
    },
    "eo": {
        "app_title": "Nova titolo",
        "new_key": "Nova frazo",
    },
}
```

### デフォルト設定の変更

各サイトのデフォルト値を調整：

```python
"throttle_default": 1.5,  # リクエスト間隔を1.5秒に
"min_date": date(2015, 1, 1),  # 最小日付を2015年に
```

---

## トラブルシューティング

### よくある問題と解決策

#### 1. URLが全く収集されない

**症状**: 「候補 URL: 0 件」と表示される

**原因**:
- 指定期間に記事が存在しない
- 収集方法が不適切
- サイトの構造変更

**解決策**:
- 期間を広げる（例: 過去3ヶ月）
- 収集方法を変更（`auto` → `feed` → `archive`）
- サイトがアクセス可能か確認（ブラウザで直接開く）

#### 2. 一部の記事が取得できない

**症状**: 「取得できなかった URL」リストに複数のURLが表示される

**原因**:
- サーバーの一時的なエラー
- タイムアウト
- ページ構造が例外的

**解決策**:
- リクエスト間隔を増やす（0.5秒 → 1.5秒）
- タイムアウト設定を増やす（`ScrapeConfig.timeout_sec`）
- 失敗URLを手動で確認

#### 3. Streamlitが起動しない

**症状**: `streamlit: command not found` エラー

**原因**: Streamlitがインストールされていない

**解決策**:
```bash
pip install -r requirements.txt
```

#### 4. モジュールのインポートエラー

**症状**: `ModuleNotFoundError: No module named 'retradio_lib'`

**原因**: Pythonのパスが正しく設定されていない

**解決策**:
- プロジェクトのルートディレクトリで実行していることを確認
- `sys.path` に追加（`streamlit_app.py` は自動的に行います）

#### 5. 日付範囲が正しく機能しない

**症状**: 範囲外の記事が含まれる、または範囲内の記事が除外される

**原因**:
- 記事の日付が正しく解析されていない
- タイムゾーンの問題

**解決策**:
- 収集後の記事リストで公開日を確認
- タイムゾーン設定を確認（`ScrapeConfig.timezone`）
- デバッグログを有効化（`logging.basicConfig(level=logging.DEBUG)`）

#### 6. キャッシュが古い

**症状**: 最新の記事が表示されない

**原因**: HTTP キャッシュが有効（12時間）

**解決策**:
```bash
# キャッシュファイルを削除 (RETRADIO_CACHE_DIR を指定している場合はそのフォルダ内)
rm -f /tmp/retradio_cache_$(whoami).sqlite*
```

または、`ScrapeConfig.use_cache = False` に設定

---

## パフォーマンスとベストプラクティス

### 最適な収集方法の選択

| サイト | 推奨方法 | 理由 |
|-------|---------|------|
| Global Voices | `auto`（既定） | REST API を優先し、使えなければ Feed+Archive に切り替わる（CLI・定期取得ジョブと同じ） |
| Pola Retradio | `auto`（既定） | REST APIが利用可能（自動選択が最適）。記事コーパスへの新規収集は方針により行っていない |
| Libera Folio | `rest`（固定） | WordPress REST API のみ対応（2016年以降の WordPress 版） |
| Scivolemo | `feed`（固定） | RSSのみ提供 |
| Monato | `both`（既定） | 年別インデックス（2024年以前のみ公開）+ Nova! ページ + ID 連番プローブ。`feed` は Nova! ページのみで直近約2か月分しか取れない（「Monato 収集の仕様と対策」参照） |
| El Popola Ĉinio | `feed`（固定） | 独自実装（node_*.htmページから収集） |
| UEA Facila | `feed`（固定） | Invision Community固有の活動ストリームから収集 |

### サーバー負荷の軽減

1. **適切なリクエスト間隔**:
   - 小規模サイト（Scivolemo、Monato）: 1.0秒以上
   - 大規模サイト（Global Voices、Pola Retradio）: 0.5秒以上

2. **ページ送り上限の設定**:
   - テスト時: `max_pages=2`（最初の2ページのみ）
   - 本番: アプリでは `0`（サイトごとの標準値）、CLI では `--max-pages` を省略（ライブラリの既定）

3. **キャッシュの活用**:
   - 開発・デバッグ時は `use_cache=True`（デフォルト）
   - 本番環境では定期的にキャッシュをクリア

### 大量記事の処理

長期間（1年以上）の記事を収集する場合：

1. **期間を分割**:
   - 例: 2023年全体 → 2023年1-6月、2023年7-12月

2. **収集方法の選択**:
   - REST API（`rest`）が最も効率的
   - アーカイブ（`archive`）は月別に分かれるため、長期間に適している

3. **タイムアウトとリトライ**:
   - `timeout_sec` を増やす（30秒 → 60秒）
   - `max_retries` を増やす（3回 → 5回）

### メモリ管理

大量の記事を処理する際のメモリ使用量を抑える方法：

1. **ストリーミング処理**:
   - 記事を一度にメモリに保持せず、逐次処理
   - 現在の実装はすべてメモリに保持するため、超大量データには注意

2. **キャッシュのクリア**:
   ```python
   _FEED_ENTRY_CACHE.clear()  # メタデータキャッシュをクリア
   ```

---

## ライセンスと著作権

### ツール本体

このツールのソースコードは MIT License で配布されています (`LICENSE` 参照)。

### 収集した記事のライセンス

収集した記事のコンテンツは、各サイトの著作権とライセンスに従います：

- **Global Voices**: CC BY 3.0
- **Pola Retradio**: サイトのライセンスを確認
- **Monato**: 有料購読誌の公開記事（利用規約を確認）
- **El Popola Ĉinio**: 政府系メディア（利用規約を確認）
- **Scivolemo**: ブログ記事（著者に確認）
- **UEA Facila**: UEA のライセンスを確認
- **Libera Folio**: 記事に別の表示がなければ CC BY 4.0（サイトのフッターの表示による。2026-09-16 確認）

**重要**: 収集した記事を再配布または商用利用する場合は、必ず各サイトのライセンスと利用規約を確認してください。

### リポジトリの方針 (2026-09 更新)

- コードと収集した記事本文を別のリポジトリで管理する。記事本文 (`取得文書*/`) はこのリポジトリには置かず (`.gitignore` で除外)、コーパスリポジトリ [`esperanta-artikolo-korpuso`](https://github.com/Esperanto-Societo-de-Kioto-Universitato/esperanta-artikolo-korpuso) に保管する (取得後に `./sync_korpuso.sh` で同期)。
- korpuso は当初プライベートで運用したが、2026-09 から所有者の判断で**公開**にしている。各記事の著作権は掲載サイト・著者に帰属し、各記事に出典 URL を記載している (上記「収集した記事のライセンス」参照)。
- 各取得フォルダの内容 (サイト×月の記事数・既知の注意点) はフォルダ内の `MANIFEST.md` (`gen_manifest.py` で生成) に記録され、korpuso 側にも同梱される。
- 2026-03-04 のコミットで入れた旧コーパスの記事ファイルがこのリポジトリの git 履歴に残っているが、同じ内容を korpuso で公開しているため、履歴を書き換える必要はない。

---

## 開発者向け情報

### コードスタイル

- **PEP 8** に準拠
- 型ヒント（Type Hints）の使用を推奨
- Docstring（`"""`）で関数の説明を記述

### テスト

現在、自動テストは実装されていません。手動テストの手順：

1. 各サイトで短期間（1週間）のテストを実行
2. 収集数が予想と一致することを確認
3. エクスポートされたファイルの内容を検証
4. エラーログを確認

### デバッグモード

詳細なログを表示するには：

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

## 貢献とサポート

### バグ報告

問題を発見した場合は、以下の情報を含めてIssueを作成してください：

- 使用環境（OS、Pythonバージョン、ブラウザ）
- 再現手順
- エラーメッセージまたはスクリーンショット
- 期待される動作

### 機能リクエスト

新機能の提案は歓迎します。以下を含めてください：

- 機能の説明
- ユースケース
- 期待される動作

### プルリクエスト

コードの改善を提案する場合：

1. フォークしてブランチを作成
2. コードを変更
3. テスト（手動でも可）
4. プルリクエストを作成（変更内容の説明を含む）

---

## 謝辞

このプロジェクトは、エスペラントコミュニティの情報アクセスを向上させるために開発されました。以下のライブラリとツールに感謝します：

- **Streamlit**: 直感的なWebアプリケーションフレームワーク
- **BeautifulSoup4**: 柔軟なHTML解析
- **Requests**: シンプルで強力なHTTPライブラリ
- **FeedParser**: RSS/Atom フィード解析
- **DateParser**: 多言語日付解析

そして、エスペラントのコンテンツを提供してくださっている全てのサイト運営者と著者の皆様に感謝します。

---

## 記事コレクションの運用記録

### コレクションの状態 (2026-09-17 時点)

| フォルダ | 期間 | 記事数 | 備考 |
|---|---|---|---|
| `取得文書ekde20260303/` | 2025-03-03〜2026-03-03 | 1202 | 7サイト。Monato の欠落 (2025-03〜12ほか) は 2026-08-13 に ID プローブで補完済み (21→195本)。2026-09-15 に本文の雑音を除去し、取りこぼしていた Global Voices 1 本を追加。2026-09-16 に取りこぼしていた UEA Facila 1 本を追加。2026-09-17 に一覧の 10 ページ制限で取りこぼしていた El Popola Ĉinio 4 本 (2025-03) を追加し、公開日が期間外 (2025-01-14) と分かった UEA Facila 1 本 (r79) を除外 |
| `取得文書ekde20260401/` | 2026-03-04〜2026-08-13 | 368 | 6サイト (Pola Retradio 除外)。2026年3月ギャップも全サイト補完済み。UEA Facila の取得失敗 6 本は 2026-08-23 に回収。前フォルダと重複していた UEA Facila 3 本 (コメント日時を公開日と取り違えて 2026-08 に入っていたもの) は 2026-09-15 に除去 (369→366)。2026-09-17 に、ID の位置より日付が数か月遅い Monato 2 本 (013752・013837) を追加 (366→368) |
| `取得文書ekde20260814/` | 2026-08-14〜2026-09-14 | 86 | 6サイト (Pola Retradio 除外)。Global Voices の更新再開分 4 本を含む |

- 3 フォルダ計 **1656 本**。2025-03-03〜2026-09-14 が切れ目なく、フォルダ間で同じ URL は重複しない
- サイト別の内訳: El Popola Ĉinio 712、Pola Retradio 335、Monato 301、UEA Facila 151、Libera Folio 120、Global Voices 37 (Scivolemo は期間内 0 本)
- 著者欄が埋まっているのは、El Popola Ĉinio 242/712 本 (署名の無い記事は空欄)、Global Voices 36/37 本 (空欄は共有アカウント名で投稿された 1 本)、UEA Facila 55/151 本。Libera Folio は全記事が共有アカウントなので空欄
- 輪読候補リスト: `取得文書ekde20260814/rondolegado_kandidatoj_202609.md` (3 フォルダから選んだ 50 本。日本語タイトル・短い紹介・語数・難しさつき)。各記事の抽出 md は `rondolegado_kandidatoj_202609/` (エスペラントの題名と本文。語注・著者紹介を含み、朗読案内・写真説明・クレジット・http(s) で始まる URL は除く)、ルビ付き HTML の Netlify Drop 用フォルダは `rondolegado_kandidatoj_202609_ruby/`
- 輪読候補一式の再生成手順は `tools/rondolegado/README.md`
- 詳細は各フォルダ内の `MANIFEST.md` を参照。フォルダを再取得・変更したら `python gen_manifest.py <フォルダ>` で再生成し、`./sync_korpuso.sh` で korpuso に反映すること。備考（`## 備考` 節）の原本は MANIFEST.md 自身で、`--notes` を省くと既存の備考をそのまま引き継ぐ。備考を書き換えるときは、節の本文を別ファイルに切り出して編集し `--notes <備考md>` で渡す

### Monato 収集の仕様と対策 (重要)

monato.be の年別インデックス `/<年>/index.php?p` は **2024年以前は公開、直近約2年分は購読者専用 (HTTP 401)**。このため従来の収集 (Nova! ページへのフォールバック) では、期間を何か月指定しても**直近約2か月の publika 記事しか取れない**。

対策として `Monato/parallel_scraper.py` に ID 連番プローブ (`/publika/NNNNNNp.php` を降順走査) を実装済み:

- `--method both`(**既定値**): Nova! ページ + プローブ。定期取得はこれでよい (Streamlit アプリも v1.3.0 から `both` が既定)
- `--method archive`: 同上 (過去ギャップの穴埋め用途)
- `--method feed`: 旧来どおり Nova! のみ (取りこぼしの可能性がある場合は警告が出る)
- プローブは安全上限 `PROBE_MAX_PAGES=500` ページ、公開年インデックスで取得済みの範囲には踏み込まない。日付のないページ (一部の書評) は published 空欄のまま `_unknown` グループに出るので人手で確認する
- 任意の ID 帯を直接指定したい場合は `Monato/backfill_publika_probe.py` を使う
- publika の ID は投稿時に振られるが、ページの日付 (Lasta adapto) は ID の位置より数か月遅れることがある (例: 013648 は近くの ID が 2025-03 なのに 2025-10-09、013752 は 2026-03-16)。`--method both` のプローブは Nova! 帯域の下端から `PROBE_MIN_SPAN=300` ID 下までは必ず走査するが、それより古い ID で日付の遅い記事は取れない。このため定期取得とは別に `backfill_publika_probe.py` で ID 帯を走査する (下記「定期取得の手順」)。プローブが約 300 ページ増えるので、1 回の実行は 1 秒間隔で約 5 分長くなる

2026-08-13 時点で既知の Monato 欠落はすべて補完済み (`取得文書ekde20260303` の 2025-03〜2026-02 は ID 13550〜13872 のプローブで回収。詳細は同フォルダの MANIFEST.md)。2026-09-17 に、ID はこの帯の中にあるが日付が遅く、どのフォルダにも入っていなかった 013752 (2026-03-16) と 013837 (2026-04-03) を `取得文書ekde20260401` に追加した。なお 2024 年以前の publika 記事にも Nova! 非掲載の日付なしページが存在することがプローブで判明している (ID 13587, 13615, 13621, 13646, 13659 など) — 2024 年以前を再整備する場合は年別インデックスとプローブの併用が必要。

### 定期取得の手順

1. 「完成YYMMDD」フォルダをコピーして作業フォルダを作る
2. `jobs/qsub_<site>_<start>_<end>_8w.sh` を日付を変えて複製する (8ワーカー並列が最速。例: `jobs/qsub_*_20260701_20260914_8w.sh`)。開始日は前回の終了日の約1か月半前にして重複区間を設け、出力先は `取得文書ekde<新期間の開始日>_staging` にする (前回実行後に遅れて公開された記事の回収と、既存記事との突合のため)
3. `qsub` で投入する。完了待ちはジョブ ID で行う (`qstat -j <ID>`。`qstat` の一覧はジョブ名を 10 文字で切るので、名前で判定しない)
4. `logs/` の `.err` を確認する。サイトに接続できずに落ちたジョブ (2026-09-15 の Global Voices の `No route to host` など) は、時間をおいて再投入するか、ログインノードで同じコマンドを実行する
5. staging の記事を既存フォルダと URL 単位で突合し、新期間分を `取得文書ekde<開始日>/` に、既存フォルダの期間に入る未収録の記事はそのフォルダに振り分ける。重複区間で本文が変わっていればサイト側の修正なので、修正後の本文に更新してよい
6. Monato: 収集の間隔は 2 か月以内にする (Nova! ページに載るのは直近約 2 か月分だけ)。あわせて毎回 `Monato/backfill_publika_probe.py` で、今回の最大 ID から約 300 ID 下までを、`--start`/`--end` をコーパス全体 (例: 2025-03-03〜今回の終了日) にして走査する。`--existing` に渡せるのは 1 フォルダだけで、ほかのフォルダにある記事も新規として出力に入るので、出力とログの「[SKIP] 期間外」を既存 3 フォルダと URL で突き合わせ、未収録の記事だけを日付に当たるフォルダの月に入れる。間隔が 2 か月を超えたときは、前回走査した帯の下端から今回の最大 ID までを同じように走査する
   ```bash
   python Monato/backfill_publika_probe.py --id-start <最大ID-300> --id-end <最大ID> \
       --start 2025-03-03 --end <今回の終了日> --workers 1 --throttle 1.5 \
       --existing 取得文書ekde<最新のフォルダ> --out <staging フォルダ>
   ```
7. 記事を入れたフォルダごとに `python gen_manifest.py <フォルダ>` でマニフェストを作り直し（既存フォルダの備考は引き継がれる。新しいフォルダの備考や追記は `--notes <備考md>` で渡す）、`./sync_korpuso.sh` で korpuso に反映する

---

## 変更履歴

### v1.3.3 (2026年9月17日)

第 2 回監査 (2026-09-16) の指摘を反映。

- **retradio_lib (本文の段落分け)**: v1.3.2 で「REST とページで本文が一致」としたのは、複数段落の引用と `<p>` の外に書かれた本文を含む記事では成り立っていなかった。REST・フィードの経路は blockquote を中の段落ごと 1 段落にまとめ、ページの経路は `<p>`・`<li>` などをタグ名で列挙していたため `<p>` の外のテキスト (WordPress の写真枠 `<div class="wp-caption">` の後ろの本文など)、h5/h6、div 直書きの本文を落としていた。両経路とも、子を文書順に見てブロック要素の境目で段落にする走査 (`_iter_text_blocks`) に変えた。blockquote の中の段落と入れ子のリストの項目は別段落になり (`<li>` の中で入れ子のリストの後ろに続く文も、ブラウザの表示と同じくリストの後の別段落)、Instagram 埋め込み (「View this post on Instagram」) と video/audio/iframe の代替テキストは除く。これで複数段落の引用を含む記事でも REST とページの本文が一致する (Libera Folio は保存ページ 16 本、Global Voices は保存ページ 37 本で、空白を除いて一致を確認)
- **retradio_lib (文字の扱い)**: `<sup>` は直前が英数字か「)」なら `^` (「N^2-oble」「1/r^x」「µg/m^3」)、句読点・空白の後なら脚注番号として空白 (これまでは数字の直後だけ `^`)。`<sub>` は何も付けない (CO2)。ソフトハイフン・ゼロ幅空白・ZWNJ・WORD JOINER・BOM を本文と題名から除き、U+2028/U+2029 は空白にし、前後の空白と合わせて 1 つにまとめる。`<img>` などの置換要素は空白にして前後の語がつながらないようにした。題名の空白の並び (NBSP を含む) を 1 つにまとめる
- **retradio_lib (Global Voices のページ経路)**: `archive`/`both`、または `auto` で REST が使えなかったときの記事ページ解析で、題名がサイトロゴの空の h1 のため URL になり、本文が関連記事カードの見出し 1 行になっていた → 本文は `div.entry`、題名は `h2.post-title` (無ければ og:title、`<title>` からサイト名を除いたもの) から取る。本文が極端に短いときは警告する。ページから取る公開日は `<time datetime>` と `<meta property="article:published_time">` を時刻・オフセット付きで読む (これまでは日付だけ。Libera Folio・Scivolemo のページ経路も同じ)
- **retradio_lib (著者・カテゴリ・音声)**: Global Voices の著者を記事ページの署名「Tradukita (Esperanto) de 〈名前〉」から取る (REST の `_embedded.author` が 401 のため。共有アカウント名は除く)。特集ラベル (The Bridge / Rising Voices / GV Advocacy) を REST の `class_list` の `gv_special-*` とページの見出し画像から categories に加える。音声リンクは URL のパスの拡張子 (.mp3/.m4a/.ogg/.oga/.opus/.wav)、`<audio>`、type が audio/* の `<source>` だけを採り、ホスト名に「mp3」を含む別サイトのページ (vinilkosmo-mp3.com) や動画の `<source>` を拾わない。フィードの enclosure の音声も加える。フィードの dc:creator がサイト名と同じなら著者にしない。Scivolemo の既定のラベルを `scivolemo.wordpress.com` に直した
- **El Popola Ĉinio**: 節名の末尾のサイト名を除くとき「E-movado」「UK-oj」などの名前まで切っていたのを修正。categories を「記事が載っている節の一覧 (Plej Freŝaj などの集約一覧は、ほかの節があれば除く)」にした (これまでは最初に見つかった 1 節だけ)。サイトの一覧は各ノード 10 ページまでで、それより前は不完全なので、開始日が一覧の深さより古いと警告を出す。ページ送りの打ち切りは、どのページにも載る新着欄・固定記事を除いた一覧本体の日付で判定する。トップページのリンクから別ホストのノードを拾わず、別ホスト (espero.chinareports.org.cn) にある記事は収集せずに一覧 (`skipped_other_host`) で知らせる。本文冒頭の「de 名前」「名前 (国)」からも著者を取る。本文・題名の NBSP を含む空白の並びを 1 つにまとめる。一覧ページの取得失敗を例外のまま `load_errors` に持つ
- **Monato**: `--method both` のプローブは、Nova! 帯域の下端から `PROBE_MIN_SPAN=300` ID 下までは古いページが続いても止まらない (ID の位置より日付が数か月遅い記事を取り逃していた)。それより古い ID は `backfill_publika_probe.py` で定期的に走査する (「定期取得の手順」)。「Lasta adapto」の日付は最初の表だけでなくページ内のすべての表から探す (年別インデックス経由の URL で取れていなかった)。`backfill_publika_probe.py` は取得済みの応答を解析に渡して二重取得をやめ、年別 URL の ID も既知として扱う。ID プローブで通信エラーが 5 回続かずに散発したときも、届かなかった ID を errors に残す (これまでは 5 回連続で中断したときだけで、散発した分は黙って飛ばしていた)。アプリ・CLI はこれまでの部分失敗と同じ表示で知らせる
- **UEA Facila**: 公開日を JSON-LD の `datePublished` から取る。filmetoj・niaj-legantoj などではコメント欄の `<time>` (コメントの投稿日時) を公開日にしていた。活動ストリームのコメント項目 (`do=findComment`) を候補から外した。共著者を ", " でつなぎ (本文末尾の右寄せ署名にある平易化の担当者は含めない)、音声リンクは retradio_lib と同じ規則にした。ログインの送信内容を直し (`_processLogin`)、一覧の経路ごとの失敗を (URL, 例外) の組で返す
- **Streamlit アプリ**: URL 収集の一部失敗 (Monato の errors、El Popola Ĉinio の load_errors と一覧の深さの警告、UEA Facila の errors) を表示言語で出す。候補が 0 件で失敗があるときは「期間を変更して」ではなく「一部に失敗したので記事が無いとは限らない」と案内する。El Popola Ĉinio で別ホストにあったため集めなかった記事を一覧で見せる。UEA Facila の候補日付の注記から「読者コメントなどを含む」を削った。Scivolemo のリクエスト間隔の既定を 1.0 秒にした (CLI と同じ)。URL 収集が例外で止まったときのエラーは、表示言語を切り替えて画面が描き直されても消えず、切り替えた言語で出し直す (収集の条件を変えると消える)
- **CLI**: 日付引数は `YYYY-MM-DD` だけを受け付け、誤りや逆順の期間は通信前に 1 行のエラーで止める。Pola Retradio の `parallel_scraper.py` でも `--split-by none` の出力名を指定期間から作る。並列版 7 本で、`--split-by none` の md の time_range を指定期間にし、本文取得後に期間外で除いた記事の件数と URL を出す。Monato で開始日を月初に丸めるのは号の日付から取った記事だけにし、効かない `--feed-url` を削除。`--max-pages`・`--workers`・`--include-audio` の help を実装に合わせた。Scivolemo のラベルを直し、El Popola Ĉinio の CLI は一覧の深さの警告と別ホストの記事を表示する
- **コーパス**: 修正後のコードで次を反映した (本数は 1651→1656)。
  - Global Voices: 本文 22 本 (欠けていた段落の追加 10 本、引用・入れ子リストの段落分割と画像の前後の空白 12 本、Instagram の定型文の除去 1 本)。空欄だった著者 7 本を補い (36/37 本。残る 1 本は共有アカウント名での投稿)、特集ラベルを 5 本に加えた
  - Libera Folio: 本文 7 本 (引用の段落分割 2 本、`^` と U+2028 1 本、ソフトハイフン除去 3 本、末尾の署名段落 1 本)
  - Pola Retradio: published の +02:00 表記 204 本を、サイト本来の +01:00 表記に統一 (同じ時点。日付が変わるのは『E_elsendo el la 26.07.2025』07-27→07-26 の 1 本)。題名の空白 8 本、本文の不可視文字 2 本、音声リンクから vinilkosmo-mp3.com のページを除去 1 本
  - El Popola Ĉinio: categories 651 本を節の一覧に付け直した (一覧から消えていた 20 本は元の値のまま)。冒頭の署名から著者 54 本を補った (188→242/712 本)。本文の空白 26 本、題名 4 本。一覧の 10 ページ制限で取りこぼしていた 2025-03 の 4 本を追加
  - Monato: ID より日付が数か月遅い 013752 (2026-03-16) と 013837 (2026-04-03) を追加。カテゴリの大小文字違いの重複 1 本、ソフトハイフン 1 本、「µg/m^3」1 本
  - UEA Facila: コメント日時になっていた published 8 本を訂正 (5 本は月のファイルを移動)。そのうち r79 は本当の公開日が 2025-01-14 で期間外なので除外。共著者 7 本、音声リンク 1 本
- **輪読候補**: 生成スクリプトを `tools/rondolegado/` に移し、作業フォルダと注釈ツールの場所を引数で渡して `build_all.sh` で一覧 md・抽出 md・ルビ付き HTML・投票ページ・zip を作り直せるようにした (手順は `tools/rondolegado/README.md`)。抽出 md の中身を「エスペラントの題名と本文 (語注・著者紹介を含む。朗読案内・写真説明・クレジット・http(s) で始まる URL は除く)」と決め、50 本から写真説明 74・クレジット 42・朗読案内 15・リンクが外れて残った見出しや告知など 7・URL だけの段落 5 ほか、計 148 段落を除き、1 段落から URL を除いた (定型の無い写真説明と告知は記事ごとに `caption_paragraphs.json`・`noise_paragraphs.json` で指定)。語数をこの本文で数え直した (UEA Facila は末尾の署名・著者紹介・語注を数えない。401〜1,961 語)
- **輪読候補 (表示)**: 原文の誤字 2 か所 (No.16「Antaǔ」、No.25「êc」) を抽出 md とルビ付き HTML だけで直し、No.40 の題名から U+200C を除いた。ルビ付き HTML で、原文が x 方式の綴りの外来語 (Tropicaux など) まで字上符に変わっていたのを戻した。投票ページは x 方式 (cx・ux など) でも検索でき、掲載日の無い記事 (No.49) は「掲載日不明」と出す。語数の変化に合わせて No.34・No.50 の注記を直し、edition を 2026-09-v3 にした (投票ページの票は端末ごとに edition 単位で保存されるので、v2 の票は引き継がれない)
- **訂正**: これまで README (v1.2.1・v1.3.0 の記録、コレクションの状態の表) と MANIFEST で「サイト側で再掲された」としていた UEA Facila の filmetoj 3 本 (r379/r382/r385) は、再掲ではなく、取得コードがコメント日時を公開日として取ったため 2026-08 に重複して入っていたもの (初出側を残した処置はそのまま)。v1.3.2 の既知の制限 (Global Voices の著者・特集ラベル) は上記で解消
- **README**: 「ページ送りの上限」の入力欄の初期値 (どのサイトも 0)、Markdown 出力例の空行、published の意味 (ページ経路の時刻、Pola Retradio の UTC+1、Monato の Lasta adapto)、CSV のコンマ区切りの注意、El Popola Ĉinio・Monato・UEA Facila のページ構造の説明、`parallel_scraper.py` の並列の単位、ライセンス (MIT) の記述、トラブルシューティングの `pip` コマンドを実態に合わせた
- **既知の制限**: Global Voices をページ経路 (`archive`/`both`、または `auto` で REST が使えなかったとき) で取ると、categories にフィード・REST 由来の「Ĉefaĵo」「Blogo」と言語ラベル (Angla・Rusa など) が付かない (記事ページにこれらのラベルが無い)。既存の 37 本はフィード・REST 経由の値

### v1.3.2 (2026年9月16日)

- **retradio_lib (本文の文字列化)**: 本文・題名の文字列化を `_inline_text` にまとめ、リンク・太字などインライン要素の境目に空白を挟まずブラウザの表示どおりにつなぐ (「Kore , la」→「Kore, la」)。`<br>` と入れ子のブロックの境目は空白、数字の直後の `<sup>` は `^` (「2^6」)、NBSP を含む空白の並びは 1 つに
- **retradio_lib (写真の説明文)**: figcaption を本文に含める。これまでは WordPress REST の本文断片から取ったときだけ (lxml が `<figure>` を暗黙の `<p>` で包むため) 説明文が入り、記事ページから取ったときは入らなかった。記事ページから取ったときに Jetpack の共有欄・関連記事 (「Konigi ĉi tion:」「Rilataj」) が本文に混入していたのも除去し、REST とページで本文が一致することを Libera Folio・Pola Retradio で確認
- **retradio_lib (メタデータ)**: REST の `_embedded.author` がエラーになるサイト (Pola Retradio) では、author ID ごとに記事ページのバイラインから著者名を補う (Libera Folio は共有アカウント名しか無いので空欄のまま)。音声リンクからプレーヤー用の `?_=N` 付きの重複を除く。記事ページの公開日はフッターの「最近の投稿」欄やコメントの日付を拾わない
- **失敗の扱い**: フィード・月別アーカイブの 1 ページ目が取れないときは「期間内 0 件」と区別して例外にする。取得の失敗は `FetchError` (URL と HTTP ステータス付き)、どの経路でも URL を集められなかったときは `URLCollectionError` (経路ごとの例外付き) とし、El Popola Ĉinio・UEA Facila の一覧の失敗も同じ形にした。各 `scraper.py`・`parallel_scraper.py` は、一部の記事の取得に失敗しても取れた分を書き出して終了コード 1 で知らせる (0 件のときは空のファイルを作らない)
- **Monato**: 本文を h1 以降の段落と小見出し (h3〜h6) の文書順で読み、欠けていた小見出しと、段落の外に置かれた太字のリード文・書誌の行を補った。著者名の文字間に入っていた空白 (「Filip I VANČIĆ」) を解消
- **El Popola Ĉinio**: 本文末尾の署名 (「Raportis:」「Verkis kaj fotis:」「Verkita de」など) から著者を取る
- **UEA Facila**: 題名が `<br>` で 2 行のときは記号を足さずに空白でつなぐ (2 行目は副題のことも 1 行目の続きのこともある)。カテゴリにパンくず末尾の記事自身の題名が入っていたのを除去。カテゴリ一覧 (loke・niaj-legantoj のカード形式) からの収集と、`<p>` を使わず `<div dir="ltr">` だけで書かれた読者投稿の本文の取りこぼしを修正。`include_audio_links=False` のときは音声リンクを取らない
- **Streamlit アプリ**: 表示言語を切り替えても入力が既定値に戻らないようにした (ウィジェットの key をラベルに依存させない。サイトを往復すると、リクエスト間隔以外はサイトの既定値に戻る)。「ページ送りの上限」の 0 はサイトごとの標準値 (El Popola Ĉinio 80、UEA Facila 400)。Global Voices の既定の収集方法を `auto` に。収集の失敗理由 (接続できない・時間切れ・HTTP ステータスなど) と、取得できなかった記事の理由を表示言語で出す (これまでライブラリの日本語の文言が韓国語版・エスペラント版の画面に混ざっていた)。キャッシュから読んだ記事では待たない。Streamlit 1.50 (Python 3.9) と 1.63 (Python 3.11) で、日本語版・韓国語版・エスペラント版それぞれ 7 サイトの収集と言語切替を確認
- **コーパス**: 修正後のコードで 6 サイトの全記事を取り直して照合し、反映した (Global Voices は 2026-09-16 に一時的に接続できた間に)。空白の違いのほか、Libera Folio の写真の説明文 (105 本)、Monato の小見出し・リード文 (130 本)、著者の補完 (Pola Retradio 335 本、El Popola Ĉinio 120 本、Monato 71 本)、Pola Retradio の音声リンクの重複 (257 本) を反映。取りこぼしていた UEA Facila 1 本 (`…r510`) を追加 (この時点で計 1651 本。v1.3.3 の補完・除外後は 1656 本)。詳細は各フォルダの MANIFEST.md の備考
- **輪読候補**: 見直しで 3 本を差し替え、紹介文・難しさの表記を一部直し、本文の語数を載せた。抽出 md とルビ付き HTML を取り直した本文で作り直した
- **既知の制限**: Global Voices は、2026-09-16 の取り直しで REST から著者とプロジェクト名 (The Bridge など) のカテゴリが取れなかった (既存の値を残した)。その後ふたたび接続できなくなり、原因は確かめられていない

### v1.3.1 (2026年9月15日)

- **UEA Facila**: 練習問題への案内 `<p class="edukado">` の閉じタグが欠けた記事では、lxml が記事本体の `<section>` をこの段落の中に入れ子にするため、本文が「全体を1段落」と「各段落」の二重に抽出されていた → 案内段落の枠だけ外して抽出 (該当 2 本を取り直し。全記事を再照合して他に変化なし)
- **El Popola Ĉinio**: 本文を `get_text("\n")` で文字列の切れ目ごとに改行していたため、段落の途中にインライン要素 (`<span>`・`<em>`・`<strong>` など) があると 1 段落が細切れになっていた (708 本中 107 本) → ブロック要素と `<br>` の境目だけで区切るよう修正。雑音除去 (`NOISE_SNIPPETS`) は 80 字以下の行だけを対象にし、「WeChat」「Facebook」を含む本文の段落まで消していた問題 (13 本) を解消。ページ下部のフォロー欄の残骸行「El Popola Chinio」も出なくなった
- **Streamlit アプリ**: 韓国語版ラッパの説明文の日韓混在を修正。日本語版・韓国語版・エスペラント版のそれぞれで、7 サイトの実収集、言語切替、画面への他言語の混入がないことを Streamlit 1.50 (Python 3.9) と 1.63 (Python 3.11) で確認
- **コーパス**: Libera Folio 全 120 本を修正後のコードで取り直して照合し、古いコードで引用部分が二重になっていた 3 本を差し替え (写真説明文を含む既存 7 本はそのまま)。El Popola Ĉinio 全 708 本を修正後のコードで取り直して反映 (段落数 8,374→6,855、本文の文字列は一致、消えていた段落 13 本分を復元)
- **輪読候補**: 京大エス研の例会向けに 50 本を選び、日本語タイトルと短い紹介を付けた一覧を `取得文書ekde20260814/rondolegado_kandidatoj_202609.md` に追加。1 記事 1 ファイルの抽出 md (`rondolegado_kandidatoj_202609/`、注釈ルビツール esperanto-radiko-cjk-annotator にそのまま読み込める、エスペラントの題名と本文の形式。中身の決まりは v1.3.3 で `tools/rondolegado/README.md` に明記) と、50 本を同ツールの注釈ルビモードで変換したルビ付き HTML に一覧・投票ページを添えた Netlify Drop 用フォルダ (`rondolegado_kandidatoj_202609_ruby/` と同名の zip) も同梱

### v1.3.0 (2026年9月15日)

- **El Popola Ĉinio**: 他ページの HTML ごと貼り込まれた記事で、本文セル内の `<title>`/`<style>` が本文として拾われ、関連記事のタイトルが `<span style=…>` タグ付きで本文末尾に混入していた (2025-03〜11 の 320 本) → 抽出前に除去
- **El Popola Ĉinio**: 記事末尾のリンク文言「Ĉina Fokuso / China Focus - Esperanto」を除くための `NOISE_SNIPPETS` が NBSP 区切りで定義されていて、通常の空白の現行ページと一致せず素通りしていた (2026-05 以降の 163 本に混入) → 空白を揃えて照合
- **UEA Facila**: 記事要素の内側にあるリアクション数 (「6」「1」等の数字だけの行) と、filmetoj の難易度投票欄の文言が本文に混入していた → 抽出前に除去
- **retradio_lib**: PowerPress の操作文言「Podkasto: Ludu en nova fenestro | Elŝutu」を本文から除去 (音声リンクは従来どおり取得)
- **retradio_lib (キャッシュ)**: HTTP キャッシュ (SQLite) を作業フォルダに置いていたため、クラスタで各サイトのジョブを同時に投入すると、共有ディスク上の同じファイルを別ノードから読み書きしてロック競合や破損読み出しが起き、ジョブが落ちていた (2026-09-15 に UEA Facila で発生) → 保存先を OS の一時フォルダに変更 (`RETRADIO_CACHE_DIR` で変更可)
- **Streamlit アプリ**: Monato は収集方法が feed (Nova! ページ) 固定で、直近約2か月より前を指定すると記事を取りこぼしていた → `both` (既定)・`feed`・`archive` を選べるように。削除予定の `use_container_width` を `width="stretch"` に置き換え (Streamlit 1.50 と 1.63 で動作確認)
- **requirements.txt**: `streamlit>=1.50.0` に更新。このクラスタ (CentOS 7, glibc 2.17) の Python 3.9 では `pip install -r requirements.txt` が pyarrow のソースビルドで失敗するため、`pyarrow<21` を指定
- **gen_manifest.py**: MANIFEST の「git 管理外」の記述を現在の運用 (記事は korpuso で管理) に合わせて修正
- **コーパス**: 修正後のコードで既存記事を取り直して照合し、雑音を除去 (El Popola Ĉinio の関連記事タイトル 320 本とリンク文言 163 本、UEA Facila 135 本、Pola Retradio 76 本、Global Voices の段落重複 19 本)。取り直しで判明したサイト側の修正 6 本を反映し、Libera Folio の published をサイト本来の UTC+1 表記に統一。フォルダ間で重複していた UEA Facila 3 本 (コメント日時で重複した 3 本) を除去し、取りこぼしていた Global Voices 1 本を追加。新フォルダ `取得文書ekde20260814` (2026-08-14〜09-14、86 本) を追加

### v1.2.1 (2026年8月23日)

v1.2.0 の修正自体への退行レビュー (確定6件) を反映:

- **retradio_lib (REST)**: published のタイムゾーンは cfg.timezone を貼らず、WP の date/date_gmt の差から**サイトの実オフセットを導出**して付与 (Libera Folio は通年 UTC+1 固定のため、Warsaw ラベルだと夏時間期間の時刻が実時刻から1時間ずれていた。日時の指す瞬間は date_gmt と等価で、期間フィルタはサイト現地日付基準を維持)
- **retradio_lib (feed)**: paged=N を無視しつつ毎回変わるリンクを返すサーバーで無限ループしないよう、max_pages 未指定時のページ送りに上限200頁を設定。エクスポート失敗時に *.tmp を残さないよう後始末を追加 (sync_korpuso.sh も *.tmp を除外)
- **backfill_publika_probe**: origin_labels を最初のファイル優先 (setdefault) にし、stale な monato_unknown.jsonl が手動配置済みの月ラベルを上書きしないように
- **UEA Facila**: 認証情報未設定時に匿名収集である旨を明示的に警告。ランブックのログイン記述と環境変数の使い方を更新
- MANIFEST (取得文書ekde20260401) の r385 注記を実態に合わせ修正 (再取得時にリアクション数「1」が本文に1行混入。連結時の重複除去は初出側を残す)

### v1.2.0 (2026年8月23日)

- **セキュリティ**: `Uea_Facila/uea_facila_lib.py` にハードコードされていたログイン認証情報を削除 (環境変数 `UEA_FACILA_USER` / `UEA_FACILA_PASS` のみ受付。**当該パスワードは漏洩済みとして要ローテーション**)
- **UEA Facila**: `fetch_article` に再試行を実装 (接続切断で記事が黙って欠落していた)。JSON-LD `datePublished` フォールバックを追加し、一覧キャッシュなしでも filmetoj の日付を取得可能に。2026-08-13 実行時の取得失敗 6 本を回収 (新コーパス 363→369 本)
- **retradio_lib**: ISO 日付 (`2026-04-12`) を DMY と誤読するバグ、フィード1ページ目が全て期間より新しいと収集を打ち切るバグ、REST の期間フィルタ基準 (`date_gmt`→`date`) の不一致、入れ子要素 (blockquote>p 等) による段落重複、エクスポートの非アトミック書き込みを修正
- **Monato**: `fetch_article` に retry_get を適用。`backfill_publika_probe.py` で一時的 5xx/429 を「非公開・不存在」と誤分類するバグを修正し、日付不明記事の無条件採用をやめ (`--include-undated`)、マージ時に手動配置済みの月ラベルを維持するよう変更
- **El Popola Ĉinio**: 本文が空になる動画・写真ページで警告を出すように (既知 4 本は実ページに本文なしで正常、MANIFEST に記録)
- **並列スクレイパー全6サイト**: `--split-by none` の出力ファイル名を取得結果依存から指定期間ベースに変更 (再実行での重複ファイル増殖を防止)
- **運用**: `sync_korpuso.sh` が push 失敗後の未 push コミットを次回送信し、ローカルで削除・改名されたコーパスフォルダを korpuso 側にも反映するように。`.gitignore` に SQLite サイドファイル (`retradio_cache.sqlite*`) を追加、`logs/.gitkeep` を追跡し qsub の `-o/-e logs/...` がフレッシュクローンで壊れないように。CRI 16w ジョブの空グロブガードを追加。輪読素材選定ランブックの Monato 記述 (feed 前提・約20本/年) を both 前提に更新

### v1.1.0 (2026年8月)

- **Monato**: 年別インデックス401問題への対策として ID 連番プローブ (`--method archive/both`) を実装、既定値を `both` に変更
- **Monato**: セクション見出し (h3) を飛び越えて ul を重複走査するバグ、author 抽出正規表現の二重エスケープ、号日付 (月粒度) と開始日 (日粒度) の境界比較バグを修正
- **Monato**: インデックス・プローブ取得に retradio_lib のリトライ (`_get`) を適用、収集統計 (initial/used/duplicates/out-of-range) を正確化
- 記事本文を git 管理から除外 (著作権対応)、`gen_manifest.py` によるマニフェスト運用を導入

### v1.0.0 (2025年10月)

- 初期リリース
- 6つのエスペラントサイト対応（後に Libera Folio を追加し7サイト）
- 多言語UI（日本語、韓国語、エスペラント）
- 4つのエクスポート形式（Markdown、TXT、CSV、JSONL）
- REST API、Feed、Archiveの3つの収集方法

---

## まとめ

このStreamlitアプリケーションは、エスペラント語の記事を効率的に収集・管理するための包括的なツールです。主な特徴：

- **多サイト対応**: 7つの主要エスペラントサイトをサポート
- **多言語UI**: 日本語、韓国語、エスペラントで利用可能
- **柔軟な収集**: REST API、Feed、Archiveの複数の収集方法
- **豊富なエクスポート**: Markdown、TXT、CSV、JSONL形式で出力
- **ユーザーフレンドリー**: 直感的なWebインターフェース
- **拡張可能**: 新しいサイトやフォーマットの追加が容易

エスペラント学習者、研究者、アーカイビストなど、様々なユーザーのニーズに対応する設計となっています。

**ぜひお試しください！**
