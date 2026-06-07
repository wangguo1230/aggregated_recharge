# AskWhy 用户端 API 对接文档（按实际抓包修订）

> 本文档为**上游第三方充值 API**的对接参考，依据真实抓包（`askwhy123.shop.har`）修订。
> 注意：早期文档写的路径前缀 `/v1` 与实际不符，**实际前缀为 `/api`**，且新增了 `token/verify`（校验 Session）、`recharge/channels`（渠道）两个接口，查订阅由 GET 改为 **POST 且需携带 fetchToken**。
>
> 本项目（10666 充值）后端对这些接口做了一层反向代理与「外部码 ↔ 真实卡密」映射，客户端只接触本项目自有接口，不直连本上游。上游字段以本文为准。

## 基础说明

- Base URL：`https://askwhy123.shop`
- 路径前缀：`/api`
- 请求格式：`application/json`
- 返回格式：`application/json`
- 时间格式：ISO 8601 字符串（部分接口额外提供北京时间字符串）
- 所有接口都返回 `ok` 字段：
  - `ok: true` 表示请求成功
  - `ok: false` 表示请求失败，失败原因查看 `message`

## 接口列表

| 接口 | 方法 | 路径 | 说明 |
| --- | --- | --- | --- |
| 校验卡密 | POST | `/api/cards/verify` | 检查卡密是否可提交，返回充值类型 |
| 校验 Session | POST | `/api/token/verify` | 校验用户 Session JSON（fetchToken），返回识别到的账号 |
| 创建充值订单 | POST | `/api/exchange/start` | 提交卡密 + Session 开始充值 |
| 查询订单状态 | GET | `/api/exchange/status` | 轮询充值进度 |
| 查询订阅结果 | POST | `/api/exchange/subscription` | 充值成功后查询订阅信息（需 fetchToken） |
| 批量查询卡密 | POST | `/api/cards/batch-query` | 批量查询卡密使用状况 |
| 查询充值渠道 | GET | `/api/recharge/channels` | 当前开放的充值类型 |

> 说明：`fetchToken` 实际就是**整段 Session JSON 字符串**（即 ChatGPT `/api/auth/session` 的完整返回），并非单一 token。

---

## 1. 校验卡密

`POST https://askwhy123.shop/api/cards/verify`

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| cardCode | string | 是 | 需要校验的卡密 |

### 请求示例

```json
{ "cardCode": "pro20xYPMEDG8CREEWLNQEN638" }
```

### 成功返回

```json
{
  "ok": true,
  "card": {
    "code": "pro20xYPMEDG8CREEWLNQEN638",
    "type": "PRO20X",
    "typeLabel": "Pro 20x",
    "channelOpen": true,
    "canSubmit": true,
    "status": "UNUSED"
  },
  "message": "卡密可用，充值类型：Pro 20x"
}
```

### 失败返回

```json
{ "ok": false, "message": "卡密不存在" }
```

### 字段说明

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| card.code | string | 卡密 |
| card.type | string | 充值类型（见「卡密类型」）|
| card.typeLabel | string | 类型展示名 |
| card.channelOpen | boolean | 该类型渠道是否开放 |
| card.canSubmit | boolean | 是否可提交（未使用且渠道开放时为 true）|
| card.status | string | 卡密状态（见「卡密状态」）|

---

## 2. 校验 Session

提交充值前，先校验用户 Session JSON 是否可识别。请求体字段名为 `fetchToken`，值为整段 Session JSON。

`POST https://askwhy123.shop/api/token/verify`

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| fetchToken | string | 是 | 整段 Session JSON（`/api/auth/session` 完整返回）|

### 请求示例

```json
{ "fetchToken": "{\"user\":{...},\"accessToken\":\"...\",\"account\":{...},...}" }
```

### 成功返回

```json
{
  "ok": true,
  "message": "已识别",
  "token": {
    "email": "user@example.com",
    "appUserId": "7f018c46-2247-4fe4-babf-eaad4b05d6b9",
    "structure": "personal",
    "planType": "free",
    "inputMode": "token"
  }
}
```

### 失败返回

```json
{ "ok": false, "message": "Session 无法识别" }
```

---

## 3. 创建充值订单

校验通过后，提交卡密 + Session 开始充值。

`POST https://askwhy123.shop/api/exchange/start`

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| cardCode | string | 是 | 卡密 |
| fetchToken | string | 是 | 整段 Session JSON |

### 请求示例

```json
{ "cardCode": "pro20xYPMEDG8CREEWLNQEN638", "fetchToken": "{...完整 Session JSON...}" }
```

### 成功返回

```json
{ "ok": true, "message": "订单已创建", "orderId": "cmq3xnwd800wilff2fob0dfe5", "status": "PENDING" }
```

### 失败返回

```json
{ "ok": false, "message": "卡密不可用或已使用" }
```

---

## 4. 查询订单状态

`GET https://askwhy123.shop/api/exchange/status?orderId=订单ID`

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| orderId | string | 是 | 创建订单返回的订单 ID |

### 成功返回

```json
{
  "ok": true,
  "order": {
    "id": "cmq3xnwd800wilff2fob0dfe5",
    "status": "RUNNING",
    "accountId": "7f018c46-2247-4fe4-babf-eaad4b05d6b9",
    "email": "user@example.com",
    "requestType": "PRO20X",
    "resultMessage": null,
    "createdAt": "2026-06-07T15:24:51.741Z",
    "startedAt": "2026-06-07T15:24:51.760Z",
    "completedAt": null
  }
}
```

### 失败返回

```json
{ "ok": false, "message": "订单不存在" }
```

---

## 5. 查询订阅结果

订单充值成功后查询订阅。**注意是 POST，且需要携带 fetchToken**（与创建订单同一份 Session）。

`POST https://askwhy123.shop/api/exchange/subscription`

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| orderId | string | 是 | 订单 ID |
| fetchToken | string | 是 | 整段 Session JSON |

### 请求示例

```json
{ "orderId": "cmq3xnwd800wilff2fob0dfe5", "fetchToken": "{...完整 Session JSON...}" }
```

### 成功返回

```json
{
  "ok": true,
  "message": "订阅查询完成",
  "subscription": {
    "planType": "pro",
    "activeStart": "2026-06-06T13:57:41Z",
    "activeStartBeijing": "2026/06/06 21:57:41",
    "activeUntil": "2026-07-06T13:57:08Z",
    "activeUntilBeijing": "2026/07/06 21:57:08",
    "subscriptionDays": 30,
    "durationDays": 30
  }
}
```

### 失败返回

```json
{ "ok": false, "message": "订单尚未充值成功，暂不能查询真实订阅" }
```

---

## 6. 批量查询卡密使用状况

`POST https://askwhy123.shop/api/cards/batch-query`

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| cardCodes | string[] | 是 | 卡密数组，最多 200 个 |

### 请求示例

```json
{ "cardCodes": ["pro20xYPMEDG8CREEWLNQEN638", "TEST-5678-DEMO"] }
```

### 成功返回

```json
{
  "ok": true,
  "count": 2,
  "items": [
    {
      "cardCode": "pro20xYPMEDG8CREEWLNQEN638",
      "cardStatus": "USED",
      "previousCardCode": "",
      "replacedByCardCode": "",
      "rechargeAccount": "user@example.com",
      "rechargeTime": "2026-06-07T15:24:55.646Z"
    },
    {
      "cardCode": "TEST-5678-DEMO",
      "cardStatus": "NOT_FOUND",
      "previousCardCode": "",
      "replacedByCardCode": "",
      "rechargeAccount": "",
      "rechargeTime": null
    }
  ]
}
```

### 字段说明

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| cardCode | string | 查询到的卡密；不存在时返回原始输入 |
| cardStatus | string | 卡密状态（见「卡密状态」）|
| previousCardCode | string | 若由旧卡置换而来，返回旧卡密 |
| replacedByCardCode | string | 若已被新卡置换，返回新卡密 |
| rechargeAccount | string | 最近一次充值账号，可能为空 |
| rechargeTime | string \| null | 最近一次充值时间，可能为空 |

---

## 7. 查询充值渠道

`GET https://askwhy123.shop/api/recharge/channels`

### 成功返回

```json
{
  "ok": true,
  "channels": [
    { "type": "PLUS", "label": "Plus", "enabled": true },
    { "type": "PRO5X", "label": "Pro 5x", "enabled": true },
    { "type": "PRO20X", "label": "Pro 20x", "enabled": true },
    { "type": "GO", "label": "Go", "enabled": false },
    { "type": "3daypro20x", "label": "3Day Pro 20x", "enabled": false },
    { "type": "3daypro5x", "label": "3Day Pro 5x", "enabled": false }
  ],
  "supportedTypes": ["PLUS", "PRO5X", "PRO20X"]
}
```

---

## 枚举说明

### 卡密类型（type）

| type | 说明 |
| --- | --- |
| PLUS | Plus |
| PRO5X | Pro 5x |
| PRO20X | Pro 20x |
| GO | Go |
| 3daypro20x | 3Day Pro 20x |
| 3daypro5x | 3Day Pro 5x |

### 卡密状态（cardStatus）

| 值 | 说明 |
| --- | --- |
| UNUSED | 未使用 |
| LOCKED | 已提交，处理中 |
| USED | 已使用 |
| ABNORMAL | 异常 |
| DISABLED | 已禁用 |
| NOT_FOUND | 卡密不存在 |

### 订单状态（status）

| 值 | 说明 |
| --- | --- |
| PENDING | 已创建，等待处理 |
| RUNNING | 处理中 |
| SUCCEEDED | 成功 |
| FAILED | 失败 |
| CANCELLED | 已取消 |

---

## 建议对接流程

1. `POST /api/cards/verify` 校验卡密，`canSubmit=true` 方可提交。
2. `POST /api/token/verify` 校验 Session JSON（fetchToken）。
3. `POST /api/exchange/start` 创建订单，拿到 `orderId`。
4. `GET /api/exchange/status?orderId=...` 轮询，每 3~5 秒一次；`SUCCEEDED/FAILED/CANCELLED` 停止。
5. 成功后 `POST /api/exchange/subscription`（带 orderId + fetchToken）查询订阅。
6. 售后/对账用 `POST /api/cards/batch-query` 核对卡密状态。

## 轮询建议

- 创建订单成功后，建议每 3~5 秒查询一次订单状态。
- 终态（`SUCCEEDED`/`FAILED`/`CANCELLED`）应停止轮询。
- 不建议高频并发轮询同一订单。

---

## 附：本项目后端代理映射

本项目（10666 充值）后端把上述上游接口封装在自有路径 `/api/askwhy/*` 下，并在中间做「外部码 ↔ 真实卡密」映射与字段白名单（响应中绝不回传真实卡密）。前端只调用本项目接口：

| 本项目接口 | 代理到的上游接口 |
| --- | --- |
| `POST /api/askwhy/card/verify` | `POST /api/cards/verify`（入参为外部码，后端解析为真实卡）|
| `POST /api/askwhy/token/verify` | `POST /api/token/verify` |
| `POST /api/askwhy/exchange/create` | `POST /api/exchange/start` |
| `GET /api/askwhy/exchange/status` | `GET /api/exchange/status` |
| `POST /api/askwhy/exchange/subscription` | `POST /api/exchange/subscription`（fetchToken 用订单加密存储的 Session）|
| `POST /api/askwhy/card/status` | `POST /api/cards/batch-query` |
| `GET /api/askwhy/recharge/channels` | `GET /api/recharge/channels` |
