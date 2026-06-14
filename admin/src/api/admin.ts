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

// ===== Claude Pro 卡密映射（Gift 上游）=====
export interface ClaudeMappingItem {
  id: number;
  externalCode: string;
  realCard: string;
  giftName: string;
  app: string;
  status: string;
  note: string;
  createdAt: string;
}

export interface ClaudeImportResultItem {
  realCard: string;
  externalCode?: string;
  giftName?: string;
  status: string;
  message?: string;
  checkOk?: boolean;
}

export interface ClaudeOrderItem {
  id: number;
  externalCode: string;
  realCard: string;
  uid: string;
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

export async function importClaudeMappings(
  realCards: string[],
  note = '',
): Promise<{ created: number; total: number; results: ClaudeImportResultItem[] }> {
  const { data } = await api.post<BaseResult & { created: number; total: number; results: ClaudeImportResultItem[] }>(
    '/claude/admin/mappings/import',
    { realCards, note },
    { timeout: IMPORT_TIMEOUT },
  );
  const r = unwrap(data);
  return { created: r.created, total: r.total, results: r.results };
}

export async function listClaudeMappings(q = ''): Promise<ClaudeMappingItem[]> {
  const { data } = await api.get<BaseResult & { items: ClaudeMappingItem[] }>('/claude/admin/mappings', {
    params: { q },
  });
  return unwrap(data).items || [];
}

// 批量外部码反查原始 cdkey。
export async function lookupClaudeMappings(externalCodes: string[]): Promise<LookupResultItem[]> {
  const { data } = await api.post<BaseResult & { results: LookupResultItem[] }>('/claude/admin/mappings/lookup', {
    externalCodes,
  });
  return unwrap(data).results || [];
}

export async function updateClaudeMappingStatus(id: number, status: 'active' | 'disabled'): Promise<void> {
  const { data } = await api.patch<BaseResult>(`/claude/admin/mappings/${id}`, { status });
  unwrap(data);
}

// 重新生成外部码：旧码失效，新建指向同一真实 cdkey 的新外部码，返回新码。
export async function reissueClaudeMapping(id: number): Promise<string> {
  const { data } = await api.post<BaseResult & { externalCode?: string }>(`/claude/admin/mappings/${id}/reissue`, {});
  return unwrap(data).externalCode || '';
}

export async function deleteClaudeMapping(id: number): Promise<void> {
  const { data } = await api.delete<BaseResult>(`/claude/admin/mappings/${id}`);
  unwrap(data);
}

// 批量启用/停用/删除 Claude 卡密映射，返回实际影响条数。
export async function batchClaudeMappings(ids: number[], action: BatchAction): Promise<number> {
  const { data } = await api.post<BaseResult & { affected: number }>('/claude/admin/mappings/batch', { ids, action });
  return unwrap(data).affected || 0;
}

export async function listClaudeOrders(q = ''): Promise<ClaudeOrderItem[]> {
  const { data } = await api.get<BaseResult & { items: ClaudeOrderItem[] }>('/claude/admin/orders', {
    params: { q },
  });
  return unwrap(data).items || [];
}
