"""輪読候補の一覧 md・抽出 md・候補メタ (candidates.json)・投票ページ (index.html) を作る。

使い方: build_rinlist.py --wd <kolektilo の作業フォルダ> --out <出力フォルダ>

入力は同じフォルダの candidates.json (番号・slug・日本語題名・紹介・注記・難しさ・テーマ・URL を人手で決めたもの)、
caption_paragraphs.json (記事ごとに落とす写真説明の段落)、noise_paragraphs.json (記事ごとに落とすリンク見出し・告知・クレジットの段落) と、
<wd>/取得文書ekde2026*/*.jsonl のコーパス。題名・掲載日・本文・収録ファイル・語数はコーパスから毎回作り直す。
出力 (<out> の下):
  rondolegado_kandidatoj_202609/*.md   抽出 md (この中の *.md だけを作り直す)
  rondolegado_kandidatoj_202609.md     一覧 md
  candidates.json                      生成後の候補メタ (finish_ruby.py の入力)
  kion-ni-legos.html                   投票ページ (Artifact 版、ルビへのリンクなし)
  netlify/index.html                   投票ページ (Netlify Drop 版、ルビ付き HTML へのリンクつき)
ruby_raw/ と netlify/ の記事 HTML には触らない (annotate.py・finish_ruby.py の出力)。
"""
import argparse, collections, glob, json, os, re, unicodedata, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
W = re.compile(r"[A-Za-zĈĉĜĝĤĥĴĵŜŝŬŭ]+(?:[-'’][A-Za-zĈĉĜĝĤĥĴĵŜŝŬŭ]+)*")
THEMES = {'言語', 'エスペラント運動', '文化・芸術', '歴史', '社会', '科学・技術', '環境・自然', '生活・食', '旅・地理', '教育', '国際'}
LEVELS = ['やさしい', 'ふつう', '手ごわい']
SITE_LABEL = {'uea_facila': 'UEA Facila', 'libera_folio': 'Libera Folio', 'global_voices_eo': 'Global Voices',
              'monato': 'MONATO', 'el_popola_cxinio': 'El Popola Ĉinio'}
REPO_BLOB = 'https://github.com/Esperanto-Societo-de-Kioto-Universitato/esperanta-artikolo-korpuso/blob/main/'
REPO_RAW = 'https://raw.githubusercontent.com/Esperanto-Societo-de-Kioto-Universitato/esperanta-artikolo-korpuso/main/'
MD_NAME = 'rondolegado_kandidatoj_202609'
MD_DIR_REL = f'取得文書ekde20260814/{MD_NAME}'
# 番号・記事が変わったら edition を変え、端末に残る旧版の票が別の記事に付かないようにする
EDITION = '2026-09-v3'
SELECTED = '2026年9月15日、選定時点の全1,650本のうち条件に合う423本に目を通して50本を選定（9月16日に見直しで3本を差し替え）'

# 抽出 md から落とす段落。語数も同じ判定で数える。
CREDIT = re.compile(r'^(Foto|Fotoj|Bildo|Bildoj|Fotis|Redaktoro|Tradukis|Verkis|Fonto|Raportis|Kredito|Ilustraĵo)\b.*'
                    r'|.*\b(Foto|Bildo|Fotis):\s*\S.*$|^\(el ĈRI\)$|^El.Popola.Chinio$|.*sekcio por abonantoj.*', re.I)
URL = re.compile(r'<?https?://\S+>?')
# 段落末尾が写真クレジットの定型で終わる写真説明。「permesilo」を段落のどこにでも当てたり「Foto de」だけで判定したりすると、
# 本文の段落 (El Popola Ĉinio の長い段落など) まで落ちる。
CAPTION_TAIL = re.compile(r'.*\b(Foto|Bildo|Ekranfoto|Ekrankopio|Il+ustraĵo)\b[^.]*\.?\s*'
                          r'((Uzata|eldonita) kun permeso[^.]*|uzata permesite|Justa uzo|laŭ permes?i?silo[^.]*|CC BY[^.]*)\.*\s*$',
                          re.I | re.S)
LICENSE = re.compile(r'\bCC[- ](BY|SA)\b|Wikimedia Commons|^(Wikipedia|Wikimedia|Vikipedio)\s*/')


def drop_reason(paras, k):
    """段落 k を抽出 md から落とす理由 (落とさないなら None)。"""
    t = paras[k]
    n = len(W.findall(t))
    if CREDIT.match(t):
        return 'クレジット'
    if URL.fullmatch(t):
        return 'URL'
    if re.match(r'Eblas aŭskulti ĉi tiun artikolon', t):
        return '朗読案内'
    if re.match(r'Legu pli:\s', t):
        return '関連記事リンク'
    if re.fullmatch(r'\[Ĉiuj ligiloj .*\]', t):
        return 'リンク注記'
    if 'ISBN' in t or 'Prezo:' in t:
        return '書誌'
    if CAPTION_TAIL.fullmatch(t) and n <= 40:
        return '写真説明'
    if LICENSE.search(t) and n <= 30:
        return '写真クレジット'
    if re.fullmatch(r'Pentraĵo de [^.]*', t) and n <= 12:
        return '写真説明'
    return None


# 原文の誤字と、本文につながった画像説明の、抽出 md だけでの置き換え (コーパスは原文どおり)。
# (置き換え前, 置き換え後) は語単位で 1 回だけ現れること。
TEXT_FIXES = {
    'https://www.liberafolio.org/2026/06/23/esperanta-vikipedio-en-pralingva-ciklo/': [('Antaǔ', 'Antaŭ')],
    'https://www.liberafolio.org/2026/01/28/kanada-filmo-en-esperanto-nun-rete-spektebla/': [('êc', 'eĉ')],
    'https://eo.globalvoices.org/2025/10/15700/': [
        ('la jenon: AI-bildoj generitaj en Perchance.org la 13-an de aŭgusto 2024. Bildoj de Tactical Tech.', 'la jenon:')],
}


def norm_title(t):
    return ''.join(ch for ch in t if unicodedata.category(ch) != 'Cf').strip()


def ascii_slug(s, maxlen=40):
    s = s.translate(str.maketrans('ĉĝĥĵŝŭĈĜĤĴŜŬ', 'cghjsuCGHJSU'))
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    s = re.sub(r'[^A-Za-z0-9]+', '-', s).strip('-').lower()
    return s[:maxlen].rstrip('-') or 'artikolo'


def apply_fixes(url, text):
    for old, new in TEXT_FIXES.get(url, []):
        hits = [m.start() for m in re.finditer(r'(?<!\w)' + re.escape(old) + r'(?!\w)', text)]
        assert len(hits) == 1, (url, old, len(hits))
        text = text[:hits[0]] + new + text[hits[0] + len(old):]
    return text


def body_paragraphs(url, content_text, captions=None, noise=None):
    """(残す段落のリスト, 落とした (理由, 段落) のリスト)。残した段落の中の URL は除く。

    captions は記事ページで写真説明だった段落 (caption_paragraphs.json の url の値)。定型の無い説明は規則で見分けられない。
    noise はリンクが外れて残った見出し・購入案内・助成クレジットなど (noise_paragraphs.json の url の値)。
    """
    paras = [p.strip() for p in apply_fixes(url, content_text).split('\n\n') if p.strip()]
    for q in (captions or []) + (noise or []):
        assert paras.count(q) == 1, (url, q, paras.count(q))
    kept, dropped = [], []
    for k, p in enumerate(paras):
        if p in (captions or []):
            why = '写真説明'
        elif p in (noise or []):
            why = '告知・リンク見出し'
        else:
            why = drop_reason(paras, k)
        if why:
            dropped.append((why, p))
            continue
        t = re.sub(r'\s*<?https?://\S+>?', '', p).strip()
        if t != p:
            dropped.append(('段落内の URL', p))
        if t:
            kept.append(t)
    return kept, dropped


def uea_signature_index(paras):
    """UEA Facila の本文末尾の署名段落 (著者名だけの段落) の位置。以降は署名・写真の注記・著者紹介・語注。

    署名は「名前だけの短い段落で、後ろに同じ名で始まる著者紹介がある」もの。本文中の写真説明
    (「Johann Martin Schleyer en 1908」) も同じ形になりうるので、条件に合う最後の段落を採る。
    """
    found = None
    for k, p in enumerate(paras):
        toks = p.split()
        if not (2 <= len(toks) <= 8) or p[-1] in '.!?:;"”)' or not all(x[:1].isupper() for x in toks[:2]):
            continue
        # 署名と紹介で姓の書き方が違うことがある (Carolyn Thomas-Nedzelsky / Carolyn Thomas)
        name = re.compile(re.escape(toks[0]) + r'\b')
        if any(name.match(q) and len(q.split()) >= 10 for q in paras[k + 1:]):
            found = k
    return found


def count_words(site, kept):
    if site == 'uea_facila':
        end = uea_signature_index(kept)
        assert end is not None, kept[:3]
        kept = kept[:end]
    return sum(len(W.findall(p)) for p in kept)


def load_corpus(wd):
    corpus = {}
    for p in sorted(glob.glob(os.path.join(wd, '取得文書ekde2026*', '*.jsonl'))):
        folder, fn = p.split(os.sep)[-2:]
        for line in open(p, encoding='utf-8'):
            if line.strip():
                r = json.loads(line)
                assert r['url'] not in corpus, r['url']
                corpus[r['url']] = (f'{folder}/{fn[:-6]}.md', r)
    return corpus


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--wd', required=True, help='kolektilo の作業フォルダ (取得文書ekde2026*/ がある場所)')
    ap.add_argument('--out', required=True, help='出力フォルダ')
    ap.add_argument('--candidates', default=os.path.join(HERE, 'candidates.json'))
    ap.add_argument('--template', default=os.path.join(HERE, 'kion-ni-legos.template.html'))
    ap.add_argument('--captions', default=os.path.join(HERE, 'caption_paragraphs.json'),
                    help='記事ごとに落とす写真説明の段落 ({url: [段落, ...]})')
    ap.add_argument('--noise', default=os.path.join(HERE, 'noise_paragraphs.json'),
                    help='記事ごとに落とすリンク見出し・告知・クレジットの段落 ({url: [段落, ...]})')
    ap.add_argument('--dropped', help='落とした段落の一覧を書き出す JSON (目視確認用)')
    args = ap.parse_args()

    corpus = load_corpus(args.wd)
    captions = json.load(open(args.captions, encoding='utf-8'))
    noise = json.load(open(args.noise, encoding='utf-8'))
    items = []
    dropped_all = []
    for x in json.load(open(args.candidates, encoding='utf-8')):
        file, c = corpus[x['url']]
        site = re.sub(r'_(\d{4}-\d{2}|unknown)$', '', os.path.basename(file)[:-3])
        assert site == x['site'] and x['theme'] in THEMES and x['level'] in LEVELS, x
        assert len(x['ja_title']) <= 32 and len(x['summary']) <= 90 and len(x.get('note') or '') <= 120, x
        eo_title = norm_title(c['title'])
        slug = f"{x['no']:02d}_{ascii_slug(eo_title)}"
        assert slug == x['slug'], (slug, x['slug'])
        kept, dropped = body_paragraphs(x['url'], c['content_text'], captions.pop(x['url'], None), noise.pop(x['url'], None))
        dropped_all.append({'no': x['no'], 'slug': slug, 'dropped': [{'reason': r, 'text': t} for r, t in dropped]})
        md_rel = f"{MD_DIR_REL}/{slug}.md"
        items.append(dict(url=x['url'], site=site, eo_title=eo_title, published=(c.get('published') or '')[:10],
                          words=count_words(site, kept), ja_title=x['ja_title'], summary=x['summary'],
                          theme=x['theme'], level=x['level'], note=x.get('note') or '', file=file,
                          no=x['no'], slug=slug, md_rel=md_rel,
                          md_url=REPO_BLOB + urllib.parse.quote(md_rel), md_raw=REPO_RAW + urllib.parse.quote(md_rel),
                          ruby=f'{slug}.html', _body=kept))
    assert not captions and not noise, sorted(captions) + sorted(noise)
    items.sort(key=lambda i: i['no'])
    assert [i['no'] for i in items] == list(range(1, 51)) and len({i['url'] for i in items}) == 50
    assert min(i['words'] for i in items) >= 400, [(i['no'], i['words']) for i in items if i['words'] < 400]

    md_dir = os.path.join(args.out, MD_NAME)
    os.makedirs(md_dir, exist_ok=True)
    for f in glob.glob(os.path.join(md_dir, '*.md')):
        os.remove(f)
    for i in items:
        with open(os.path.join(md_dir, i['slug'] + '.md'), 'w', encoding='utf-8') as f:
            f.write(i['eo_title'] + '\n\n' + '\n\n'.join(i['_body']) + '\n')
    with open(os.path.join(args.out, 'candidates.json'), 'w', encoding='utf-8') as f:
        json.dump([{k: v for k, v in i.items() if not k.startswith('_')} for i in items], f, ensure_ascii=False, indent=1)
        f.write('\n')
    if args.dropped:
        with open(args.dropped, 'w', encoding='utf-8') as f:
            json.dump(dropped_all, f, ensure_ascii=False, indent=1)

    keys = ('no', 'ja_title', 'eo_title', 'site', 'published', 'words', 'theme', 'level', 'summary', 'note', 'url', 'file', 'md_url')
    meta = {'edition': EDITION, 'selected': SELECTED}
    tpl = open(args.template, encoding='utf-8').read()
    assert tpl.count('/*__DATA__*/[]') == 1 and tpl.count('/*__META__*/{}') == 1

    def page(rows):
        return (tpl.replace('/*__DATA__*/[]', json.dumps(rows, ensure_ascii=False))
                .replace('/*__META__*/{}', json.dumps(meta, ensure_ascii=False)))
    with open(os.path.join(args.out, 'kion-ni-legos.html'), 'w', encoding='utf-8') as f:
        f.write(page([{k: i[k] for k in keys} for i in items]))
    head, body = page([{**{k: i[k] for k in keys}, 'ruby': i['ruby']} for i in items]).split('<div class="wrap">', 1)
    standalone = ('<!doctype html>\n<html lang="ja">\n<head>\n<meta charset="utf-8">\n'
                  '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
                  + head.strip() + '\n</head>\n<body>\n<div class="wrap">' + body.rstrip() + '\n</body>\n</html>\n')
    os.makedirs(os.path.join(args.out, 'netlify'), exist_ok=True)
    with open(os.path.join(args.out, 'netlify', 'index.html'), 'w', encoding='utf-8') as f:
        f.write(standalone)

    fmt = lambda n: f'{n:,}'
    sess = lambda w: '2回に分けて' if w > 1500 else '1回'
    lines = ['# 輪読候補 50 本(2026年9月) — Kion ni legos?', '',
             '京都大学エスペラント研究会の例会で、次に輪読する記事を皆で選ぶための候補リストです。日本語タイトルと紹介を見て、読みたい記事を番号で挙げてください。', '',
             '- 選定日: 2026-09-15',
             '- 対象: 取得文書ekde20260303 / ekde20260401 / ekde20260814 (2025-03-03〜2026-09-14、選定時点 (2026-09-15) の 1,650 本)',
             '- 条件: 全文が読める・動画でない・350〜2,500 語・過去の輪読素材 (2026-03、2026-08) で使っていない記事 423 本 (選定時点の数) に目を通し、話題の広がり・分量・読みやすさ・テーマと出典の偏りのなさで選んだうえで、本文 400 語未満の 3 本を予備候補と差し替えた (Pola Retradio は方針により除外)',
             '- 難しさ: やさしい = 短い平叙文中心で基本語彙で読める / ふつう = 一般的な報道・解説文 / 手ごわい = 専門用語や長く入り組んだ文、文芸的・抽象的な論説',
             '- 語数は本文のおおよその語数 (語注・朗読案内・写真説明・クレジット・URL を除く。UEA Facila は末尾の署名・著者紹介も除く)。分量の目安は 1,500 語以下なら 1 回、それを超えるものは 2 回に分けて。候補はすべて本文 400 語以上',
             '- 番号は難しさ(やさしい → ふつう → 手ごわい)の順。各記事の著作権は掲載サイト・著者に帰属します',
             '- 抽出md: 各記事を 1 記事 1 ファイルにした Markdown (`rondolegado_kandidatoj_202609/` フォルダ)。エスペラントの題名と本文 (語注・著者紹介を含む) で、朗読案内・写真説明・クレジット・URL は除いてあるので、注釈ルビツール ([esperanto-radiko-cjk-annotator](https://esperanto-radiko-cjk-annotator.streamlit.app/)) の「ファイルアップロード」にそのまま読み込める ([raw] を保存してアップロードするか、全文をコピーして貼り付ける)',
             '- ルビ付き HTML: 50 本すべてを同じツールの注釈ルビモードで変換し、一覧ページ (投票・集計つき) と合わせた Netlify Drop 用フォルダ `rondolegado_kandidatoj_202609_ruby/` を同梱 (フォルダごと https://app.netlify.com/drop にドロップすると部員と共有できるサイトになる)', '',
             '## 一覧', '', '| No. | 日本語タイトル | 出典 | 本文語数 | 難しさ | テーマ |', '|---:|---|---|---:|---|---|']
    for i in items:
        lines.append(f"| {i['no']} | {i['ja_title']} | {SITE_LABEL[i['site']]} | {fmt(i['words'])} | {i['level']} | {i['theme']} |")
    lines += ['', '## 紹介', '']
    for i in items:
        lines += [f"### No.{i['no']} {i['ja_title']}", '',
                  f"*{i['eo_title']}* — {SITE_LABEL[i['site']]}、{i['published'] or '掲載日不明'}、本文 {fmt(i['words'])} 語({sess(i['words'])})、{i['level']}、{i['theme']}", '',
                  i['summary'], '']
        if i['note']:
            lines += [f"※ {i['note']}", '']
        lines += [f"原文: <{i['url']}>  ",
                  f"抽出md: [{i['slug']}.md]({MD_NAME}/{i['slug']}.md) ([raw]({i['md_raw']}))  ",
                  f"コーパス: `{i['file']}`", '']
    with open(os.path.join(args.out, MD_NAME + '.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines).rstrip() + '\n')
    print('難しさ:', dict(collections.Counter(i['level'] for i in items)), '| 出典:', dict(collections.Counter(i['site'] for i in items)))
    print('語数:', min(i['words'] for i in items), '〜', max(i['words'] for i in items),
          '| 落とした段落:', sum(len(d['dropped']) for d in dropped_all))


if __name__ == '__main__':
    main()
