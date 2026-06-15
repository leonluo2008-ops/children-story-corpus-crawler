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

## 总结：关键经验

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