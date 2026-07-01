import { createApiClient } from './http';

const TOKEN_KEY = 'askwhy:adminToken';

export function getAdminToken(): string {
  try {
    return localStorage.getItem(TOKEN_KEY) || '';
  } catch {
    return '';
  }
}

export function setAdminToken(token: string): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // 忽略
  }
}

// 管理接口客户端：自动带上 Bearer 口令。
const api = createApiClient({ getToken: getAdminToken });

// 卡密导入会逐条对上游做校验/生成，数量多时耗时较长，单独放宽超时（默认 30s 不够用）。
const IMPORT_TIMEOUT = 180_000;

// 批量操作动作（启用/停用/删除）。
export type BatchAction = 'enable' | 'disable' | 'delete';

export interface MappingItem {
  id: number;
  externalCode: string;
  realCard: string;
  cardType: string;
  cardTypeLabel: string;
  status: string;
  note: string;
  createdAt: string;
}

export interface OrderItem {
  id: number;
  orderId: string;
  externalCode: string;
  realCard: string;
  cardTypeLabel: string;
  status: string;
  accountEmail: string;
  resultMessage: string;
  submitIp: string;
  subscriptionUntil: string;
  createdAt: string;
  updatedAt: string;
}

export interface ImportResultItem {
  realCard: string;
  externalCode?: string;
  typeLabel?: string;
  status: string;
  message?: string;
  verifyOk?: boolean;
}

// 批量反查结果：外部码/兑换码 → 原始卡密。
export interface LookupResultItem {
  input: string;
  found: boolean;
  externalCode: string;
  realCard: string;
  phone?: string;
  cardTypeLabel?: string;
  status?: string;
}

interface BaseResult {
  ok: boolean;
  message?: string;
}

function unwrap<T extends BaseResult>(data: T): T {
  if (!data?.ok) throw new Error(data?.message || '请求失败');
  return data;
}

// 校验口令（登录）。
export async function adminCheck(): Promise<void> {
  const { data } = await api.post<BaseResult>('/askwhy/admin/session', {});
  unwrap(data);
}

export async function importMappings(
  realCards: string[],
  note = '',
): Promise<{ created: number; total: number; results: ImportResultItem[] }> {
  const { data } = await api.post<BaseResult & { created: number; total: number; results: ImportResultItem[] }>(
    '/askwhy/admin/mappings/import',
    { realCards, note },
    { timeout: IMPORT_TIMEOUT },
  );
  const r = unwrap(data);
  return { created: r.created, total: r.total, results: r.results };
}

export async function listMappings(q = ''): Promise<MappingItem[]> {
  const { data } = await api.get<BaseResult & { items: MappingItem[] }>('/askwhy/admin/mappings', {
    params: { q },
  });
  return unwrap(data).items || [];
}

// 批量外部码反查原始卡密。
export async function lookupMappings(externalCodes: string[]): Promise<LookupResultItem[]> {
  const { data } = await api.post<BaseResult & { results: LookupResultItem[] }>('/askwhy/admin/mappings/lookup', {
    externalCodes,
  });
  return unwrap(data).results || [];
}

export async function updateMappingStatus(id: number, status: 'active' | 'disabled'): Promise<void> {
  const { data } = await api.patch<BaseResult>(`/askwhy/admin/mappings/${id}`, { status });
  unwrap(data);
}

// 重新生成外部码：旧码失效，新建指向同一真实卡密的新外部码，返回新码。
export async function reissueMapping(id: number): Promise<string> {
  const { data } = await api.post<BaseResult & { externalCode?: string }>(`/askwhy/admin/mappings/${id}/reissue`, {});
  return unwrap(data).externalCode || '';
}

export async function deleteMapping(id: number): Promise<void> {
  const { data } = await api.delete<BaseResult>(`/askwhy/admin/mappings/${id}`);
  unwrap(data);
}

export async function listOrders(q = ''): Promise<OrderItem[]> {
  const { data } = await api.get<BaseResult & { items: OrderItem[] }>('/askwhy/admin/orders', {
    params: { q },
  });
  return unwrap(data).items || [];
}

// ===== 接码卡密映射 =====
export interface SmsMappingItem {
  id: number;
  externalCode: string;
  phone: string;
  realCard: string;
  status: string;
  note: string;
  createdAt: string;
}

export interface SmsImportResultItem {
  phone: string;
  externalCode?: string;
  status: string;
  message?: string;
}

export async function importSmsMappings(
  realCards: string[],
  note = '',
): Promise<{ created: number; total: number; results: SmsImportResultItem[] }> {
  const { data } = await api.post<BaseResult & { created: number; total: number; results: SmsImportResultItem[] }>(
    '/sms/admin/mappings/import',
    { realCards, note },
    { timeout: IMPORT_TIMEOUT },
  );
  const r = unwrap(data);
  return { created: r.created, total: r.total, results: r.results };
}

export async function listSmsMappings(q = ''): Promise<SmsMappingItem[]> {
  const { data } = await api.get<BaseResult & { items: SmsMappingItem[] }>('/sms/admin/mappings', {
    params: { q },
  });
  return unwrap(data).items || [];
}

// 批量兑换码反查接码原始卡密。
export async function lookupSmsMappings(externalCodes: string[]): Promise<LookupResultItem[]> {
  const { data } = await api.post<BaseResult & { results: LookupResultItem[] }>('/sms/admin/mappings/lookup', {
    externalCodes,
  });
  return unwrap(data).results || [];
}

export async function updateSmsMappingStatus(id: number, status: 'active' | 'disabled'): Promise<void> {
  const { data } = await api.patch<BaseResult>(`/sms/admin/mappings/${id}`, { status });
  unwrap(data);
}

// 重新生成兑换码：旧码失效，新建指向同一接码卡密的新兑换码，返回新码。
export async function reissueSmsMapping(id: number): Promise<string> {
  const { data } = await api.post<BaseResult & { externalCode?: string }>(`/sms/admin/mappings/${id}/reissue`, {});
  return unwrap(data).externalCode || '';
}

export async function deleteSmsMapping(id: number): Promise<void> {
  const { data } = await api.delete<BaseResult>(`/sms/admin/mappings/${id}`);
  unwrap(data);
}

// 批量启用/停用/删除接码卡密映射，返回实际影响条数。
export async function batchSmsMappings(ids: number[], action: BatchAction): Promise<number> {
  const { data } = await api.post<BaseResult & { affected: number }>('/sms/admin/mappings/batch', { ids, action });
  return unwrap(data).affected || 0;
}

export interface GptOrderItem {
  id: number;
  realCard: string;
  giftName: string;
  useStatus: number;
  status: string;
  resultMessage: string;
  account: string;
  completedAt: string;
  submitIp: string;
  createdAt: string;
  updatedAt: string;
}

// GPT 充值直调 Gift（无映射），仅有充值记录可供对账/售后。
export async function listGptOrders(q = ''): Promise<GptOrderItem[]> {
  const { data } = await api.get<BaseResult & { items: GptOrderItem[] }>('/gpt/admin/orders', {
    params: { q },
  });
  return unwrap(data).items || [];
}

// ===== GPT 批量订阅 =====
export interface GptBatchItemInput {
  cdkey: string;
  sessionInfo: string;
}

export interface GptBatchCreateResultItem {
  seq: number;
  email: string;
  cdkeyLast4: string;
  status: string;
  message: string;
}

export interface GptBatchSummary {
  id: number;
  channel: string;
  status: string;
  force: boolean;
  note: string;
  total: number;
  concurrency: number;
  cancelRequested: boolean;
  inFlight: number;
  retryWaiting: boolean;
  pausedReason: string;
  counts: Record<string, number>;
  createdAt: string;
  startedAt: string;
  finishedAt: string;
}

export interface GptBatchItem {
  seq: number;
  email: string;
  cdkeyLast4: string;
  status: string;
  useStatus: number | null;
  resultCode: string;
  resultMessage: string;
  account: string;
  completedAt: string;
  attempts: number;
}

export async function createGptBatch(
  items: GptBatchItemInput[],
  channel: string,
  force: boolean,
  note = '',
  concurrency = 0,
): Promise<{ batchId: number; total: number; accepted: number; skipped: number; results: GptBatchCreateResultItem[] }> {
  const { data } = await api.post<
    BaseResult & { batchId: number; total: number; accepted: number; skipped: number; results: GptBatchCreateResultItem[] }
  >('/gpt/admin/batch', { items, channel, force, note, concurrency }, { timeout: IMPORT_TIMEOUT });
  const r = unwrap(data);
  return { batchId: r.batchId, total: r.total, accepted: r.accepted, skipped: r.skipped, results: r.results };
}

export async function listGptBatches(channel = '', q = '', limit = 100): Promise<GptBatchSummary[]> {
  const { data } = await api.get<BaseResult & { items: GptBatchSummary[] }>('/gpt/admin/batch', {
    params: { channel, q, limit },
  });
  return unwrap(data).items || [];
}

export async function getGptBatch(id: number): Promise<{ batch: GptBatchSummary; items: GptBatchItem[] }> {
  const { data } = await api.get<BaseResult & { batch: GptBatchSummary; items: GptBatchItem[] }>(`/gpt/admin/batch/${id}`);
  const r = unwrap(data);
  return { batch: r.batch, items: r.items || [] };
}

export async function cancelGptBatch(id: number): Promise<void> {
  const { data } = await api.post<BaseResult>(`/gpt/admin/batch/${id}/cancel`, {});
  unwrap(data);
}

// concurrency>0 时同时更新该批次的并发数（重跑用新并发）。
export async function resumeGptBatch(id: number, concurrency = 0): Promise<void> {
  const { data } = await api.post<BaseResult>(`/gpt/admin/batch/${id}/resume`, {}, { params: { concurrency } });
  unwrap(data);
}

// 重新提交单个失败/跳过的条目；NEEDS_REVIEW 需 force=true 显式确认。
export async function retryGptBatchItem(batchId: number, seq: number, force = false, concurrency = 0): Promise<void> {
  const { data } = await api.post<BaseResult>(
    `/gpt/admin/batch/${batchId}/items/${seq}/retry`,
    {},
    { params: { force, concurrency } },
  );
  unwrap(data);
}

// 一键重试整批失败/跳过条目；includeReview=true 连 NEEDS_REVIEW 一起重试。
export async function retryFailedGptBatch(batchId: number, includeReview = false, concurrency = 0): Promise<number> {
  const { data } = await api.post<BaseResult & { reset?: number }>(
    `/gpt/admin/batch/${batchId}/retry-failed`,
    {},
    { params: { include_review: includeReview, concurrency } },
  );
  return unwrap(data).reset || 0;
}

// 导出批次结果 CSV（浏览器下载）。
export async function exportGptBatch(batchId: number): Promise<void> {
  const res = await api.get(`/gpt/admin/batch/${batchId}/export`, { responseType: 'blob' });
  const url = URL.createObjectURL(res.data as Blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `gpt-batch-${batchId}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
