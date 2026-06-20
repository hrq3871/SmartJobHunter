# 五站抓取策略巡检报告（2026-06-21）

## 运行结论

- Run ID：`20260621-five-site-repair`
- 执行方式：一个 `crawler-strategy-inspector` 子 Agent 串行处理 5 个站点
- 关键词：产品经理
- 岗位类型：校招
- 总探测耗时：7.723 秒
- 结果：0 repaired，5 blocked，0 failed
- 阻断原因：当前企业网络策略关闭外部连接，Playwright 返回 `ERR_CONNECTION_CLOSED`，HTTP 探测在 TLS 握手阶段失败
- 配置变更：无。证据不足时未猜测 API、字段映射或详情 URL

> `network_unreachable` 表示本次运行环境无法访问，不代表招聘网站自身失效。应在允许访问这些域名的网络环境中重跑同一任务队列。

## 逐站结果

| 公司任务 | 原始链接 | 状态 | 耗时（秒） | 产物目录 |
|---|---|---:|---:|---|
| ruijie_campus | [https://app.mokahr.com/campus-recruitment/ruijie/136206#/jobs](https://app.mokahr.com/campus-recruitment/ruijie/136206#/jobs) | blocked/network_unreachable | 1.994 | `logs/crawler_evidence/20260621-five-site-repair/ruijie_campus` |
| dongchedi_campus | [https://dcar.jobs.feishu.cn/campus/position/list](https://dcar.jobs.feishu.cn/campus/position/list) | blocked/network_unreachable | 1.421 | `logs/crawler_evidence/20260621-five-site-repair/dongchedi_campus` |
| yonyou_campus | [https://career.yonyou.com/SU67ac41886202cc7916ae3029/pb/school.html](https://career.yonyou.com/SU67ac41886202cc7916ae3029/pb/school.html) | blocked/network_unreachable | 1.386 | `logs/crawler_evidence/20260621-five-site-repair/yonyou_campus` |
| sf_campus | [https://campus.sf-express.com/#/positionList](https://campus.sf-express.com/#/positionList) | blocked/network_unreachable | 1.384 | `logs/crawler_evidence/20260621-five-site-repair/sf_campus` |
| genertec_campus | [https://genertec.zhiye.com/custom/813f55cb-8392-5c3d-038e-1f815555e637](https://genertec.zhiye.com/custom/813f55cb-8392-5c3d-038e-1f815555e637) | blocked/network_unreachable | 1.538 | `logs/crawler_evidence/20260621-five-site-repair/genertec_campus` |

## 产物与边界

每站均已生成 `inspection.json`、`actions.json`、`network.json`、`evidence.json`、`strategy_decision.yaml`、`verification.json` 和 `task.json`。原始链接逐字保留；未保存 Cookie、Authorization、Token 或其他登录凭证。

由于连接在页面加载前被网络策略关闭，本轮没有可分析的 XHR、DOM 或岗位数组，因此没有进入 API 结构分析和 Python 策略写回阶段，也没有使用登录态或反检测方式绕过阻断。
