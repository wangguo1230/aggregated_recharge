import { createApiClient } from './http';

// GPT 充值接口：直接调用 Gift 上游（/api/gpt/*），客户输入真实 cdkey，无外部码映射。
const api = createApiClient();

// 上游激活/校验可能较慢（后端上游超时 60s），前端给足等待时间，避免前端先于后端超时
// 造成「卡已扣、客户却看到失败」。
const SLOW_TIMEOUT = 120_000;

export interface GptCard {
  giftName: string;
  app: string;
  useStatus: number | null;
  statusHint: string;
  account: string;
  completedAt: string;
  inCooldown: boolean;
  cooldownRemaining: number;
}

export interface GptActivateResult {
  giftName: string;
  useStatus: number | null;
  account: string;
  completedAt: string;
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

// 校验真实 cdkey，返回商品信息与当前状态（后端会校验产品类型为 gpt）。
export async function verifyGptCard(cdkey: string): Promise<{ card: GptCard; message: string }> {
  const { data } = await api.post<BaseResult & { card?: GptCard }>(
    '/gpt/card/verify',
    { cdkey: cdkey.trim() },
    { timeout: SLOW_TIMEOUT },
  );
  const r = unwrap(data);
  if (!r.card) {
    throw new Error('卡密校验返回为空');
  }
  return { card: r.card, message: r.message || '' };
}

// 提交激活：真实 cdkey + 账号 Session JSON（session_info），force 跳过套餐检查。
// 注意：上游「处理中」(use_status=-1) 时 ok=false，这里不抛异常，返回结果让页面提示稍后刷新。
export async function activateGpt(
  cdkey: string,
  sessionInfo: string,
  force = false,
): Promise<{ ok: boolean; message: string; order: GptActivateResult | null }> {
  const { data } = await api.post<BaseResult & { order?: GptActivateResult }>(
    '/gpt/activate',
    { cdkey: cdkey.trim(), sessionInfo: sessionInfo.trim(), force },
    { timeout: SLOW_TIMEOUT },
  );
  return {
    ok: Boolean(data?.ok),
    message: data?.message || '',
    order: data?.order || null,
  };
}
