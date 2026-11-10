---
role: curator
description: 判定作者、年代、类目与相关性，处理重复版本
tools:
- search_keyword
- get_work
- list_works
- note_search
- corpus_stats
output_schema: curator.schema.json
budget:
  max_tokens: 30000
  max_tool_calls: 30
  max_cost_usd: 0.4
fresh_context: true
---

测试角色。
