"""注釈ルビ HTML に日本語の見出しとナビゲーションを付け、Netlify Drop 用フォルダに置く。

使い方: finish_ruby.py <出力フォルダ>
<出力フォルダ>/candidates.json (build_rinlist.py の出力) と ruby_raw/<slug>.html (annotate.py の出力) から
netlify/<slug>.html を作る。netlify/ にある候補以外の記事 HTML は消す (index.html は残す)。
"""
import glob, json, os, sys, html, re
if len(sys.argv) != 2 or sys.argv[1] in ("-h", "--help"):
    sys.exit(__doc__)
OUT = os.path.abspath(sys.argv[1])
RAW = os.path.join(OUT, 'ruby_raw')
DST = os.path.join(OUT, 'netlify')
SITE = {'uea_facila': 'UEA Facila', 'libera_folio': 'Libera Folio', 'global_voices_eo': 'Global Voices',
        'monato': 'MONATO', 'el_popola_cxinio': 'El Popola Ĉinio'}
STYLE = '''
    <style>
      .kes-hdr { font-family: "Hiragino Kaku Gothic ProN", "Yu Gothic", "Noto Sans JP", sans-serif; max-width: 46em;
                 margin: 0 0 1.4em; padding: 0 0 1em; border-bottom: 1px solid #cfd8cc; color: #1f2a23; line-height: 1.7; }
      .kes-hdr a { color: #1d7543; }
      .kes-nav, .kes-meta, .kes-links, .kes-cred { margin: 0.3em 0; font-size: 0.85rem; }
      .kes-meta, .kes-cred { color: #5d6b62; }
      .kes-ja { margin: 0.3em 0 0.1em; font-size: 1.35rem; line-height: 1.45; }
      .kes-eo { margin: 0; font-style: italic; color: #3b4a40; }
      .kes-sum { margin: 0.6em 0 0.2em; }
      .kes-links a { margin-right: 1.2em; }
      body { padding: 0 16px 48px; }
    </style>
'''
cands = json.load(open(os.path.join(OUT, 'candidates.json'), encoding='utf-8'))
os.makedirs(DST, exist_ok=True)
keep = {c['slug'] + '.html' for c in cands} | {'index.html'}
for f in glob.glob(os.path.join(DST, '*.html')):
    if os.path.basename(f) not in keep:
        os.remove(f)
done = 0
for c in cands:
    src = os.path.join(RAW, c['slug'] + '.html')
    s = open(src, encoding='utf-8').read()
    e = html.escape
    title = f"No.{c['no']} {c['ja_title']} — {c['eo_title']}"
    assert s.count('<title>エスペラント語根分解ルビ注釈テキスト</title>') == 1 and s.count('<body>') == 1 and s.count('</head>') == 1, src
    s = s.replace('<title>エスペラント語根分解ルビ注釈テキスト</title>', f'<title>{e(title)}</title>')
    s = s.replace('</head>', STYLE + '  </head>', 1)
    hdr = (f'<header class="kes-hdr">\n'
           f'  <p class="kes-nav"><a href="index.html">← 候補一覧（Kion ni legos?）</a></p>\n'
           f'  <p class="kes-meta">No.{c["no"]} ・ {e(SITE[c["site"]])} ・ {e(c["published"] or "掲載日不明")} ・ {c["words"]:,}語 ・ {e(c["level"])} ・ {e(c["theme"])}</p>\n'
           f'  <h1 class="kes-ja">{e(c["ja_title"])}</h1>\n'
           f'  <p class="kes-eo" lang="eo">{e(c["eo_title"])}</p>\n'
           f'  <p class="kes-sum">{e(c["summary"])}</p>\n'
           + (f'  <p class="kes-meta">※ {e(c["note"])}</p>\n' if c.get('note') else '') +
           f'  <p class="kes-links"><a href="{e(c["url"])}" target="_blank" rel="noopener">原文（{e(SITE[c["site"]])}）</a>'
           f'<a href="{e(c["md_url"])}" target="_blank" rel="noopener">抽出md</a></p>\n'
           f'  <p class="kes-cred">語根の上の青い小さな文字が日本語訳です（esperanto-radiko-cjk-annotator 日本語版・注釈ルビモードで生成）。記事の著作権は掲載サイト・著者に帰属します。</p>\n'
           f'</header>\n')
    s = s.replace('<body>', '<body>\n' + hdr, 1)
    s = s.replace('</body></html>', '<p class="kes-nav" style="font-family: sans-serif; font-size: 0.85rem;"><a href="index.html">← 候補一覧へ戻る</a></p>\n</body></html>', 1)
    open(os.path.join(DST, c['slug'] + '.html'), 'w', encoding='utf-8').write(s)
    done += 1
print('仕上げ:', done, '本 →', DST)
