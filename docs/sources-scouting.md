# 先秦语料源侦察报告

- 日期：2026-11-11
- 范围：在本机可达的前提下，补充殆知阁与维基文库之外的公开语料源
- 原则：只收古籍原文与公开数字转录；不收现代点校、译注、外文译本；许可不明者隔离

## 1. 可达性

| 站点 | 状态 |
|---|---|
| github.com | 200 |
| zh.wikisource.org | 301（正常） |
| archive.org | 200 |
| www.bsm.org.cn（简帛网） | 200 |
| www.xianqin.org（先秦史研究室） | 301 → 200 |
| jgw.aynu.edu.cn（殷契文渊） | 200 |
| www.jgwlbq.org.cn（甲骨文 AI 协同平台） | 200，疑似需登录 |
| www.guoxuedashi.net | 502 |
| ctext.org | 超时，放弃 |
| fdgwz.fudan.edu.cn / www.gwz.fudan.edu.cn | 连接失败 |

## 2. 候选源

| # | 源 | 地址 | 规模 | 格式 | 许可 | 抓取方式 | 评价 |
|---|---|---|---|---|---|---|---|
| 1 | 殆知阁 V2.0（已用） | https://github.com/garychowcmu/daizhigev20 | 约 2.1 GB / 15,694 txt | txt | 无 LICENSE | `git clone --depth 1` | 广度底座，许可不明 |
| 2 | 中文维基文库 | https://zh.wikisource.org | 按需，全站 dump 10.9 GB 压缩 | wikitext | CC BY-SA 4.0 | API 按标题取，勿下整站 dump | 质量与许可最好 |
| 3 | gujilab/chinese-classical-corpus | https://github.com/gujilab/chinese-classical-corpus | 64 MB / 33 个 JSON | JSON / JSONL | 原文公版，衍生数据 CC0 1.0 | `git clone --depth 1` | 十三经、说文、资治通鉴、二十四史前 15 部，结构化好 |
| 4 | JasonWade001/chtxt | https://github.com/JasonWade001/chtxt | 35 MB / 约 90 txt | txt | 仓库无 LICENSE，原文公版 | `git clone --depth 1` | 儒家 7、道家 2、兵家 1、史书 16、字书 6、蒙学 16；适合补充核心文本 |
| 5 | kuanghy/zh-ancient-texts | https://github.com/kuanghy/zh-ancient-texts | 9 MB / 80 JSON | JSON | 无 LICENSE | `git clone --depth 1` | 论语、左传、道德经、孙子等，单书一 JSON，易解析 |
| 6 | 维基文库「金文」分类 | https://zh.wikisource.org/wiki/Category:金文 | 22 篇 | wikitext | CC BY-SA 4.0 | `list=categorymembers` | 青铜器铭文释文，出土文献的高质量起点 |
| 7 | 维基文库出土文献页面 | 见下 | 单篇数千至数万字 | wikitext | CC BY-SA 4.0 | API 按标题取 | 清华简《系年》8,840 字、郭店楚墓竹简 28,691 字、睡虎地《封診式》4,648 字、马王堆帛书、上博简目录 |
| 8 | 简帛网（武大简帛研究中心） | https://www.bsm.org.cn | 文章级 | HTML | 研究文章版权归作者 | 小规模抓取需逐篇确认 | 「簡帛文庫」有释文与考释，适合参考，不宜整站入库 |
| 9 | 先秦史研究室 | https://www.xianqin.org | 博客文章 | HTML | 版权归作者 | 不建议批量 | 甲骨、金文、简帛研究文章，作检索线索 |
| 10 | 殷契文渊 | https://jgw.aynu.edu.cn | 甲骨数据库 | Web/API 未知 | 未标注 | 需进一步探测接口 | 甲骨文字形与著录，可能有价值，但非纯文本 |
| 11 | Internet Archive | https://archive.org | 大量扫描本 | PDF / DjVu / OCR | 逐件不同 | `advancedsearch.php` | 多为扫描件，OCR 噪声大，优先级低 |
| 12 | Project Gutenberg | https://www.gutenberg.org | 少量 | txt | 公版 | 直接下载 | 多为英译，按政策不收 |
| 13 | ctext.org | https://ctext.org | — | — | — | 不可达 | 放弃 |

### 维基文库可直接取用的出土文献标题

- `清華大學藏戰國竹簡`、`清華大學藏戰國竹簡/系年`、`清華大學藏戰國竹簡/尹至`
- `郭店楚墓竹簡`
- `馬王堆帛書`、`老子 (帛書本)`、`春秋事语`
- `睡虎地秦簡`、`睡虎地秦簡/秦律雜抄`、`睡虎地秦簡/封診式`、`睡虎地秦簡/為吏之道`、`睡虎地秦簡/法律答問`
- `上海博物館藏戰國楚竹書` 及其子页（孔子詩論、緇衣、性情論等）
- `Category:金文` 下 22 篇铭文（利簋、何尊、史牆盤、中山王器等）

取用命令示例：

```bash
curl -s 'https://zh.wikisource.org/w/api.php?action=query&prop=revisions&rvprop=content&rvslots=main&format=json&formatversion=2&titles=清華大學藏戰國竹簡/系年'
```

## 3. 质量风险

| 源 | 风险 |
|---|---|
| 殆知阁 | 编码混杂、重复版本多（已检出 2,480 部近重复）、无许可声明 |
| 维基文库 | 页面质量不一，部分只有目录或未完成；需按长度与结构过滤 |
| gujilab | 以十三经与正史为主，先秦诸子与野史覆盖有限；JSON 结构需适配 |
| chtxt | 仓库无 LICENSE；部分文件含现代标点与编辑说明，需清洗 |
| kuanghy | 无 LICENSE；JSON 字段不统一，需逐书检查 |
| 简帛网 / 先秦史研究室 | 研究文章有版权，释文常夹在论文中；只能作参考，不能整站复制 |
| 殷契文渊 | 以字形图像与著录为主，非连续文本；接口与许可待确认 |
| Internet Archive | OCR 错误率高，扫描件需大量校对 |

## 4. 建议排序（价值 / 成本）

1. **维基文库出土文献 + 先秦核心**：许可最清晰、文本质量最高，现有 `ingest/wikisource.py` 稍加标题表即可覆盖清华简、郭店、睡虎地、马王堆、金文。优先做。
2. **gujilab CC0 语料**：一次 clone 即可拿到十三经等结构化文本，许可明确，适合作为校对骨架。
3. **chtxt + kuanghy**：体量小、补充性强；因许可不明，先放隔离区，标记 `license: unknown`。
4. **简帛网 / 先秦史研究室**：作为人工检索与释文核对来源，不做批量入库。
5. **殷契文渊 / Internet Archive**：等文本接口与许可明确后再评估。

## 5. 对现有实现的直接建议

- 扩展 `CORE_TITLES`：加入上列出土文献标题；按标题抓取，规避 10.9 GB 全站 dump。
- 新增 `gujilab` 采集器：读取 `output/corpus.jsonl` 与 `output/histories/*.json`，映射到现有 `work/edition/section` 模型。
- `sources.yaml` 增加 `wikisource_excavated`、`gujilab`、`chtxt`、`kuanghy` 四个源，分别标注 `trust` 与 `license`。
- 对 `license: unknown` 的 chtxt/kuanghy 默认放入隔离区，不进入公开 Release。
