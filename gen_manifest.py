# -*- coding: utf-8 -*-
"""
gen_manifest.py

取得文書フォルダ (*.jsonl 群) を走査して MANIFEST.md を生成する。
記事本文は著作権保護のため git 管理しないので、代わりにこのマニフェストが
「何がどれだけ入っているか」を repo 側から参照できる記録になる。

使い方:
    python gen_manifest.py 取得文書ekde20260401 [--notes notes.md]

--notes で渡した Markdown 断片は「備考」節としてそのまま埋め込まれる。
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


def main() -> None:
    p = argparse.ArgumentParser(description="取得文書フォルダの MANIFEST.md を生成")
    p.add_argument("folder", help="対象フォルダ")
    p.add_argument("--notes", default=None, help="備考として埋め込む Markdown ファイル")
    args = p.parse_args()

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
    lines.append("- 記事本文は著作権保護のため git 管理外（このマニフェストのみ記録用）")
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
    if args.notes:
        lines.append("## 備考")
        lines.append("")
        lines.append(open(args.notes, encoding="utf-8").read().rstrip())
        lines.append("")

    out_path = os.path.join(args.folder, "MANIFEST.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"[DONE] {out_path} ({total} 記事)")


if __name__ == "__main__":
    main()
