# 常见 HTML 容器速查

> 各站点的内容结构往往相似，提取前先看属于哪种模板。

## 模板 A: WordPress 标准（gushi365 / 多数博客）

```html
<article class="post type-post">
  <header class="entry-header">
    <h1 class="entry-title">标题</h1>
  </header>
  <div class="entry-content">
    <div class="single-content">
      <p>段落1</p>
      <p>段落2</p>
      <textarea>分享文案...</textarea>  <!-- 噪音 -->
    </div>
    <footer class="single-footer">
      <div class="single-cat">作者：XXX 日期：YYY</div>
      <div class="single-cat">所属分类：<a>...</a> 标签：<a>...</a></div>
    </footer>
  </div>
</article>
```

**关键选择器**：
- 标题：`h1.entry-title`
- 正文：`div.single-content`（或 `div.entry-content` 整段）
- 作者/日期：`div.single-cat` 含"作者：XXX 日期：YYY"
- 分类/标签：`div.single-cat` 含"所属分类：<a>..." + "标签：<a>..."

**gushi365 用的就是这个模板。**

---

## 模板 B: 通用 article 容器

```html
<article>
  <h1 class="article-title">标题</h1>
  <div class="article-content">
    <p>段落1</p>
    ...
  </div>
  <div class="article-meta">
    <span class="author">XXX</span>
    <time datetime="2024-01-01">2024年1月1日</time>
  </div>
</article>
```

**关键选择器**：
- 标题：`h1.article-title` 或 `article > h1`
- 正文：`div.article-content` 或 `article > div`
- 日期：`<time datetime="...">`

---

## 模板 C: 仿 SemPress / 自研

```html
<div class="post">
  <h1 class="post-title">标题</h1>
  <div class="post-body">
    <p>段落1</p>
    ...
  </div>
  <div class="post-info">
    <span>作者：XXX</span>
    <span>发布时间：YYY</span>
  </div>
</div>
```

**关键选择器**：
- 标题：`h1.post-title`
- 正文：`div.post-body`
- 元信息：`div.post-info` 文本

---

## 模板 D: 极简（无 class，全靠语义）

```html
<main>
  <h1>标题</h1>
  <div>
    <p>段落1</p>
    ...
  </div>
</main>
```

**关键选择器**：
- 标题：`main > h1` 或简单 `h1`
- 正文：`main > div`（第二个子元素）

---

## 模板 E: 嵌入渲染（JavaScript 加载）

```html
<div id="root"></div>
<script src="bundle.js"></script>
```

**这是 SPA / React / Vue 站点**，正文不在 HTML 里。

**应对**：
- 用 `browser_navigate` 抓渲染后的页面
- 或放弃这个站，找替代源
- 或用站点提供的 API（如有）

**千万不要**：用 curl 抓 HTML 然后期望能解析出正文。

---

## 元信息提取模式汇总

| 元信息 | 常见形式 | 提取方式 |
|---|---|---|
| **作者** | "作者：XXX" / `<span class="author">XXX</span>` / `<a rel="author">XXX</a>` | 文本匹配 + 标签选择 |
| **发布日期** | "日期：XXX" / `<time datetime="2024-01-01">` | 同上 |
| **分类** | "分类：XXX" / `<a rel="category">XXX</a>` | 同上 |
| **标签** | "标签：A, B, C" / `<a rel="tag">` × N | 多个 `a` 拼接 |
| **字数/阅读时间** | "约 1000 字" / "阅读 5 分钟" | 可选提取 |

**注意**：很多中文站用**纯文本**（如 "作者：XXX 日期：YYY"），不用 HTML 标签——这反而好提取。

---

## 段落级结构

正文容器里通常是连续 `<p>`，但也可能有：

| 元素 | 含义 | 处理 |
|---|---|---|
| `<p>` | 段落 | 主提取目标 |
| `<p>&nbsp;</p>` | 空段（排版用） | **跳过** |
| `<h2>/<h3>` | 小标题（章内） | 按正文段保留 |
| `<img>` | 图片 | 去标签（保留 alt 文本可考虑） |
| `<strong>/<em>` | 加粗/斜体 | 去标签保留文本 |
| `<blockquote>` | 引用 | 转 `<p>` 保留 |
| `<pre>/<code>` | 代码块 | 极少见，跳过 |
| `<ul>/<ol>` | 列表 | 展开为 `<p>`（保留项目符号可考虑） |
| `<iframe>` | 嵌入视频 | 整段跳过 |

---

## 调试技巧

### 看页面结构

```bash
# 找正文容器
curl -sSL "URL" | grep -nE 'class="(content|article|single|post)' | head

# 找元信息
curl -sSL "URL" | grep -nE '作者|日期|分类|标签|datetime|published' | head

# 看段落数
curl -sSL "URL" | grep -c "<p"

# 看末尾噪音
curl -sSL "URL" | tail -c 1500
```

### 单篇提取测试

```python
import yaml, re, html
cfg = yaml.safe_load(open('configs/gushi365.yaml'))
text = open('raw/33.html').read()

# 找正文容器
m = re.search(r'<div class="single-content">(.*?)(?:<textarea|</div>)', text, re.S)
if m:
    body = m.group(1)
    print("段落数:", len(re.findall(r'<p', body)))
    print("前 200:", re.sub(r'<[^>]+>', '', body[:200]))
    print("后 500:", re.sub(r'<[^>]+>', '', body[-500:]))
```