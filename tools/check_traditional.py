#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Report Simplified-only characters in a Traditional Chinese document.

    python tools/check_traditional.py README.md [more.md ...]

The README of this project is written in Traditional Chinese, and a stray
Simplified character is easy to introduce and hard to notice. This script scans
for characters that exist ONLY in the Simplified set and prints every hit with
its line and column, so the document can be fixed and then re-checked.

Exit codes: 0 clean / 1 hits found / 2 bad usage.

Notes on the character set
--------------------------
The set below lists characters whose Traditional counterpart is a DIFFERENT
character (们/們, 为/為, 说/說 ...). Characters that are identical in both
scripts (境, 入, 后, 里, 面, 台 ...) are deliberately absent: including them
would produce nothing but false positives. `后` and `里` are valid Traditional
in their own right (皇后, 公里), which is exactly why they are not listed.

The two PDF manuals in this repository keep Simplified file names
(mqtt-CLI-使用说明.pdf), so `IGNORE_SUBSTRINGS` skips lines that merely name
them. A genuine Simplified character elsewhere on the same line is still
reported.

Quoting the interface verbatim
-----------------------------
The web panel's own UI is Simplified Chinese. Where this document quotes a
button or checkbox EXACTLY as it appears on screen, so that a reader can find
it, the line carries an explicit `<!-- zh-Hans -->` marker. Only marked lines
are skipped -- this keeps the exception visible in the source instead of
silently widening the ignore list.
"""

from __future__ import annotations

import sys

# Characters that have a distinct Traditional form.
SIMPLIFIED_ONLY = (
    "们对来学样应让认为语读记录设网连电话数据线权传缓队监浏览计算务业达过运"
    "术断变换类观统员构议严检测调询请谁讲吗着别页级层汇总结处图阶际联终经给"
    "绝继维缩罗职脑艺节药获蓝虑虽规触订讨训讯访诀评识诉词译诗诚诞详误诸课"
    "谈谋谐谓谜谢谣谦谨谱负责贤败账贩贪贫购贯贷贸费贺资赋赌赎赏赐赔赖赚赛"
    "赞赠赢够综爱亲觉习书车东马鸟鱼龙岁万亿举义头顺须顾预领风飞饮馆饭鲜鸡"
    "鸭猪猫兽虫蚁贝货贵买卖质织杂号键盘频宽带络缆钟针铁电压闭启动静态状团"
    "组织编码权当双单开关个应说着这里会从内见门问题时后无复"
)

# Lines that merely name a file whose name is legitimately Simplified, or that
# quote the Simplified interface verbatim on purpose.
IGNORE_SUBSTRINGS = ("使用说明.pdf", "<!-- zh-Hans -->")


def scan(path: str) -> list[tuple[int, int, str, str]]:
    hits: list[tuple[int, int, str, str]] = []
    with open(path, encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if any(skip in line for skip in IGNORE_SUBSTRINGS):
                continue
            for column, char in enumerate(line, 1):
                if char in SIMPLIFIED_ONLY:
                    hits.append((number, column, char, line.rstrip()))
    return hits


def main(argv: list[str]) -> int:
    targets = argv[1:]
    if not targets:
        print(__doc__.strip().splitlines()[2].strip(), file=sys.stderr)
        return 2

    total = 0
    for path in targets:
        try:
            hits = scan(path)
        except OSError as exc:
            print("check_traditional: %s: %s" % (path, exc), file=sys.stderr)
            return 2
        for number, column, char, line in hits:
            print("%s:%d:%d: Simplified %r in: %s" % (path, number, column, char, line))
        print("%s: %d Simplified character(s)" % (path, len(hits)))
        total += len(hits)

    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
