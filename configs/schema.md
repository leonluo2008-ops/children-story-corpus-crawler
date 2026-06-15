# configs/ YAML Schema

每个站点一个 YAML 文件，由 `scripts/extract.py` 读取。

## 完整字段

```yaml
site:                         # 站点基础信息
  name: string                # 必填，站点标识
  base_url: string            # 必填，根 URL（如 https://www.example.com）
  user_agent: string          # 可选，默认 Chrome UA
  article_url_pattern: string # 必填，文章 URL 模板（{id} 是占位符）
  list_path: string           # 可选，列表页路径（人参考）

selectors:                    # 必填，HTML 选择器
  title_class: string         # 标题 <h1 class="..."> 的 class
  content_class: string       # 正文容器 <div class="..."> 的 class

noise:                        # 噪音清理规则
  fence_chars:                # 围栏字符列表（含此字符的整段 <p> 砍）
    - string
  patterns:                   # 正则模式（命中整段砍，re.S 模式）
    - string
  keywords:                   # 关键词列表（短段/中段命中砍）
    - string

meta_selectors:               # 可选，元信息选择器
  author_date_pattern: string # 单条正则，group(1)=作者 group(2)=日期
  category_tag_pattern: string # 单条正则，group(1)=分类 group(2)=标签 HTML

output:                       # 输出格式
  header_format: string       # 支持字段：{title} {author} {date} {category} {tags}
                              # 默认 "标题：{title}\n\n"
                              # 写空字符串 = 不写头部
```

## 字段详细说明

### `site.article_url_pattern`

模板字符串，`{id}` 会被替换成 `extract.py --ids` 文件里的每个 ID。

- 相对路径：自动拼到 `base_url` 后（推荐）
- 绝对 URL：直接使用

```yaml
# 相对路径
article_url_pattern: /info/{id}.html
# 实际: https://www.example.com/info/123.html

# 绝对 URL
article_url_pattern: https://api.example.com/article/{id}
```

### `selectors.content_class`

正文容器的 class 名（不含 `<div class=` 部分）。

### `noise.fence_chars`

任何 `<p>` 段落里**包含**这些字符的字符，整段砍。

适用场景：站点用特殊字符围起内链列表（如 `｜`）。

### `noise.patterns`

正则模式列表。**任一**模式命中整段砍。`re.S` 模式生效。

适用场景：整段是 `<textarea>` / `<script>` / `<iframe>` 等。

### `noise.keywords`

段落内**包含**这些关键词时：
- 段落长度 < 60 字 → 砍（基本是广告/推广）
- 段落长度 < 200 字 → 砍（可能是带关键词的中长段）
- 段落长度 ≥ 200 字 → **保留**（避免误杀正文里的相关字）

### `output.header_format`

支持 Python str.format() 字段。可用：`{title}` `{author}` `{date}` `{category}` `{tags}`。

**经验**：
- 训练用：`header_format: ""`（完全不要头部）
- 阅读用：`header_format: "标题：{title}\n\n"`
- 档案用：包含作者/日期/分类

## 完整示例（gushi365）

见 `configs/gushi365.yaml`。

## 添加新站流程

1. `cp configs/gushi365.yaml configs/<新站>.yaml`
2. 改 `site.base_url` + `site.article_url_pattern`
3. 改 `selectors.title_class` + `selectors.content_class`（看 Step 2 摸到的 HTML）
4. 改 `noise.*` 三个字段（看 Step 2 摸到的噪音模式）
5. 跑 100 篇样本 → 4 项零残留扫描 → 通过
6. 全量

## 调试技巧

```bash
# 单篇调试
python3 -c "
import yaml
from scripts.extract import extract
cfg = yaml.safe_load(open('configs/gushi365.yaml'))
info = extract(open('raw/33.html').read(), cfg)
print(info['title'], '|', len(info['body']), '字')
print(info['body'][:200])
print('...')
print(info['body'][-200:])
"
```

确认正文起止干净、无噪音。