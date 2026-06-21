# 五站抓取策略复检报告（网络恢复后）

## 运行结论

- Run ID：`20260621-five-site-repair-retry`
- 执行方式：同一个 `crawler-strategy-inspector` 子 Agent 串行处理 5 个站点
- 子 Agent 巡检耗时：188.4 秒
- 结果：3 repaired，0 blocked，2 failed
- 主 Agent 独立复验：3 个 repaired 站点各返回 3 个岗位，岗位有效率、URL 有效率及 `company/title/url/duty/requirement` 完整率均为 100%

## 逐站结果

| 公司任务 | 原始链接 | 状态 | 子 Agent 耗时（秒） | 结论 |
|---|---|---:|---:|---|
| ruijie_campus | [https://app.mokahr.com/campus-recruitment/ruijie/136206#/jobs](https://app.mokahr.com/campus-recruitment/ruijie/136206#/jobs) | failed/insufficient_evidence | 51.1 | Mokahr 岗位响应为加密载荷，缺少可复现字段映射，未猜测或固化配置 |
| dongchedi_campus | [https://dcar.jobs.feishu.cn/campus/position/list](https://dcar.jobs.feishu.cn/campus/position/list) | repaired/verified | 42.8 | 飞书 `search/job/posts` 接口、字段和完整详情 URL 已固化 |
| yonyou_campus | [https://career.yonyou.com/SU67ac41886202cc7916ae3029/pb/school.html](https://career.yonyou.com/SU67ac41886202cc7916ae3029/pb/school.html) | failed/insufficient_evidence | 13.8 | 列表接口缺少职责、任职要求和可验证详情 URL，未猜测详情路由 |
| sf_campus | [https://campus.sf-express.com/#/positionList](https://campus.sf-express.com/#/positionList) | repaired/verified | 53.7 | `/api/web/position/query` 接口、岗位字段和详情路由已固化 |
| genertec_campus | [https://genertec.zhiye.com/custom/813f55cb-8392-5c3d-038e-1f815555e637](https://genertec.zhiye.com/custom/813f55cb-8392-5c3d-038e-1f815555e637) | repaired/verified | 27.0 | `Jobad/GetJobAdPageList` 接口、岗位字段和详情 URL 已固化 |

## 主 Agent 独立复验

| 公司任务 | 验证岗位数 | 有效岗位率 | URL 有效率 | 五个必填字段完整率 | 复验耗时 |
|---|---:|---:|---:|---:|---:|
| dongchedi_campus | 3 | 100% | 100% | 100% | 12.832 秒 |
| sf_campus | 3 | 100% | 100% | 100% | 12.317 秒 |
| genertec_campus | 3 | 100% | 100% | 100% | 12.058 秒 |

验证样例链接均按接口原值完整保留：

- [https://dcar.jobs.feishu.cn/campus/position/7569217575054608691/detail](https://dcar.jobs.feishu.cn/campus/position/7569217575054608691/detail)
- [https://campus.sf-express.com/#/postDetail/2188](https://campus.sf-express.com/#/postDetail/2188)
- [https://genertec.zhiye.com/custom/2c145520-9dce-0868-c707-e65870a45b86?ct=7a34f1fa-99fc-d287-e761-c9dc230e5baa&jobAdId=9c5530d6-48a1-4d03-a161-9237f4aeef85](https://genertec.zhiye.com/custom/2c145520-9dce-0868-c707-e65870a45b86?ct=7a34f1fa-99fc-d287-e761-c9dc230e5baa&jobAdId=9c5530d6-48a1-4d03-a161-9237f4aeef85)

## 修复闭环

三项成功策略均经过：公开页面访问 → Network/XHR 采证 → Agent 分析 API 与字段 → Python `strategy_applier` 定向写回 → Python 严格验证 → 保存 `verification.json` → 保存页面 fingerprint → 标记 `verified`。两项失败站点保留 `strategy_decision.yaml`、`verification.json` 和 `task.json`，没有生成无法验证的抓取规则。

## Codex in-app Browser 追加深挖

- Run ID：`20260621-ruijie-yonyou-iab`
- 锐捷：in-app Browser 在导航前被企业网络策略阻断，耗时 0.712 秒；无法验证 Mokahr 加密载荷在浏览器端如何转换为岗位字段。
- 用友：in-app Browser 在导航前被企业网络策略阻断，耗时 0.007 秒；无法确认岗位详情 URL、完整职责和任职要求。
- 两站均保留 `failed/insufficient_evidence`，未修改配置或代码；对应产物位于 `logs/crawler_evidence/20260621-ruijie-yonyou-iab/`。
