import { createApiClient } from './http';

// 74 渠道充值接口：直接调用后端 /api/vip/*（后端转发 zzlokp12 上游）。客户输入卡密 + 账号 JSON。
const api = createApiClient();

// 上游较慢时给足等待时间（后端上游超时 60s），避免前端先超时造成「卡已扣、却显示失败」。
const SLOW_TIMEOUT = 120_000;

interface BaseResult {
  ok: boolean;
  message?: string;
}

function unwrap<T extends BaseResult>(data: T): T {
  if (!data?.ok) {
    throw new Error(data?.message || '请求失败');
  }
  return data;
}

// 验卡：卡密 + 账号 JSON。
export async function verifyVipCard(cdk: string, account: string): Promise<string> {
  const { data } = await api.post<BaseResult>(
    '/vip/card/verify',
    { cdk: cdk.trim(), account: account.trim() },
    { timeout: SLOW_TIMEOUT },
  );
  return unwrap(data).message || '卡密验证通过';
}

// 充值：卡密 + 账号 JSON。失败时不抛异常，返回结果让页面提示。
export async function activateVip(
  cdk: string,
  account: string,
): Promise<{ ok: boolean; message: string; account: string }> {
  const { data } = await api.post<BaseResult & { order?: { account?: string; status?: string } }>(
    '/vip/activate',
    { cdk: cdk.trim(), account: account.trim() },
    { timeout: SLOW_TIMEOUT },
  );
  return {
    ok: Boolean(data?.ok),
    message: data?.message || '',
    account: data?.order?.account || '',
  };
}
