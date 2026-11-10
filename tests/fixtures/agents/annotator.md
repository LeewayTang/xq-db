---
role: annotator
description: 抽取人物、地名、国名、职官、事件与主题
tools:
- search_keyword
- get_passage
- get_work
- entity_lookup
- timeline
output_schema: annotator.schema.json
budget:
  max_tokens: 50000
  max_tool_calls: 50
  max_cost_usd: 0.6
fresh_context: true
---

测试角色。
