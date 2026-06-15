---
name: children-story-corpus-crawler
description: 爬取中文儿童故事网站（gushi365 / storymami / runruneando 等），清洗站点噪音，输出纯文本语料库。当用户说"爬 XXX 网站故事""下载睡前故事/童话""做儿童故事语料库""X 网站的故事做训练素材"时触发。新站接入只需写一个 configs/<site>.yaml + 复用 scripts/extract.py 骨架 + 走 5 步 SOP。已验证站点：gushi365.com（4400+ 篇睡前故事）。
license: MIT
metadata:
  hermes:
    tags: [crawler, corpus, chinese, children-stories, training-data]
    related_skills: [github-repo-management]
    version: 1.0.0
    notes: 5 步 SOP + 通用 extractor 骨架 + 已验证 gushi365 配置。开发版在 ~/Github/children-story-corpus-crawler/，安装版在 ~/.hermes/skills/children-story-corpus-crawler/。
---

# Children Story Corpus Crawler

> **做什么**：爬中文儿童故事网站（睡前故事/童话/绘本/寓言），提取纯文本正文，清洗站点噪音，输出 `.txt` 语料库供训练或阅读。
>
> **怎么用**：① 写 `configs/<site>.yaml` ② 跑 `scripts/extract.py` ③ 走 5 步 SOP ④ 验证后全量。

---

## 何时用

**触发场景**：
- "爬 gushi365 / storymami / runruneando 上的睡前故事"
- "从 XXX 网站下载儿童故事做训练素材"
- "做一个儿童故事语料库"
- "X 网站上的故事，做训练用"

**不用**：
- 爬非中文 / 非儿童向 → 通用爬虫框架
- 爬单篇人工阅读 → 直接 `web_extract`
- 爬论坛 / 评论 / 视频 → 结构不同

---

## 5 步 SOP（任何站必走，跳步必出错）

```
Step 1 摸底       站名 vs 实际内容？有没有 API/RSS/sitemap？    [决策点]
Step 2 单篇       抓 3 篇摸 HTML 结构，识别选择器 + 噪音模式   [必须先过]
Step 3 摸分页     列表分页规则？真实末页 = 多少？              [必须先过]
Step 4 样本       抓 50-100 篇 → 跑 4 项零残留扫描 → 用户确认 [质量门]
Step 5 全量       分批抓 + 实时校验 + 失败率报警 → 出库         [执行]
```

**核心经验**：噪音模式是按站定制的，**不要照搬 gushi365 的清单**——每个新站都要在 Step 2 重新识别。

---

## Step 1: 摸底

**不通过不准进 Step 2**——这是 qigushi.com 案例最痛的教训：站名"儿童故事网"，实际 90% 是橙光游戏攻略。

**先看首页 HTML 是不是 WAF 拦截页**——如果首页是 JS + cookie 验证，curl 永远拿不到内容（gushi365 v1.1.1 踩坑）。

```bash
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0"
mkdir -p /tmp/<site>_corpus && cd /tmp/<site>_corpus
curl -sSL -A "$UA" "https://<目标站>/" -o home.html
curl -sSL -A "$UA" "https://<目标站>/map.html" -o sitemap.html  # 或 sitemap.xml

# ⚠️ WAF 探测 — 看首页是不是 JS + cookie 验证页
if grep -q "Browser security check\|noscript.*JavaScript\|document.cookie" home.html; then
  echo "⚠️ WAF 拦截 — curl 拿不到内容，需要 browser_navigate 或换站"
  exit 1
fi

# 抽样 5-10 个内页
grep -oE 'href="[^"]+\.html"' home.html | sort -u | head -10 > urls.txt
for url in $(cat urls.txt); do
  curl -sSL -A "$UA" "$url" -o "sample_$(basename $url)"
done
```

**判断三选一**：
- ✅ 真是儿童故事 → 进 Step 2
- ⚠️ 名实不符 → `web_search` 找替代站（见下）
- ✅ 有官方 API/RSS → 直接调，跳过 Step 2-3

**已验证可用站点**（**注意 WAF 状态**）：
| 站 | 路径 | 内容 |
|---|---|---|
| `gushi365.com/shuiqiangushi/` | `/shuiqiangushi/index_N.html` | 睡前故事（**2101 篇已爬** ✅）|
| `gushi365.com/tonghuagushi/` | `/tonghuagushi/index_N.html` | 童话（探测到 1271 URL，**WAF 拦截** ⚠️）|
| `gushi365.com` 其他 11 个栏目 | — | **WAF 拦截** ⚠️ |
| `storymami.com/cn` | `/cn/?page=N` | 睡前故事（按类型/长度） |
| `runruneando.com/zh-cn` | `/zh-cn/gushi/` | 睡前故事（按年龄分级） |

---

## Step 2: 单篇实测

```bash
# 抓首页前 3 篇
for id in 33 97 209; do
  curl -sSL -A "$UA" "https://<站>/info/${id}.html" -o "raw_${id}.html"
done

# 定位关键元素（用 grep）
grep -nE '<h1|entry-title|single-content|class="author"|datetime|class="post-date"|single-cat' raw_33.html | head -20
```

**必找的 5 类元素**：

| 元素 | 典型标识 |
|---|---|
| 标题 | `<h1 class="entry-title">` / `<title>` |
| 正文容器 | `<div class="single-content">` / `<article>` |
| 作者 | `作者：XXX` 文字 |
| 发布日期 | `日期：XXX` / `<time datetime>` |
| 分类/标签 | `class="cat-tag"` |

**退出条件**：extract 返回 `body` ≥ 100 字纯文本，**无任何推广/分享/扫码文字**。

---

## Step 3: 摸分页

**首页分页显示 ≠ 真实末页**（gushi365 案例：首页显示 10 页，真实 113 页）。

**分页末页 ≠ 真实总量**（gushi365 案例：估算 113 × 39 = 4400 篇，实际只有 2140 篇）。

```bash
# 看首页分页区
grep -oE 'class="page-numbers" href="[^"]+"' home.html | head -10

# 二分探测末页（首页可能截断显示）
for p in 50 100 150 200; do
  curl -sSL -A "$UA" -o /dev/null -w "%{http_code}\n" "https://<站>/<列表路径>/index_${p}.html"
done

# 扫全部 N 页拿真实 URL 列表（**必须做，不要按 ID 范围试**）
for p in $(seq 1 113); do
  if [ $p -eq 1 ]; then URL="https://<站>/<列表路径>/index.html"
  else URL="https://<站>/<列表路径>/index_${p}.html"; fi
  curl -sSL -A "$UA" "$URL" | grep -oE 'href="<URL_PATTERN>"|<URL_PATTERN>"' | sort -u
done | sort -u > all_urls.txt
sed 's|.*/info/||; s|\.html||; s|"||g' all_urls.txt > all_ids.txt
# 真实 ID 数 = wc -l all_ids.txt
```

**常见分页 URL 模式**：
- WordPress 默认：`/category/page/N/` 或 `/category/?paged=N`
- WordPress 自定义：`/shuiqiangushi/index_N.html`（gushi365）
- Discuz：`/forum-N-1.html`
- 自研：`/list_N.html`

**反模式**：
- ❌ 按 ID 范围 `[800..18700]` 批量试——ID 不连续，13000+ 浪费的 404 请求
- ❌ 按 `末页 × 平均URL数` 估算总量——单页 URL 数量方差大，估算可能偏高 2 倍

---

## Step 4: 样本（**质量门，必须通过**）

**目的**：跑全量前用 50-100 篇验证 extractor 的噪音清洗能力。

### 4.1 跨年代选样（**不要只爬首页**）

首页是最新模板，旧文可能是旧模板：

```python
ids = sorted(all_known_ids)
step = max(1, len(ids) // 100)
sample = sorted(ids)[::step][:100]
```

### 4.2 跑 extractor

```bash
python3 scripts/extract.py --config configs/<site>.yaml --ids sample_100_ids.txt --out corpus/
```

### 4.3 4 项零残留扫描（**必须全过**）

```bash
# 1. 推荐链接段（含 ｜ 字符）
grep -l "｜" corpus/*.txt | wc -l   # 必须 0

# 2. 内链残留
grep -l "<站域名>" corpus/*.txt | wc -l   # 必须 0

# 3. 推广段（按站定制关键词）
grep -l -E "<按站定制的噪音关键词>" corpus/*.txt | wc -l   # 必须 0

# 4. 不该有的头部（按用户要求）
grep -lE "^作者：|^日期：|^分类：|^标签：" corpus/*.txt | wc -l   # 必须 0
```

**或跑 `scripts/validate.py` 自动扫**。

### 4.4 字数分布

- 中位 **500-1500 字** 算正常
- 中位 < 200 → extractor 漏抽正文段
- 有 < 50 字样本 → 模板识别失败
- 字数分布双峰 → 可能 2 种模板混在一起

### 4.5 用户确认

把样本包发用户看。**用户反馈噪音 → 改 extractor → 重跑样本 → 再确认**。

**关键经验**（gushi365 三轮修复）：
- v1：漏掉 `<textarea>` 后分享区 → 加截断
- v2：漏掉 `｜...｜` 推荐段 → 加整段砍
- **每次修复后自动跑全样本 4 项零残留扫描**——不靠人眼抽样

---

## Step 5: 全量

### 5.1 分批 + 限速

```python
time.sleep(0.3)  # 默认 0.3s 间隔（保护对方站）
```

### 5.2 容错 + 实时校验

- 单篇失败 → 写入 `failures.json`，**继续下一篇**
- 失败率 > 5% → **暂停**，先查失败原因
- 全程输出进度（每 10 篇一行）

### 5.3 出库结构

```
<site>_corpus_full/
├── corpus/           # .txt 一篇一个
├── manifest.jsonl    # 元信息（id/标题/作者/日期/字数/URL）
├── report.txt        # 统计（字数分布/失败列表）
├── failures.json     # 失败的 ID + 原因
└── extract.py        # 可复用的 extractor
```

---

## 输出格式

### 默认

每篇 .txt：
```
标题：XXX

<正文段落1>

<正文段落2>
...
```

### 用户可定制（**爬前必问**）

| 变体 | 何时选 |
|---|---|
| 裸 .txt（只含正文） | 喂训练 |
| JSONL | 后续分析 |
| 双出 | 既要训练又要分析 |
| 标题 + 作者 + 日期 头部 | 人工阅读 |

**经验**：训练用语料**别塞作者/日期/标签头部**——会污染 prompt。

---

## 关键经验 / Pitfalls

| Pitfall | 案例 | 解法 |
|---|---|---|
| 站名 ≠ 实际内容 | qigushi.com 90% 橙光攻略 | Step 1 抽样 5-10 个内页 |
| 首页分页截断 | gushi365 显示 10 页实际 113 页 | 永远二分探测末页 |
| web_extract 超时 ≠ 站拒绝 | parallel.ai 后端慢 | 批量抓用 curl + urllib |
| `<textarea>` 后是分享区 | gushi365 90% 页有这个 | 正则截到 `<textarea` |
| `｜...｜` 推荐链接 | gushi365 33% 页有 | 含 `｜` 整段砍 |
| 俄语翻译页编码错位 | gushi365 ID=5024 | extractor 返回 None，记 failures |
| 用户反馈噪音只看抽样 | 每次只发现表面问题 | **自动跑全样本 4 项扫描** |
| 训练用 .txt 塞元信息头部 | prompt 污染 | 默认只输出标题 + 正文 |
| 全量 1000+ 一次性跑 | 中途失败全废 | 分批 + 失败率报警 |
| 不留 extractor 源码 | 出问题无法重跑 | 永远把 extract.py 入库 |

完整噪音模式库见 `references/noise-patterns.md`。

---

## 版权 / 合规

| 用途 | 风险 |
|---|---|
| 个人研究 / 实验 | ✅ 低 |
| 内部训练 / 不发布 | ⚠️ 中（数据来源要标注） |
| 公开发布 / 商用 | ❌ 高（要原作者授权） |

**必要提醒**：原始版权归原作者。商用场景需训练后做改写、标数据来源、补公有领域语料。

---

## 文件结构

```
children-story-corpus-crawler/
├── SKILL.md                          # 本文件（skill 入口）
├── README.md                         # GitHub 仓库门面
├── LICENSE                           # MIT
├── .gitignore
├── scripts/
│   ├── extract.py                    # 通用 extractor 骨架
│   ├── extract_gushi365.py           # gushi365 适配版（已验证）
│   └── validate.py                   # 4 项零残留扫描脚本
├── configs/
│   ├── gushi365.yaml                 # 已验证站点配置
│   └── schema.md                     # 配置文件 schema 说明
├── references/
│   ├── noise-patterns.md             # 噪音模式库（持续追加）
│   └── html-structures.md            # 常见 HTML 容器 + 选择器
├── examples/
│   └── gushi365_run.md               # 完整实战记录
├── evals/
│   └── evals.json                    # 测试 prompt
└── output/                           # 运行时输出（不入库）
    └── .gitkeep
```

**双份维护**：
- 开发版：`~/Github/children-story-corpus-crawler/`（GitHub 公开）
- 安装版：`~/.hermes/skills/children-story-corpus-crawler/`（hermes 加载）
- 改一边 → 同步另一边（详见 `examples/sync-workflow.md`）

---

## 相关文件

- `configs/gushi365.yaml` — 已验证站点配置（4400+ 篇）
- `scripts/extract_gushi365.py` — gushi365 extractor v3（含所有噪音清理）
- `scripts/validate.py` — 4 项零残留扫描
- `references/noise-patterns.md` — 噪音模式库
- `examples/gushi365_run.md` — 完整实战记录（v1→v3 三轮修复）

## 版本历史

- **v1.1.1** (2026-06-15) — 扩栏目撞 WAF。发现 gushi365 新上"Browser security check"拦截：cookie + JS 验证 → curl 永远 403。睡前故事（无 WAF 时爬的 2101 篇）保留可用，其他 13 个栏目 WAF 拦截暂不可爬。SKILL.md Step 1 加 WAF 探测代码 + 已验证站点表加状态列。

- **v1.1** (2026-06-15) — 全量踩坑追加：坑 1「分页末页 ≠ 真实总量」（估算 4400 实际 2140）/ 坑 2「按 ID 范围爬是反模式」（13000+ 浪费 404）/ 坑 3「validate.py 两个误报」（标题里的 ｜ / 正文里"作者："段落）。validate.py 跳过标题行 + 只检查前 5 行；SKILL.md Step 3 加"按真实 URL 列表去重" + "反模式"清单。

- **v1.0.0** (2026-06-15) — 初版。gushi365.com 适配完成（2101 篇），噪音模式 3 类（textarea 分享区/页内重复标题/｜ 推荐链接）。