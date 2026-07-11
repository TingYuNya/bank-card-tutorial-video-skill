# 银行卡教程事实核验契约

## 来源优先级

1. 银行产品页、费率表、持卡人协议、帮助中心。
2. 卡组织官网规则与权益说明。
3. 金融监管机构和政府网站。
4. 银行官方应用内页面或用户提供的当前截图。

默认排除：

- 中文资讯站和聚合站。
- 论坛、社交媒体帖文和自媒体教程。
- 未标日期的第三方博客。
- 搜索结果摘要中没有打开核对的内容。

## 每条 Claim 的必填字段

```json
{
  "id": "claim-001",
  "claim": "",
  "category": "eligibility|fee|deposit|activation|repayment|benefit|credit_reporting|other",
  "region": "",
  "status": "verified|qualified|removed|unresolved",
  "severity": "high|medium|low",
  "source_title": "",
  "source_url": "",
  "source_type": "bank_official|card_network_official|regulator|product_agreement|official_help|official_app|other_official",
  "source_official": true,
  "source_language": "en-US",
  "checked_at": "YYYY-MM-DD",
  "effective_date": null,
  "notes": ""
}
```

## 处理冲突

- 不同地区条款冲突时，分别记录地区。
- 产品页和协议冲突时，优先显示协议内容，并在备注中记录差异。
- 截图 UI 与帮助中心不一致时，记录截图日期、应用版本和账户类型。
- 无法确认的高风险陈述应删除、改成有条件表述或暂停渲染。

## 补足文档

AI 可以补充遗漏步骤，但新增步骤也需要来源。新增内容在 `revised-article.md` 中正常呈现，在 `fact-check.json` 中保留对应 Claim，在 `source-list.md` 中列出来源。

## 来源字段约束

- `source_url` 使用 HTTPS，并打开原页面核对，不使用搜索结果摘要代替。
- `source_official` 必须为 `true`。
- `source_language` 记录页面实际语言。默认配置禁止 `zh` 开头的来源。
- 同一条陈述涉及多个地区或不同生效日期时，拆成多条 Claim。
