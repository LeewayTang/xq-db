---
role: muse
description: 从语料生成母题、场景、冲突与人物弧光
tools:
- search_keyword
- search_hybrid
- get_passage
- seed_add
- seed_list
- note_add
- note_search
output_schema: muse.schema.json
budget:
  max_tokens: 40000
  max_tool_calls: 40
  max_cost_usd: 0.5
fresh_context: true
---

测试角色。
