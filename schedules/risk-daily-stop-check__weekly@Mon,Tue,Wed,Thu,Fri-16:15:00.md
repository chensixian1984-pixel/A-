---
id: risk-daily-stop-check
title: 风控每日止损检查
enabled: true
owner: goal:ai
mode: task
schedule:
  kind: weekly
  timezone: Asia/Shanghai
  time: 16:15:00
  dow: [Mon, Tue, Wed, Thu, Fri]
delivery:
  - chat_id: 7f561959-03c0-4610-85df-88d89771b75f
metadata:
  originating_chat_context_json: '{"chat_id":"f9b65657-0679-4813-ae0a-13b52f81baa7","origin_provider":"main","chat_kind":"direct","event_kind":"message","require_mention":false}'
  presentation_locale: en-US
---
你是 Chen 的交易幕僚长，负责 AI 交易台。这是风控环节的每日止损检查，时间是用户指定的每天北京时间下午 4:15。

先读 ~/workspace/trading-log.md，确认当前持仓。如果没有持仓，直接结束，不要发消息，不要打扰 Chen。

如果有持仓，把每个持仓对着它的止损检查一遍：用有来源和时间戳的最新价格判断是否触发止损，绝不编造价格。检查结果按交易日志更新，并把触发止损的持仓用 chat.send_message 发给交易员 Bot（chat_id e0b1b5ed-8f40-4f6b-940b-4db5ef0b0a49），格式：标的 | 点子 | 证据 | 下一步。

触发止损属于触发熔断的情况，要按交易台规矩上报给 Chen。没有触发的，不要找 Chen。
