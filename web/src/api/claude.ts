import { createApiClient } from './http';

// Claude Pro 充值接口：只与本项目后端交互（/api/claude/*），由后端解析外部码并转发到 Gift 上游。
const api = createApiClient();

export interface ClaudeCard {
  code: string;
  giftName: string;
  app: string;
  useStatus: number | null;
  statusHint: string;
  account: string;
  completedAt: string;
  inCooldown: boolean;
  cooldownRemaining: number;
}

export interface ClaudeActivateResult {
  externalCode: string;
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

// 校验外部码，返回商品信息与当前状态（不暴露真实 cdkey）。
export async function verifyClaudeCard(cardCode: string): Promise<{ card: ClaudeCard; message: string }> {
  const { data } = await api.post<BaseResult & { card?: ClaudeCard }>('/claude/card/verify', {
    cardCode: cardCode.trim(),
  });
  const r = unwrap(data);
  if (!r.card) {
    throw new Error('卡密校验返回为空');
  }
  return { card: r.card, message: r.message || '' };
}

// 提交激活：外部码 + Claude Organization ID（uid）。
// 注意：上游「处理中」(use_status=-1) 时 ok=false，这里不抛异常，返回结果让页面提示稍后刷新。
export async function activateClaude(
  cardCode: string,
  uid: string,
): Promise<{ ok: boolean; message: string; order: ClaudeActivateResult | null }> {
  const { data } = await api.post<BaseResult & { order?: ClaudeActivateResult }>('/claude/activate', {
    cardCode: cardCode.trim(),
    uid: uid.trim(),
  });
  return {
    ok: Boolean(data?.ok),
    message: data?.message || '',
    order: data?.order || null,
  };
}
