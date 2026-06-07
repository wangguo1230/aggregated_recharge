import { createApiClient } from './http';

// 只与独立 AskWhy 后端交互（/api/askwhy/*），由后端转发到第三方并加密落库。
const api = createApiClient();

export interface AskWhyCard {
  code: string;
  type: string;
  typeLabel: string;
  channelOpen: boolean;
  canSubmit: boolean;
  status: string;
}

export interface AskWhyTokenInfo {
  email: string;
  appUserId: string;
  structure: string;
  planType: string;
  inputMode: string;
}

export interface AskWhyOrder {
  id: string;
  status: string;
  accountId?: string;
  email?: string;
  requestType?: string;
  resultMessage?: string | null;
  createdAt?: string;
  startedAt?: string;
  completedAt?: string | null;
}

export interface AskWhySubscription {
  planType: string;
  activeStart?: string;
  activeStartBeijing?: string;
  activeUntil?: string;
  activeUntilBeijing?: string;
  subscriptionDays?: number;
  durationDays?: number;
}

export interface AskWhyCardStatus {
  cardCode: string;
  cardStatus: string;
  previousCardCode: string;
  replacedByCardCode: string;
  rechargeAccount: string;
  rechargeTime: string | null;
}

interface BaseResult {
  ok: boolean;
  message?: string;
}

// 后端业务失败时返回 HTTP 200 + ok:false，这里统一转成异常。
function unwrap<T extends BaseResult>(data: T): T {
  if (!data?.ok) {
    throw new Error(data?.message || '请求失败');
  }
  return data;
}

export async function verifyCard(cardCode: string): Promise<AskWhyCard> {
  const { data } = await api.post<BaseResult & { card?: AskWhyCard }>('/askwhy/card/verify', {
    cardCode: cardCode.trim(),
  });
  const card = unwrap(data).card;
  if (!card) {
    throw new Error('卡密校验返回为空');
  }
  return card;
}

// 校验 Session JSON（参数 sessionJson 即整段 /api/auth/session 返回，对应第三方的 fetchToken）。
export async function verifyToken(sessionJson: string): Promise<AskWhyTokenInfo> {
  const { data } = await api.post<BaseResult & { token?: AskWhyTokenInfo }>('/askwhy/token/verify', {
    fetchToken: sessionJson.trim(),
  });
  const token = unwrap(data).token;
  if (!token) {
    throw new Error('Session 校验返回为空');
  }
  return token;
}

export async function createOrder(
  cardCode: string,
  sessionJson: string,
): Promise<{ orderId: string; status: string; message?: string }> {
  const { data } = await api.post<BaseResult & { orderId: string; status: string }>('/askwhy/exchange/create', {
    cardCode: cardCode.trim(),
    fetchToken: sessionJson.trim(),
  });
  const result = unwrap(data);
  return { orderId: result.orderId, status: result.status, message: result.message };
}

export async function fetchOrderStatus(orderId: string): Promise<AskWhyOrder> {
  const { data } = await api.get<BaseResult & { order?: AskWhyOrder }>('/askwhy/exchange/status', {
    params: { orderId },
  });
  const order = unwrap(data).order;
  if (!order) {
    throw new Error('订单查询返回为空');
  }
  return order;
}

// 查订阅：默认只传 orderId，由后端用该订单加密存储的 Session JSON 查询；
// 也可显式传 sessionJson（查询不在本库的订单时）。
export async function fetchSubscription(orderId: string, sessionJson = ''): Promise<AskWhySubscription> {
  const { data } = await api.post<BaseResult & { subscription?: AskWhySubscription }>('/askwhy/exchange/subscription', {
    orderId: orderId.trim(),
    fetchToken: sessionJson.trim(),
  });
  const subscription = unwrap(data).subscription;
  if (!subscription) {
    throw new Error('订阅查询返回为空');
  }
  return subscription;
}

// 卡密使用状况查询（批量，最多 200 个）。
export async function queryCards(cardCodes: string[]): Promise<AskWhyCardStatus[]> {
  const { data } = await api.post<BaseResult & { items?: AskWhyCardStatus[] }>('/askwhy/card/status', {
    cardCodes,
  });
  return unwrap(data).items || [];
}
