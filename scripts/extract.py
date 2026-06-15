#!/usr/bin/env python3
"""通用 extractor 骨架 —— 按 configs/<site>.yaml 适配新站。

工作流程:
  1. 读 configs/<site>.yaml（站点配置 + 选择器 + 噪音规则）
  2. 读 --ids 文件（一行一个 article ID）
  3. 对每篇: 抓 HTML（缓存到 raw/）→ extract() → 写 .txt
  4. 写 manifest.jsonl + report.txt + failures.json

用法:
  python3 scripts/extract.py --config configs/gushi365.yaml \
      --ids sample_100_ids.txt --out corpus/

新站适配:
  1. 复制 configs/gushi365.yaml → configs/<新站>.yaml
  2. 改 site.* / selectors / noise 三个段
  3. 跑 extract.py 验证 4 项零残留
"""
import argparse
import re
import sys
import json
import time
import html
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

# ──────────────────────────── 依赖 ────────────────────────────
try:
    import yaml
except ImportError:
    print("需要 PyYAML: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


# ──────────────────────────── 网络 ────────────────────────────
def fetch(url: str, ua: str, retries: int = 3, timeout: int = 30):
    """抓 URL，返回 (status, html_text or error_msg)。"""
    req = urllib.request.Request(url, headers={
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml",
    })
    for i in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            if i == retries - 1:
                return 0, f"ERR: {e}"
            time.sleep(1.5 * (i + 1))
    return 0, "ERR: exhausted"


def load_ids(path: Path):
    """读 --ids 文件，返回 list[int]。"""
    return [int(x) for x in path.read_text().split() if x.strip().isdigit()]


def slugify(s: str, maxlen: int = 40) -> str:
    """生成文件名安全的 slug（保留中文）。"""
    s = re.sub(r"[^\w\u4e00-\u9fff\-]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:maxlen] or "untitled"


# ──────────────────────────── 提取（核心）────────────────────────────
def extract(html_text: str, cfg: dict) -> Optional[dict]:
    """从一篇页面提取 {title, body, author, date, category, tags}。

    返回 None = 失败（编码错位 / 找不到正文容器等）。

    噪音清理顺序（**重要**：先按结构切，再按关键词过滤）:
      1. 用 selectors.content 截出正文容器（**不包含 <textarea> 之后**）
      2. 段落级过滤:
         - <p>&nbsp;</p> 空段跳过
         - 页内重复标题跳过（== 主标题）
         - 短段 + 命中噪音关键词 → 砍
         - 含 ｜（围栏链接字符） → 整段砍
         - 正则匹配噪音模式 → 整段砍
      3. 段落内清理:
         - 去 HTML 标签
         - HTML 实体反转义
         - 多空白合一
    """
    sels = cfg["selectors"]
    noise = cfg.get("noise", {})

    # ── 标题
    m = re.search(rf"<h1[^>]*class=\"{sels['title_class']}\"[^>]*>([^<]+)</h1>",
                  html_text) if sels.get("title_class") else \
         re.search(r"<title>([^<]+)</title>", html_text)
    if not m:
        return None
    title = html.unescape(m.group(1)).strip()
    # 去掉 <title> 里的站点后缀
    title = re.sub(r"\s*[-_|].*$", "", title).strip() or "untitled"

    # ── 正文容器（**截到 <textarea> 或容器结束**）
    content_pat = re.compile(
        rf'<div class="{sels["content_class"]}">(.*?)(?:<textarea|</div>\s*</div><!--)',
        re.S
    )
    m = content_pat.search(html_text)
    if not m:
        # 容错：截到第一个 </div>
        m = re.search(rf'<div class="{sels["content_class"]}">(.*?)</div>',
                      html_text, re.S)
        if not m:
            return None
    body_html = m.group(1)

    # ── 段落提取 + 过滤
    paras = re.findall(r"<p[^>]*>(.*?)</p>", body_html, re.S)

    NOISE_KEYWORDS = tuple(noise.get("keywords", []))
    NOISE_PATTERNS = [re.compile(p, re.S) for p in noise.get("patterns", [])]

    cleaned = []
    for p in paras:
        # 整段级：围栏字符 + 模式命中 → 砍
        if any(ch in p for ch in noise.get("fence_chars", [])):
            continue
        if any(pat.search(p) for pat in NOISE_PATTERNS):
            continue

        # 段落内清理
        text = re.sub(r"<[^>]+>", "", p)
        text = html.unescape(text)
        text = re.sub(r"\s+", " ", text).strip()

        # 跳过空段 / 非中文段
        if not text or text in ("&nbsp;", "\xa0"):
            continue
        if len(text) <= 4:
            continue

        # 页内重复标题
        if text == title:
            continue

        # 关键词命中 + 长度限制 → 砍
        if NOISE_KEYWORDS:
            if len(text) < 60 and any(k in text for k in NOISE_KEYWORDS):
                continue
            if any(k in text for k in NOISE_KEYWORDS) and len(text) < 200:
                continue

        cleaned.append(text)

    if not cleaned:
        return None
    body = "\n\n".join(cleaned)

    # ── 元信息（可选，按站定制）
    author = date = category = ""
    tags = []
    meta = cfg.get("meta_selectors", {})
    if meta.get("author_date_pattern"):
        fm = re.search(meta["author_date_pattern"], html_text)
        if fm:
            author = fm.group(1).strip()
            date = fm.group(2).strip()
    if meta.get("category_tag_pattern"):
        cm = re.search(meta["category_tag_pattern"], html_text, re.S)
        if cm:
            category = html.unescape(cm.group(1)).strip()
            tags = [html.unescape(t).strip()
                    for t in re.findall(r">([^<]+)</a>", cm.group(2))]

    return {
        "title": title,
        "body": body,
        "author": author,
        "date": date,
        "category": category,
        "tags": tags,
    }


# ──────────────────────────── 写文件 ────────────────────────────
def write_article(out_dir: Path, sid: int, info: dict, header_format: str = "标题：{title}\n\n"):
    """按 header_format 写 .txt，返回文件路径。"""
    slug = slugify(info["title"])
    out = out_dir / f"{sid:06d}_{slug}.txt"
    header = header_format.format(**info) if header_format else ""
    out.write_text(header + info["body"] + "\n")
    return out


# ──────────────────────────── 主流程 ────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="configs/<site>.yaml")
    ap.add_argument("--ids", required=True, help="一行一个 article ID 的文件")
    ap.add_argument("--out", default="corpus/", help="输出目录")
    ap.add_argument("--raw", default="raw/", help="HTML 缓存目录")
    ap.add_argument("--sleep", type=float, default=0.3, help="每篇间隔秒数")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text())
    site = cfg["site"]
    print(f"[config] site={site['name']} base={site['base_url']}")

    out = Path(args.out); out.mkdir(exist_ok=True, parents=True)
    raw = Path(args.raw); raw.mkdir(exist_ok=True, parents=True)
    ids = load_ids(Path(args.ids))
    print(f"[ids] {len(ids)} to fetch")

    manifest, failures, char_counts = [], [], []
    UA = site.get("user_agent",
                  "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0")
    HEADER_FMT = cfg.get("output", {}).get("header_format",
                                           "标题：{title}\n\n")

    for i, sid in enumerate(ids, 1):
        url = site["article_url_pattern"].format(id=sid)
        url = url if url.startswith("http") else site["base_url"].rstrip("/") + url

        raw_path = raw / f"{sid}.html"
        if raw_path.exists():
            html_text = raw_path.read_text()
        else:
            status, html_text = fetch(url, UA)
            if status != 200 or html_text.startswith("ERR"):
                failures.append({"id": sid, "url": url, "error": html_text[:80]})
                print(f"[{i}/{len(ids)}] {sid} HTTP/FAIL: {html_text[:60]}")
                continue
            raw_path.write_text(html_text)
            time.sleep(args.sleep)

        info = extract(html_text, cfg)
        if info is None:
            failures.append({"id": sid, "url": url, "error": "extract failed"})
            print(f"[{i}/{len(ids)}] {sid} extract FAIL")
            continue

        path = write_article(out, sid, info, HEADER_FMT)
        char_counts.append(len(info["body"]))
        manifest.append({
            "id": sid, "file": path.name, **info,
            "url": url, "char_count": len(info["body"]),
        })
        if i % 10 == 0:
            print(f"[{i}/{len(ids)}] ok, last={sid} chars={len(info['body'])}")

    # 写元数据
    Path("manifest.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in manifest) + "\n")
    Path("failures.json").write_text(
        json.dumps(failures, ensure_ascii=False, indent=2))

    # 写报告
    if char_counts:
        n = len(char_counts)
        char_counts_sorted = sorted(char_counts)
        report = [
            f"OK: {n} / 抽 {len(ids)} 个 ID",
            f"fail: {len(failures)}",
            f"字符数: min={char_counts_sorted[0]} median={char_counts_sorted[n//2]} "
            f"max={char_counts_sorted[-1]} mean={sum(char_counts)//n}",
            "",
            "失败列表:",
        ]
        for f in failures:
            report.append(f"  - [{f['id']}] {f['error']}")
        Path("report.txt").write_text("\n".join(report))
        print("\n=== report ===")
        print("\n".join(report))


if __name__ == "__main__":
    main()