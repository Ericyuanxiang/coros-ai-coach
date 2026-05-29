# Workflows

固定流程编排 — 顺序调用 coach/ 模块，不依赖 AI 做判断。

```
daily_checkin    → 每天一次   (状态 + 建议 + 告警)
post_workout     → 每次练完   (质量检查 + 偏离检测)
weekly_review    → 每周一次   (趋势 + 下周调整)
generate_plan    → 每阶段一次  (自动制定周计划)
alerts           → 自动触发   (异常检测)
```
