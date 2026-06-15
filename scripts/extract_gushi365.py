#!/usr/bin/env python3
"""提取 gushi365 睡前故事 → 裸 .txt 语料库。

输入: sample_100_ids.txt (一行一个 info id)
输出: corpus/<id>_<title_slug>.txt  (纯正文)
      manifest.jsonl (一行一篇元信息)
      report.txt    (统计)
"""
import re
import sys
import json
import time
import html
import urllib.request
import urllib.error
from pathlib import Path

BASE_URL = "https://www.gushi365.com/info/{}.html"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
ROOT = Path("/tmp/gushi365_corpus")
CORPUS = ROOT / "corpus"
RAW = ROOT / "raw"
CORPUS.mkdir(exist_ok=True)
RAW.mkdir(exist_ok=True)


def fetch(url, retries=3):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"})
    for i in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, r.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            if i == retries - 1:
                return 0, f"ERR: {e}"
            time.sleep(1.5 * (i + 1))
    return 0, "ERR: exhausted"


def slugify(s, maxlen=40):
    s = re.sub(r"[^\w\u4e00-\u9fff\-]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:maxlen] or "untitled"


def extract(html_text):
    """从一篇页面提取 {title, body, author, date, category, tags}。
    返回 None 表示失败。

    噪音处理:
      1. <textarea> 之前 = 正文；之后 = 分享/二维码区，全砍
      2. <p>&nbsp;</p> 空段跳过
      3. <h2><span class="entry-title"> 页内重复标题，跳过
      4. 含"点击""收藏""分享""扫描""二维码""朋友圈""浏览器底部"等关键词的 <p> 整段砍
    """
    # 标题
    m = re.search(r'<h1 class="entry-title">([^<]+)</h1>', html_text)
    if not m:
        return None
    title = html.unescape(m.group(1)).strip()

    # 正文容器（先按标准结构取）
    m = re.search(r'<div class="single-content">(.*?)(?:<textarea|</div>\s*</div><!-- \.entry-content)',
                  html_text, re.S)
    if not m:
        m = re.search(r'<div class="single-content">(.*?)</div>', html_text, re.S)
        if not m:
            return None
    body_html = m.group(1)

    # 提取所有 <p>...</p>
    paras = re.findall(r"<p[^>]*>(.*?)</p>", body_html, re.S)

    NOISE_KEYWORDS = ("点击", "收藏", "分享", "扫描", "二维码", "朋友圈",
                      "浏览器底部", "右上角", "订阅", "复制好", "已复制",
                      "粘贴", "微博", "微信", "QQ空间", "点击这里")
    # 推荐区链接的域名特征（多个 ｜ 围起的 gushi365.com/info/<id> 链接）
    RECOMMEND_RE = re.compile(r"｜.*?gushi365\.com/info/\d+\.html.*?｜", re.S)

    cleaned = []
    for p in paras:
        # 推荐区段特征：包含 ｜ 围起的多个内链。简单粗暴：含 ｜ 就整段砍
        if "｜" in p:
            continue

        # 去掉内嵌标签
        text = re.sub(r"<[^>]+>", "", p)
        text = html.unescape(text)
        text = re.sub(r"\s+", " ", text).strip()

        # 跳过空段
        if not text or text in ("&nbsp;", "\xa0"):
            continue
        # 跳过页内重复标题（h2 里的标题）
        if text == title:
            continue
        # 跳过噪音段（关键词命中 + 内容像广告短句）
        if len(text) < 60 and any(k in text for k in NOISE_KEYWORDS):
            continue
        if any(k in text for k in NOISE_KEYWORDS) and len(text) < 200:
            continue
        # 兜底：如果段落全是 ｜ 和标题（残留），砍
        if text.replace("｜", "").replace(" ", "") == "":
            continue
        if len(text) > 4:
            cleaned.append(text)

    if not cleaned:
        return None
    body = "\n\n".join(cleaned)

    # 元信息
    author = date = category = ""
    tags = []
    fm = re.search(r"<div class=\"single-cat\">作者：([^<\s]+)\s*日期：([^<]+)</div>", html_text)
    if fm:
        author = fm.group(1).strip()
        date = fm.group(2).strip()
    cm = re.search(r'<div class="single-cat">所属分类：<a[^>]+>([^<]+)</a>\s*标签：(.*?)</div>', html_text, re.S)
    if cm:
        category = html.unescape(cm.group(1)).strip()
        tag_m = re.findall(r'>([^<]+)</a>', cm.group(2))
        tags = [html.unescape(t).strip() for t in tag_m]

    return {
        "title": title,
        "body": body,
        "author": author,
        "date": date,
        "category": category,
        "tags": tags,
    }


def main():
    ids_file = ROOT / "sample_100_ids.txt"
    if not ids_file.exists():
        print("no sample_100_ids.txt", file=sys.stderr)
        sys.exit(1)
    ids = [int(x) for x in ids_file.read_text().split() if x.strip().isdigit()]
    print(f"to fetch: {len(ids)}")

    manifest = []
    failures = []
    char_counts = []

    for i, sid in enumerate(ids, 1):
        url = BASE_URL.format(sid)
        # 先看是否已下载
        raw_path = RAW / f"{sid}.html"
        if raw_path.exists():
            html_text = raw_path.read_text()
        else:
            status, html_text = fetch(url)
            if status != 200 or html_text.startswith("ERR"):
                failures.append({"id": sid, "url": url, "error": html_text[:80]})
                print(f"[{i}/{len(ids)}] {sid} FAIL: {html_text[:60]}")
                continue
            raw_path.write_text(html_text)
            time.sleep(0.3)  # 限速

        info = extract(html_text)
        if info is None:
            failures.append({"id": sid, "url": url, "error": "extract failed"})
            print(f"[{i}/{len(ids)}] {sid} extract FAIL")
            continue

        # 写 .txt（只保留标题作为头部，作者/日期/分类/标签都不要）
        slug = slugify(info["title"])
        out = CORPUS / f"{sid:06d}_{slug}.txt"
        out.write_text(f"标题：{info['title']}\n\n{info['body']}\n")
        # 统计字符数只算正文（不含头部）
        body_chars = len(info["body"])
        char_counts.append(body_chars)
        manifest.append({
            "id": sid,
            "file": out.name,
            **info,
            "url": url,
            "char_count": body_chars,
        })
        if i % 10 == 0:
            print(f"[{i}/{len(ids)}] ok, last={sid} chars={len(info['body'])}")

    # 写 manifest + report
    (ROOT / "manifest.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in manifest) + "\n"
    )
    (ROOT / "failures.json").write_text(json.dumps(failures, ensure_ascii=False, indent=2))

    if char_counts:
        char_counts.sort()
        n = len(char_counts)
        report = [
            f"OK: {n} / 抽 {len(ids)} 个 ID",
            f"fail: {len(failures)}",
            f"字符数: min={char_counts[0]} median={char_counts[n//2]} max={char_counts[-1]} mean={sum(char_counts)//n}",
            f"分桶: <200字={sum(1 for c in char_counts if c<200)} "
            f"200-500={sum(1 for c in char_counts if 200<=c<500)} "
            f"500-1000={sum(1 for c in char_counts if 500<=c<1000)} "
            f"1000-2000={sum(1 for c in char_counts if 1000<=c<2000)} "
            f">=2000={sum(1 for c in char_counts if c>=2000)}",
            "",
            "前 5 篇示例标题:",
        ]
        for r in manifest[:5]:
            report.append(f"  - [{r['id']}] {r['title']}  ({r['char_count']} 字, 作者={r['author']})")
        report.append("")
        report.append("失败列表:")
        for f in failures:
            report.append(f"  - [{f['id']}] {f['error']}")
        (ROOT / "report.txt").write_text("\n".join(report))
        print("\n=== report ===")
        print("\n".join(report))


if __name__ == "__main__":
    main()