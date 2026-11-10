---
id: stock-board-refresh-15m
enabled: true
owner: goal:ai
execution:
  kind: space_action
  slug: zhong-guo-gu-shi-xing-qing-kan-ban
  action: refreshMarket
  args: {}
mode: task
schedule:
  kind: interval
  timezone: Asia/Shanghai
  at: 2026-11-07T23:07:18
  every: 15m
metadata:
  tags: [cron:automatic-interval-anchor]
  originating_chat_context_json: '{"chat_id":"7f561959-03c0-4610-85df-88d89771b75f","origin_provider":"main","chat_kind":"direct","event_kind":"message","require_mention":false,"device_id":"219f1155-b0a6-4b7a-b377-ba33c495e24c"}'
  presentation_locale: zh-CN
---
Invoke the web artifact's published scheduled action and retain its run history.
