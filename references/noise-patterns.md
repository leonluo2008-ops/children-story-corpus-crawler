# 噪音模式库

> 持续追加。每个新站测出新模式就补一节，按"模式 → 特征 → 修法 → 案例"格式。

---

## 模式 1: `<textarea>` 后分享/二维码区

**特征**：正文容器内，正文段落结束后跟一个 `<textarea>`（含分享文案 + URL），其后有 1-2 个 `<p>` 是"电脑用户，点击这里..."、"手机用户点击浏览器底部..."等推广段。

**典型 HTML**：

```html
<div class="single-content">
  <p>正文段落...</p>
  <p>正文最后一段。</p>
  <textarea>【分享标题 - 站点名】分享文案 https://www.example.com/info/123.html</textarea>
  <p><input type="button" value="电脑用户，点击这里收藏或分享"></p>
  <p>手机用户点击浏览器底部 ≡ ↗ 或右上角 ┅ 等按钮，收藏或分享到朋友圈</p>
</div>
```

**修法**：正则截到 `<textarea` 为止，正文容器只取 `<textarea` 之前的部分。

**适用站点**：gushi365.com（90%+ 页面有此模式）

**gushi365 extractor v2 修复**：见 `scripts/extract_gushi365.py` 的正则：
```python
re.search(r'<div class="single-content">(.*?)(?:<textarea|</div>\s*</div><!--)',
          html_text, re.S)
```

---

## 模式 2: 页内重复标题 `<h2><span class="entry-title">`

**特征**：正文末尾出现一个 `<h2>`，里面是 `<span class="entry-title"><a href="/info/xxx">标题</a></span>`，跟主标题一样（页内重复）。

**典型 HTML**：

```html
<div class="single-content">
  <p>正文...</p>
  <p>正文最后一句。</p>
  <h2><span class="entry-title"><a href="/info/123.html">梨子提琴</a></span></h2>
</div>
```

**修法**：提取正文段落时，跳过文本 == 主标题 的 `<p>`。

**适用站点**：gushi365.com

---

## 模式 3: `｜...｜` 推荐链接围栏

**特征**：页面末尾有一个 `<p>`，里面用 `｜`（中文竖线）围起多个站内内链，列出"相关推荐"。

**典型 HTML**：

```html
<p>｜<a href="https://www.gushi365.com/info/8740.html">小熊家的冰糖葫芦</a>｜<a href="https://www.gushi365.com/info/6401.html">明天，妈妈不在家</a>｜<a href="https://www.gushi365.com/info/10211.html">大灰狼会变成好狼吗</a>｜</p>
```

**修法**：含 `｜` 字符的 `<p>` 整段砍（不要试图正则删中间部分——非贪婪匹配会漏段）。

**适用站点**：gushi365.com（33% 页面有此模式）

**gushi365 extractor v3 修复**：见 `scripts/extract_gushi365.py` 的 `if "｜" in p: continue`。

---

## 模式 4: 短段关键词命中

**特征**：噪音段通常是 30-80 字，含"点击""收藏""分享""扫描""二维码""朋友圈"等推广关键词。

**典型段落**：
- "电脑用户，点击这里收藏或分享"
- "手机用户点击浏览器底部 ≡ ↗ 或右上角 ┅ 等按钮，收藏或分享到朋友圈"
- "扫码下载 APP"

**修法**：关键词命中 + 段落长度 < 60/200 字 → 砍。长段落（如正文里提到"分享"）保留。

**注意**：这是兜底防御，**前 3 个模式应该先解决**——靠关键词过滤的精度不高，容易误伤正文里相关词。

---

## 模式 5: 编码错位页（**不是噪音，但 extractor 应跳过**）

**特征**：原页是外语翻译成中文时编码错位（如 CP1252 / GBK 错位），标题和正文全是 `?????` 或乱码。

**典型情况**：gushi365 ID=5024 是俄语翻译页，整页编码错位。

**修法**：extractor 检测标题或首段是否含大量乱码字符 → 返回 None → 记 `failures.json`。

**实现思路**（**待补**）：
```python
def is_mojibake(text):
    """简单检测：连续 3 个以上 ? 或 Latin-1 字符。"""
    return bool(re.search(r'\?{3,}|[\x80-\xFF]{3,}', text))
```

---

## 模式 6: 站内广告/合作内容段

**待识别**。常见形式：
- "本文由 XX 出版社授权发布"
- "扫码关注公众号 XXX"

修法：关键词扩展 + 长度限制。

---

## 模式 7: `<iframe>` 嵌入视频

**待识别**。常见形式：正文里嵌一段 `<iframe src="...">` 视频。

修法：去 HTML 标签时已经过滤，但要在抽取前先剔除 iframe 整段。

---

## 添加新模式的流程

1. **发现**：用户反馈或 `scripts/validate.py` 扫描命中
2. **记录**：在本文件加一节，格式：`## 模式 N: <标题>` + 四段（特征/HTML/修法/站点）
3. **修 extractor**：在 `scripts/extract.py` 或 `scripts/extract_<site>.py` 加规则
4. **重跑样本**：100 篇 → 4 项零残留 → 通过
5. **更新版本历史**：在 SKILL.md 末尾的"版本历史"加一条

---

## 4 项零残留扫描（**质量门**）

每次修改 extractor 后跑：

```bash
python3 scripts/validate.py corpus/ <site-domain>
```

**4 项检查**：
1. **推荐链接围栏**（如 `｜`）残留
2. **站内内链**残留（如 `gushi365.com/info`）
3. **噪音关键词**残留（点击/收藏/分享/扫码/朋友圈/微信/QQ 等）
4. **不该有的元信息头部**（按用户要求，默认无作者/日期/分类/标签头部）

全部 0 才能进入全量。