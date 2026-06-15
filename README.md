# Children Story Corpus Crawler

> 中文儿童故事语料库爬取 skill —— 适配 gushi365 / storymami / runruneando 等站点

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)

## 这是什么

爬取中文儿童故事网站（睡前故事/童话/绘本/寓言），提取纯文本正文，清洗站点噪音，输出 `.txt` 语料库供训练或阅读。

**已验证站点**：gushi365.com（睡前故事 4400+ 篇）

## 5 步 SOP（任何站必走）

```
Step 1 摸底       站名 vs 实际内容？有没有 API/RSS/sitemap？
Step 2 单篇       抓 3 篇摸 HTML 结构，识别选择器 + 噪音模式
Step 3 摸分页     列表分页规则？真实末页 = 多少？
Step 4 样本       抓 50-100 篇 → 4 项零残留扫描 → 用户确认
Step 5 全量       分批抓 + 实时校验 + 失败率报警 → 出库
```

详见 [SKILL.md](SKILL.md)。

## 快速开始

### 1. 安装

```bash
# 安装 Python 依赖
pip install pyyaml

# 准备数据目录
mkdir -p /tmp/gushi365_corpus && cd /tmp/gushi365_corpus
```

### 2. 单篇测试

```bash
# 准备 100 个 article ID（一行一个）
# 从栏目分页页提取（详见 SKILL.md Step 3）

# 跑 extractor
python3 ~/Github/children-story-corpus-crawler/scripts/extract.py \
    --config ~/Github/children-story-corpus-crawler/configs/gushi365.yaml \
    --ids sample_100_ids.txt \
    --out corpus/
```

### 3. 质量验证

```bash
python3 ~/Github/children-story-corpus-crawler/scripts/validate.py \
    corpus/ gushi365.com
```

期望输出：4 项全部 ✅，否则回 Step 2 修 extractor。

### 4. 全量

```bash
# 扩到全站所有 ID 后跑
python3 scripts/extract.py --config configs/gushi365.yaml \
    --ids all_ids.txt --out corpus_full/ --sleep 0.3
```

## 适配新站

```bash
cp configs/gushi365.yaml configs/<新站>.yaml
# 改 site.base_url / site.article_url_pattern / selectors / noise
# 跑 5 步 SOP
```

详见 [configs/schema.md](configs/schema.md)。

## 文件结构

```
children-story-corpus-crawler/
├── SKILL.md                       # 主入口（5 步 SOP）
├── README.md                      # 本文件
├── LICENSE                        # MIT
├── scripts/
│   ├── extract.py                 # 通用 extractor 骨架（配置驱动）
│   └── validate.py                # 4 项零残留扫描
├── configs/
│   ├── gushi365.yaml              # 已验证站点配置
│   └── schema.md                  # 配置 schema 说明
├── references/
│   ├── noise-patterns.md          # 噪音模式库（持续追加）
│   └── html-structures.md         # 常见 HTML 容器速查
├── examples/
│   └── gushi365_run.md            # 实战记录（v1→v3 三轮修复）
└── evals/
    └── evals.json                 # 测试 prompt（10 个）
```

## 关键经验

- **站名 ≠ 实际内容** — qigushi.com 案例教训
- **首页分页截断** — gushi365 显示 10 页实际 113 页
- **噪音模式按站定制** — 不照搬，5 步 SOP 摸出来
- **训练用 .txt 别塞元信息** — 会污染 prompt
- **每次修复跑全样本扫描** — 不靠人眼抽样

详见 [references/noise-patterns.md](references/noise-patterns.md)。

## 版本

- **v1.0.0** (2026-06-15) — 初版。gushi365.com 适配完成（4400+ 篇）。

## 许可

MIT — 详见 [LICENSE](LICENSE)。

数据来源版权归原作者所有，详见 [SKILL.md 版权章节](SKILL.md)。