import { createApiClient } from './http';

// 接码（短信）接口：只与本项目后端交互（/api/sms/*），由后端解析兑换码并转发到上游。
const api = createApiClient();

export interface SmsCard {
  code: string;
  phone: string;
}

export interface SmsFetchResult {
  phone: string;
  hasSms: boolean;
  code: string;
  content: string;
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

// 校验兑换码，返回绑定的手机号（不含查询地址）。
export async function verifySmsCard(cardCode: string): Promise<SmsCard> {
  const { data } = await api.post<BaseResult & { card?: SmsCard }>('/sms/card/verify', {
    cardCode: cardCode.trim(),
  });
  const card = unwrap(data).card;
  if (!card) {
    throw new Error('兑换码校验返回为空');
  }
  return card;
}

// 拉取一次最新短信，可重复调用（长期接码）。
export async function fetchSms(cardCode: string): Promise<SmsFetchResult> {
  const { data } = await api.post<BaseResult & SmsFetchResult>('/sms/fetch', {
    cardCode: cardCode.trim(),
  });
  const result = unwrap(data);
  return {
    phone: result.phone || '',
    hasSms: Boolean(result.hasSms),
    code: result.code || '',
    content: result.content || '',
  };
}
