# gushi365.com 实战记录

> 2026-06-15，从发现到全量可用的完整过程。给后续适配新站的人参考。

---

## 背景

用户原话："我想从 https://www.qigushi.com/ 下载故事，文字版"

## Step 1: 摸底（**发现问题：名实不符**）

抓首页 + sitemap + 5 个内页：

```bash
curl -sSL -A "$UA" "https://www.qigushi.com/" -o home.html
curl -sSL -A "$UA" "https://www.qigushi.com/map.html" -o sitemap.html
```

**结果**：
- 站名"七故事网 - 儿童睡前故事"
- 但首页 + 内页抓出来的全是**橙光游戏攻略**（《冥帝不好当》《洛希极限》等乙女养成攻略）
- 90%+ 内容不是儿童故事

**判断**：名实不符，**回退 + 找替代源**。

## Step 1.4: 找替代站

`web_search` query="儿童睡前故事 OR 童话 site:gushi365.com OR site:storymami.com OR site:runruneando.com"

**结果**：
- **gushi365.com/shuiqiangushi/** — 睡前故事，结构清晰 ✅ **选定**
- storymami.com — 睡前故事，按类型分类
- runruneando.com — 按年龄分级

## Step 2: 单篇实测（gushi365）

抓 3 篇不同位置：

```bash
for id in 33 97 209; do
  curl -sSL -A "$UA" "https://www.gushi365.com/info/${id}.html" -o "raw_${id}.html"
done
```

**HTML 结构识别**（WordPress 标准 + 分享区噪音）：
- 标题：`<h1 class="entry-title">XXX</h1>`
- 正文容器：`<div class="single-content">...</div>`
- 末尾：`<textarea>` 后跟分享/二维码/推广段
- 元信息：`<div class="single-cat">作者：XXX 日期：YYY</div>`

## Step 3: 摸分页

首页分页显示：
```html
<a class="page-numbers" href="/shuiqiangushi/index_2.html">2</a>
...
<a class="page-numbers" href="/shuiqiangushi/index_10.html">10</a>
```

只显示 1-10 页。但二分探测后：

```bash
for p in 50 100 150 200; do
  curl -sSL -A "$UA" -o /dev/null -w "%{http_code}\n" \
    "https://www.gushi365.com/shuiqiangushi/index_${p}.html"
done
# 50: 200, 100: 200, 150: 404, 200: 404
```

真实末页 = 113 页。**首页分页截断 = 站点的常见坑**。

## Step 4: 样本测试（**三轮修复**）

### v1: 第一版 extractor

- 标题 + 正文 + 元信息全部提取
- 关键词黑名单（点击/收藏/分享/二维码）

**用户反馈**："内容里有噪音未完全清除，末尾有此类文字'赞 订阅 分享'、'手机用户点击浏览器底部...'"

**根因**：`<textarea>` 之后整段是分享区，关键词过滤漏了部分段落。

### v2: 修复 textarea

```python
# 改成截到 <textarea> 为止
m = re.search(r'<div class="single-content">(.*?)(?:<textarea|</div>\s*</div><!-- \.entry-content)',
              html_text, re.S)
```

**用户反馈**："不需要'作者'、'日期'、'标签'这些信息"

**修法**：写 .txt 时只写 `标题：XXX`，不要元信息头部。

### v3: 修复 ｜ 推荐链接

**用户反馈**："又有这种结构的噪音，在末尾'｜小青蛙：我喜欢我自己｜小青蛙与荷花...'"

**根因**：gushi365 33% 页有 `｜...｜` 围起的推荐链接段。

**修法**：含 `｜` 字符的 `<p>` 整段砍。

```python
if "｜" in p:
    continue
```

**4 项零残留扫描结果**：

```bash
grep -l "｜" corpus/*.txt | wc -l       # 0 ✅
grep -l "gushi365.com/info" corpus/*.txt | wc -l  # 0 ✅
grep -lE "手机用户点击|朋友圈|收藏分享" corpus/*.txt | wc -l  # 0 ✅
grep -lE "^作者：|^日期：|^分类：|^标签：" corpus/*.txt | wc -l  # 0 ✅
```

**通过质量门**。

---

## v1.1 追加：全量 2101 篇 + 4 项误报修复（2026-06-15）

样本测试通过后，跑全量时**踩了 3 个新坑**，每条都补充进 SKILL.md / validate.py / 配置文件。

### 坑 1：分页末页 ≠ 真实总量（**最大教训**）

**问题**：v1.0 估算 gushi365 睡前故事 = 113 页 × 39 篇 = **约 4400 篇**。结果扫完 113 页真实 URL 只有 **2140 个去重 ID**。

**根因**：
- 首页分页显示 `class="page-numbers"` 只到第 10 页，**实际末页有 113 页**
- 但**单页 URL 数量波动很大**——有些页 39 篇，有些页 24 篇（末页填充），有些页可能 10 篇以下
- 之前估算用了"恒定 39 篇 × 页数"的简单乘法，**没考虑单页 URL 数量方差**

**教训**：

| ❌ 不要 | ✅ 要 |
|---|---|
| 按 `末页 × 平均URL数` 估算总量 | 按真实 URL 列表去重后计数 |
| 看到末页是 113 就估算 4400 | 末页只代表**分页上限**，不代表**内容上限** |

**正确做法**：

```bash
# 1. 扫全部 N 页拿 URL（不要按 ID 范围）
for p in $(seq 1 113); do
  curl -sSL "https://www.gushi365.com/shuiqiangushi/index_${p}.html" \
    | grep -oE 'href="/info/[0-9]+\.html"' | sort -u
done | sort -u > all_urls.txt
# gushi365 真实结果: 2140 篇（不是估算的 4400）

# 2. 提取 ID
sed 's|.*/info/||; s|\.html||; s|"||g' all_urls.txt > all_ids.txt
```

**写入 SKILL.md**：Step 3 新增"按真实 URL 列表去重计数"。

### 坑 2：按 ID 范围爬是反模式（**速度杀手**）

**问题**：v1.0 全量第一版尝试按 ID 范围 `[800..18700]` 爬 → **17899 个候选 ID**，实际只有 2140 存在 → **13000+ 浪费的 404 请求**。

**实测时间对比**：
- 按 ID 范围爬 17899 个：跑 9 分钟仅完成 9.3%（364/17899），按速度算要 2.7 小时
- 按真实 URL 列表爬 2140 个：跑 25 分钟完成 **2101/2140 = 98.2%**

**为什么按 ID 范围慢**：
- ID 不连续（gushi365 的 ID 是分配的，不是自增），范围 [800..18700] 里 13000+ 是空洞
- 每个空洞至少 200ms 等待 404 + 重试 = 浪费时间

**教训**：**永远先扫分页页拿真实 URL 列表，再爬**——不要尝试"按 ID 范围批量试"。

### 坑 3：validate.py 两个误报 bug（**质量门本身有 bug**）

全量跑完后跑 `validate.py`，两个 false positive 差点被当 true positive：

**Bug A：标题里的 ｜ 被误判为推荐链接**

```
标题：催眠｜小河马的哈欠
```

某些**系列名含 ｜**（"催眠｜小河马的哈欠" 是某系列的章节），用 `grep "｜"` 全文件扫描会误判。

**修复**：

```python
# 跳过头部 "标题：..." 行，只检查正文
lines = text.split("\n")
if lines and lines[0].startswith("标题："):
    body = "\n".join(lines[2:])  # 跳过 "标题：..." 和空行
else:
    body = text
if "｜" in body:  # 现在只检查 body
    issues["fence_chars"].append(f.name)
```

**Bug B：正文里介绍作者的段落被误判为元信息头部**

```
标题：萝卜回来了

雪这么大，天气这么冷...

作者：方轶群，1914年出生。江苏苏州人。著有童话集《月亮婆婆》等。
```

正文中以"作者："开头的段落（介绍作者信息）被 `re.findall(r"^(作者|日期|分类|标签)：", text, re.M)` 误判。

**修复**：

```python
# 只检查前 5 行（真正的头部），不看正文
head_text = "\n".join(lines[:5])
bad_headers = re.findall(r"^(作者|日期|分类|标签)：", head_text, re.M)
```

**教训**：质量门本身要避开误报，否则反而会**被 false positive 误导去修没问题的 extractor**。

### v1.1 改动清单

| 文件 | 改动 |
|---|---|
| `scripts/validate.py` | 跳过标题行 + 只检查前 5 行（修两个误报） |
| `SKILL.md` Step 3 | 新增"按真实 URL 列表去重计数"原则 + 删"按 ID 范围批量试"反模式 |
| `examples/gushi365_run.md` | 本节追加 |
| `references/noise-patterns.md` | 不改（噪音模式没变） |

### v1.1 全量最终结果

| 指标 | 值 |
|---|---|
| 总 ID | 2140 |
| ✅ 成功 | 2101 (98.2%) |
| ❌ 失败 | 39 (1.8%) — 编码错位 + 模板异常 |
| 中位字数 | 785 |
| max 字数 | 5396 |
| 总耗时 | ~25 分钟（含旧 raw 缓存复用） |

4 项零残留全过。**语料可入库**。

| 经验 | 教训 |
|---|---|
| **Step 1 必须抽样内页** | qigushi.com 案例教训——只看首页文字会被骗 |
| **首页分页 ≠ 真实末页** | gushi365 10 vs 113 实际差距 10 倍 |
| **噪音模式按站定制** | 不要照搬——gushi365 有 textarea/页内重复标题/｜ 三种，但其他站不一定有 |
| **关键词过滤是兜底** | 优先按结构切（截到 `<textarea>`），关键词过滤精度不高 |
| **每次修复跑全样本扫描** | 不靠人眼抽样 3 篇——`scripts/validate.py` 全扫 |
| **用户反馈噪音立即重扫** | 每次用户提噪音问题，跑 `validate.py` 看是哪类问题 |
| **`.txt` 默认不写元信息头部** | 训练用 .txt 塞作者/日期 = prompt 污染 |

## 时间线

- 摸底 + 找替代源：5 分钟
- 单篇实测 + 写 extractor v1：10 分钟
- 抓 100 篇样本：50 秒
- 修 v2（textarea 截断）：5 分钟
- 修 v3（｜ 推荐链接）：3 分钟
- **总耗时：~25 分钟**

## 后续：扩展到其他栏目

gushi365.com 还有：
- `/tonghua/` — 童话
- `/yingyu/` — 英文故事（待确认）

复用 `scripts/extract.py` + `configs/gushi365.yaml`，**只需要在 Step 3 把 list_path 改一下**就能扩到其他栏目。

## 扩展到其他站

`scripts/extract.py` 是配置驱动的，**新站 = 新 YAML 文件 + 跑 5 步 SOP**：

```bash
cp configs/gushi365.yaml configs/storymami.yaml
# 改 site.base_url / article_url_pattern / selectors / noise
python3 scripts/extract.py --config configs/storymami.yaml --ids ids.txt --out corpus_storymami/
```