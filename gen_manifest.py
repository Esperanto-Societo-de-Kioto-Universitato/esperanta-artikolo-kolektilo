# -*- coding: utf-8 -*-
"""
gen_manifest.py

取得文書フォルダ (*.jsonl 群) を走査して MANIFEST.md を生成する。
記事本文はコード用リポジトリ (kolektilo) には含めず (取得文書*/ ごと ignore)、
sync_korpuso.sh でコーパスリポジトリ (esperanta-artikolo-korpuso) に同期する。
「何がどれだけ入っているか」は各フォルダ内のこの MANIFEST.md に記録する。
フォルダの内容を変更したら再生成すること。

使い方:
    python gen_manifest.py 取得文書ekde20260401 [--notes notes.md]

--notes で渡した Markdown 断片は「備考」節としてそのまま埋め込まれる。
--notes を省くと、既存の MANIFEST.md の「備考」節をそのまま引き継ぐ
(備考の原本は MANIFEST.md 自身。書き換えるときは節の本文を別ファイルに切り出して
編集し --notes で渡す。空のファイルを渡すと備考節を消す)。
"""
from __future__ import annotations

import argparse
import json
import os
import re
from collections import defaultdict
from datetime import datetime
from glob import glob

FILE_RE = re.compile(r"^(?P<site>.+?)_(?P<label>\d{4}-\d{2}|\d{4}|unknown)\.jsonl$")
NOTES_HEADING_RE = re.compile(r"^## 備考[ \t]*\n", re.M)


def existing_notes(manifest_path: str) -> str:
    """既存 MANIFEST.md の「備考」節の本文を返す (ファイルや節がなければ空文字)。"""
    if not os.path.isfile(manifest_path):
        return ""
    with open(manifest_path, encoding="utf-8") as f:
        text = f.read()
    m = NOTES_HEADING_RE.search(text)
    if not m:
        return ""
    # 備考は常に最後の節として書くので、見出し以降をすべて備考とみなす
    # (備考の中に ### や ## の見出しがあってもそのまま引き継ぐ)
    return text[m.end():].lstrip("\n").rstrip()


def main() -> None:
    p = argparse.ArgumentParser(description="取得文書フォルダの MANIFEST.md を生成")
    p.add_argument("folder", help="対象フォルダ")
    p.add_argument(
        "--notes",
        default=None,
        help="備考として埋め込む Markdown ファイル (省略時は既存 MANIFEST.md の備考を引き継ぐ)",
    )
    args = p.parse_args()

    out_path = os.path.join(args.folder, "MANIFEST.md")
    if args.notes is not None:
        with open(args.notes, encoding="utf-8") as f:
            notes = f.read().rstrip()
    else:
        notes = existing_notes(out_path)
        if notes:
            print(f"[INFO] 既存の {out_path} の備考を引き継ぎます")

    counts: dict = defaultdict(dict)      # site -> label -> n
    date_range: dict = {}                 # site -> [min, max]
    undated: dict = defaultdict(int)      # site -> n

    # 記事セット (site_label.{md,txt,csv,jsonl}) 以外の同梱ファイルも記録する
    article_set_re = re.compile(r"^.+?_(\d{4}-\d{2}|\d{4}|unknown)\.(md|txt|csv|jsonl)$")
    extra_files = [
        name
        for name in sorted(os.listdir(args.folder))
        if os.path.isfile(os.path.join(args.folder, name))
        and not article_set_re.match(name)
        and name != "MANIFEST.md"
    ]

    for path in sorted(glob(os.path.join(args.folder, "*.jsonl"))):
        name = os.path.basename(path)
        m = FILE_RE.match(name)
        if not m:
            continue
        site, label = m.group("site"), m.group("label")
        n = 0
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            n += 1
            pub = (r.get("published") or "")[:10]
            if pub:
                lo, hi = date_range.get(site, (pub, pub))
                date_range[site] = (min(lo, pub), max(hi, pub))
            else:
                undated[site] += 1
        counts[site][label] = n

    labels = sorted({l for site in counts.values() for l in site})
    sites = sorted(counts)
    total = sum(sum(site.values()) for site in counts.values())

    lines = []
    lines.append(f"# MANIFEST — {os.path.basename(os.path.abspath(args.folder))}")
    lines.append("")
    lines.append(f"- 生成日: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"- 総記事数: **{total}**")
    lines.append("- 各記事は md / txt / csv / jsonl の4形式で保存（記事数は jsonl 行数）")
    lines.append("- 記事本文はコーパスリポジトリ esperanta-artikolo-korpuso で管理（コード用リポジトリ kolektilo には含めない）")
    lines.append("- 各記事の著作権は掲載サイト・著者に帰属する（出典 URL は各記事に記載）")
    lines.append("")
    lines.append("## サイト × 月 記事数")
    lines.append("")
    lines.append("| サイト | " + " | ".join(labels) + " | 合計 | 日付範囲 |")
    lines.append("|---" * (len(labels) + 3) + "|")
    for site in sites:
        row = [str(counts[site].get(l, "")) for l in labels]
        subtotal = sum(counts[site].values())
        lo, hi = date_range.get(site, ("-", "-"))
        rng = f"{lo} 〜 {hi}" if lo != "-" else "-"
        if undated.get(site):
            rng += f"（日付なし {undated[site]} 件含む）"
        lines.append(f"| {site} | " + " | ".join(row) + f" | **{subtotal}** | {rng} |")
    lines.append("")
    if extra_files:
        lines.append("## その他のファイル")
        lines.append("")
        for name in extra_files:
            lines.append(f"- {name}")
        lines.append("")
    if notes:
        lines.append("## 備考")
        lines.append("")
        lines.append(notes)
        lines.append("")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"[DONE] {out_path} ({total} 記事)")


if __name__ == "__main__":
    main()
