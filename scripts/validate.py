#!/usr/bin/env python3
"""4 项零残留扫描 —— 验证 extractor 输出干净度。

用法:
  python3 scripts/validate.py corpus/ <site-domain>

退出码: 0 = 全过, 1 = 有残留
"""
import sys
import re
from pathlib import Path
from collections import defaultdict


def scan(corpus_dir: Path, site_domain: str, noise_keywords=None):
    """返回 dict {check_name: [files_with_issue]}。"""
    noise_keywords = noise_keywords or [
        "手机用户点击", "电脑用户", "点击这里", "朋友圈",
        "收藏或分享", "二维码", "微信", "QQ空间",
    ]
    files = list(corpus_dir.glob("*.txt"))
    issues = defaultdict(list)

    fence = "｜"  # gushi365 推荐链接围栏

    for f in files:
        text = f.read_text()
        # 1. 推荐链接围栏
        if fence in text:
            issues["fence_chars"].append(f.name)
        # 2. 内链残留
        if site_domain in text:
            issues["internal_link"].append(f.name)
        # 3. 噪音关键词
        hits = [k for k in noise_keywords if k in text]
        if hits:
            issues["noise_keywords"].append(f"{f.name} ({', '.join(hits)})")
        # 4. 不该有的头部
        bad_headers = re.findall(r"^(作者|日期|分类|标签)：", text, re.M)
        if bad_headers:
            issues["unexpected_header"].append(f"{f.name} ({', '.join(bad_headers)})")

    return issues, len(files)


def main():
    if len(sys.argv) < 3:
        print("用法: validate.py <corpus_dir> <site_domain> [noise_keywords.txt]",
              file=sys.stderr)
        sys.exit(2)

    corpus = Path(sys.argv[1])
    domain = sys.argv[2]

    noise_kw = None
    if len(sys.argv) > 3:
        noise_kw = Path(sys.argv[3]).read_text().split()

    issues, total = scan(corpus, domain, noise_kw)

    print(f"扫描 {total} 篇 .txt（domain={domain}）\n")
    checks = ["fence_chars", "internal_link", "noise_keywords", "unexpected_header"]
    labels = {
        "fence_chars": "推荐链接围栏（｜）残留",
        "internal_link": f"内链残留（含 {domain}）",
        "noise_keywords": "噪音关键词残留",
        "unexpected_header": "不该有的元信息头部",
    }
    fail = False
    for c in checks:
        n = len(issues.get(c, []))
        status = "✅" if n == 0 else "❌"
        print(f"  {status} {labels[c]}: {n} 篇")
        if n > 0:
            for f in issues[c][:5]:
                print(f"      - {f}")
            if n > 5:
                print(f"      ... 还有 {n-5} 篇")
            fail = True

    print()
    if fail:
        print("❌ 有残留，需修 extractor 重跑")
        sys.exit(1)
    print("✅ 全部 4 项零残留，语料可入库")


if __name__ == "__main__":
    main()