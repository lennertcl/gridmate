---
name: chartjs
description: "Build or modify Chart.js charts in GridMate. Use this skill when the user asks to create, fix, refine, or restyle Chart.js charts, time-series dashboards, dataset gaps, axes, legends, tooltips, or live chart behavior."
---

This skill guides work on Chart.js charts in GridMate.

When modifying a chart:
- Read the relevant Chart.js documentation before coding.
- Prefer built-in Chart.js behavior such as `null` data points, `spanGaps`, scriptable point options, time scales, and dataset configuration over custom drawing code.
- Keep chart setup in a dedicated `*-charts.js` file and page orchestration in the matching page module.
- Reuse the color tokens already defined in `web/static/css/main.css`.
- Use `{ x, y }` point objects for time-series data.

When handling gaps or intermittent activity:
- Use `null` points to create explicit breaks in line charts.
- Only connect two points when the underlying data should be continuous across that interval.

Relevant Chart.js docs:
- Line charts: https://www.chartjs.org/docs/latest/charts/line.html
- Time Cartesian axis: https://www.chartjs.org/docs/latest/axes/cartesian/time.html
- Data structures: https://www.chartjs.org/docs/latest/general/data-structures.html
