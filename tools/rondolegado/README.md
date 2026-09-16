# 輪読候補一式の生成スクリプト (tools/rondolegado/)

`取得文書ekde20260814/` にある輪読候補一式を、コーパスとこのフォルダの入力から作り直すためのスクリプトです。

- `rondolegado_kandidatoj_202609.md`: 50 本の一覧 md
- `rondolegado_kandidatoj_202609/`: 抽出 md (1 記事 1 ファイル)
- `rondolegado_kandidatoj_202609_ruby/`: ルビ付き HTML 50 本と投票ページ index.html (Netlify Drop 用)
- `rondolegado_kandidatoj_202609_ruby.zip`: 上のフォルダの zip

## 入力

| ファイル | 中身 |
|---|---|
| `candidates.json` | 候補 50 本のメタ。人手で決めるのは `no`・`slug`・`url`・`site`・`ja_title`・`summary`・`note`・`theme`・`level`。題名・掲載日・語数・収録ファイル・md のリンクは毎回コーパスから作り直す (生成後の値で上書きして保存してある) |
| `caption_paragraphs.json` | 記事ごとに落とす写真説明の段落 (`{url: [段落, ...]}`、コーパスの段落と完全一致)。定型のクレジットが付かない説明 (El Popola Ĉinio の中央寄せの説明、Libera Folio の figcaption など) は規則で見分けられないので、記事ページで写真説明だった段落をここに書く |
| `noise_paragraphs.json` | 記事ごとに落とす、本文ではない段落 (リンクが外れて残った見出し・購入案内・助成クレジット・関連記事の案内など)。形は `caption_paragraphs.json` と同じ |
| `kion-ni-legos.template.html` | 投票ページの雛形 (`/*__DATA__*/[]` と `/*__META__*/{}` に候補とメタを入れる) |
| `<作業フォルダ>/取得文書ekde2026*/*.jsonl` | コーパス。本文・題名・掲載日はここから読む |
| 注釈ツール | [esperanto-radiko-cjk-annotator](https://github.com/Esperanto-Societo-de-Kioto-Universitato/esperanto-radiko-cjk-annotator) のコミット `791e395` の `Esperanto-Kanji-Ruby-JA/` (日本語版) |

## 再生成の手順

```sh
# 注釈ツール (初回だけ)
git clone https://github.com/Esperanto-Societo-de-Kioto-Universitato/esperanto-radiko-cjk-annotator.git /path/to/annotator
git -C /path/to/annotator checkout 791e395
python3 -m venv /path/to/annvenv && /path/to/annvenv/bin/pip install -r /path/to/annotator/Esperanto-Kanji-Ruby-JA/requirements.txt

# 一式を作り直して 取得文書ekde20260814/ に配置する (50 本の注釈で約 7 分)
ANNOTATOR_PYTHON=/path/to/annvenv/bin/python \
  sh tools/rondolegado/build_all.sh "$PWD" /path/to/annotator/Esperanto-Kanji-Ruby-JA /path/to/work
```

`build_all.sh` は次の順に動きます。出力フォルダ (`/path/to/work`) は消さずに使い回します。配置せずに確かめるときは 4 番目の引数に `--no-place` を付けます。

1. `build_rinlist.py --wd <作業フォルダ> --out <出力>`: 抽出 md・一覧 md・`candidates.json`・投票ページ (`kion-ni-legos.html` は Artifact 版、`netlify/index.html` は Netlify 版) を作る。落とした段落の一覧を `dropped_paragraphs.json` に書く
2. `annotate.py <注釈ツール> <出力>/rondolegado_kandidatoj_202609 <出力>/ruby_raw`: 抽出 md をルビ付き HTML にする (md・annotate.py・注釈ツールの *.py と app_data/ が前回と同じ記事は飛ばす)
3. `finish_ruby.py <出力>`: ルビ付き HTML に日本語の見出しとナビゲーションを付けて `netlify/` に置く
4. `place_kandidatoj.sh <出力> <作業フォルダ>`: `取得文書ekde20260814/` に配置し、zip を作る

作り直したら、`<出力>/candidates.json` をこのフォルダの `candidates.json` に写しておく (次回の入力と揃える)。

## 抽出 md と語数の決まり

- 抽出 md はエスペラントの題名と本文 (語注・著者紹介を含む)。題名から書式制御文字 (U+200C など) を除く
- `caption_paragraphs.json` に書いた段落 (写真説明) と `noise_paragraphs.json` に書いた段落 (告知・リンク見出し) を落とす。候補を差し替えたら、新しい記事のページで写真説明を、抽出 md の冒頭と末尾で告知などを確かめて足す
- 次の段落は落とす: 写真クレジット (`Foto:` など)・URL だけの段落と「Fonto:」・朗読案内 (`Eblas aŭskulti ĉi tiun artikolon`)・`Legu pli:`・`[Ĉiuj ligiloj …]`・ISBN や価格を含む書誌・末尾がクレジット定型 (`uzata kun permeso`・`Justa uzo`・`CC BY` など) の写真説明 (40 語以下)・CC BY や Wikimedia Commons を含む短い段落 (30 語以下)。残った段落の中の URL も除く
- 原文の誤字などは `build_rinlist.py` の `TEXT_FIXES` で抽出 md だけを直す (コーパスは原文どおり)。直した記事は `candidates.json` の note に書く
- 語数は抽出 md の本文の語数。UEA Facila は末尾の署名段落から後ろ (署名・著者紹介・語注) を数えない
- 注釈ツールは x 方式 (ux→ŭ など) を文字列置換で字上符にするので、`annotate.py` は原文で x 方式だった語 (Leroux・Tropicaux など) を原文の綴りに戻す
- 候補の番号や記事を変えたら、`build_rinlist.py` の `EDITION` を上げる (投票ページの票は端末ごとに edition 単位で保存される)
