"""esperanto-radiko-cjk-annotator 日本語版の「📖 注釈ルビ」モードと同じ手順で、抽出 md をルビ付き HTML に変換する。

使い方: annotate.py <注釈ツールの Esperanto-Kanji-Ruby-JA フォルダ> <抽出 md のフォルダ> <出力フォルダ>
<抽出 md のフォルダ>/*.md を <出力フォルダ>/<同名>.html に書く。入力・本スクリプト・注釈ツール (*.py と app_data/) が
前回と同じなら変換を飛ばす (<出力フォルダ>/<同名>.sha1 に照合用のハッシュを置く)。
"""
import glob, hashlib, os, re, sys, time

SELF = os.path.abspath(__file__)
if len(sys.argv) != 4 or sys.argv[1] in ("-h", "--help"):
    sys.exit(__doc__)
APP = os.path.abspath(sys.argv[1])
SRC = os.path.abspath(sys.argv[2])
DST = os.path.abspath(sys.argv[3])
os.chdir(APP); sys.path.insert(0, APP)
from esp_text_replacement_module import (x_to_circumflex, hat_to_circumflex, replace_esperanto_chars, import_placeholders,
                                         orchestrate_comprehensive_esperanto_text_replacement, apply_ruby_html_header_and_footer)
import esp_overlay_module as ov
import json
FMT = "HTML格式_Ruby文字_大小调整"
X_WORD = re.compile(r'\w*[cghjsuCGHJSU]x\w*')
TAG = re.compile(r'<[^>]*>')


def _plain_with_positions(html):
    """ルビ注釈の出力から、<rt> の中身とタグを除いたテキストと、各文字の出力上の位置を作る。

    ruby/rt 以外のタグ (<br> など) は語の区切りとして None の位置を持つ改行にする。
    """
    chars, pos = [], []
    i, n = 0, len(html)
    while i < n:
        if html[i] == '<':
            m = TAG.match(html, i)
            if not m:
                chars.append('<'); pos.append(i); i += 1
                continue
            name = re.match(r'</?\s*([A-Za-z0-9]+)', m.group(0))
            name = name.group(1).lower() if name else ''
            if name == 'rt' and not m.group(0).startswith('</'):
                end = html.find('</rt>', m.end())
                i = end + len('</rt>') if end >= 0 else m.end()
                continue
            if name not in ('ruby', 'rt'):
                chars.append('\n'); pos.append(None)
            i = m.end()
            continue
        if html[i] == '&':
            m = re.match(r'&(#\d+|#x[0-9A-Fa-f]+|\w+);', html[i:])
            if m:
                chars.append('￼'); pos.append(None); i += len(m.group(0))
                continue
        chars.append(html[i]); pos.append(i); i += 1
    return ''.join(chars), pos


def restore_x_words(src_text, html):
    """注釈ツールは x 方式 (ux→ŭ など) を文字列置換で字上符にするので、原文にある
    エスペラント以外の語 (Leroux, Tropicaux) まで変わる。原文で x 方式だった語の出現だけを原文の綴りに戻す。"""
    words = sorted(set(X_WORD.findall(src_text)))
    if not words:
        return html
    plain, pos = _plain_with_positions(html)
    edits = {}
    for w in words:
        conv = replace_esperanto_chars(w, x_to_circumflex)
        if conv == w:
            continue
        # 原文での w と conv の出現順と、出力での conv の出現順を対応させる (原文に字上符で書かれた conv はそのまま)
        src_seq = [m.group(0) for m in re.finditer(r'(?<!\w)(' + re.escape(w) + '|' + re.escape(conv) + r')(?!\w)', src_text)]
        out_hits = [m.start() for m in re.finditer(r'(?<!\w)' + re.escape(conv) + r'(?!\w)', plain)]
        assert len(src_seq) == len(out_hits), (w, len(src_seq), len(out_hits))
        for orig, start in zip(src_seq, out_hits):
            if orig != w:
                continue
            j = 0
            for k, ch in enumerate(conv):
                if w[j:j + 2] in x_to_circumflex and x_to_circumflex[w[j:j + 2]] == ch:
                    p = pos[start + k]
                    assert p is not None and html[p] == ch, (w, start + k)
                    edits[p] = w[j:j + 2]
                    j += 2
                else:
                    j += 1
    for p in sorted(edits, reverse=True):
        html = html[:p] + edits[p] + html[p + 1:]
    return html


t0 = time.time()
with open('./app_data/置換リスト_ルビ.json', encoding='utf-8') as f:
    data = json.load(f)
GG = data.get("全域替换用のリスト(列表)型配列(replacements_final_list)", [])
GL = data.get("局部文字替换用のリスト(列表)型配列(replacements_list_for_localized_string)", [])
G2 = data.get("二文字词根替换用のリスト(列表)型配列(replacements_list_for_2char)", [])
ents = ov.load_overlay_entries('./app_data', 'ruby')
if ents:
    GG = ov.merge_overlay(GG, ents)
PS = import_placeholders('./app_data/placeholders_skip.txt')
PL = import_placeholders('./app_data/placeholders_localcapture.txt')
print(f'[load] {time.time()-t0:.1f}s 補正 {len(ents)} 件', file=sys.stderr)


def run(text, gg):
    return orchestrate_comprehensive_esperanto_text_replacement(text=text, placeholders_for_skipping_replacements=PS,
        replacements_list_for_localized_string=GL, placeholders_for_localized_replacement=PL,
        replacements_final_list=gg, replacements_list_for_2char=G2, format_type=FMT)


def convert(text):
    out = run(text, GG)
    try:
        auto = ov.auto_overlay_entries(out, './app_data', 'ruby')
        if auto:
            out = run(text, ov.merge_overlay(GG, auto))
    except Exception as e:
        print('[auto_overlay skipped]', e, file=sys.stderr)
    out = replace_esperanto_chars(out, x_to_circumflex)
    out = replace_esperanto_chars(out, hat_to_circumflex)
    out = restore_x_words(text, out)
    return apply_ruby_html_header_and_footer(out, FMT)


def tool_hash():
    """本スクリプトと注釈ツール (直下の *.py と app_data/ の全ファイル) の内容のハッシュ。"""
    h = hashlib.sha1(open(SELF, "rb").read())
    files = glob.glob(os.path.join(APP, '*.py')) + [p for p in glob.glob(os.path.join(APP, 'app_data', '**'), recursive=True)
                                                  if os.path.isfile(p)]
    for p in sorted(files):
        h.update(os.path.relpath(p, APP).encode('utf-8') + b'\0')
        with open(p, 'rb') as f:
            h.update(hashlib.sha1(f.read()).digest())
    return h.hexdigest()


if __name__ == '__main__':
    os.makedirs(DST, exist_ok=True)
    self_hash = tool_hash()
    srcs = sorted(glob.glob(os.path.join(SRC, '*.md')))
    assert srcs, SRC
    for src in srcs:
        base = os.path.splitext(os.path.basename(src))[0]
        dst, stamp = os.path.join(DST, base + '.html'), os.path.join(DST, base + '.sha1')
        raw = open(src, 'rb').read()
        key = hashlib.sha1(raw).hexdigest() + ' ' + self_hash
        if os.path.exists(dst) and os.path.exists(stamp) and open(stamp).read().strip() == key:
            print(f'[skip] {base}.html', file=sys.stderr)
            continue
        t = time.time()
        html = convert(raw.decode('utf-8'))
        with open(dst, 'w', encoding='utf-8') as f:
            f.write(html)
        with open(stamp, 'w') as f:
            f.write(key + '\n')
        print(f'[done] {base}.html {time.time()-t:.1f}s {len(html)} bytes', file=sys.stderr)
