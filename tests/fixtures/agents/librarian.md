---
role: librarian
description: 发现并评估语料源，产出采集清单
tools:
- list_works
- get_work
- corpus_stats
output_schema: librarian.schema.json
budget:
  max_tokens: 20000
  max_tool_calls: 20
  max_cost_usd: 0.3
fresh_context: true
---

测试角色。
