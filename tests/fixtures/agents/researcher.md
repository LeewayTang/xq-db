---
role: researcher
description: 多轮检索并写出带引用的综述
tools:
- search_keyword
- search_hybrid
- get_passage
- get_work
- entity_lookup
- timeline
- note_search
output_schema: researcher.schema.json
budget:
  max_tokens: 40000
  max_tool_calls: 40
  max_cost_usd: 0.5
fresh_context: true
---

测试角色。
