---
role: reviewer
description: 常驻质量门：来源准入、质量分级与性质标注
tools:
- search_keyword
- get_passage
- get_work
- list_works
- corpus_stats
output_schema: reviewer.schema.json
budget:
  max_tokens: 40000
  max_tool_calls: 40
  max_cost_usd: 0.5
fresh_context: true
---

测试角色。
