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

export async function deleteSmsMapping(id: number): Promise<void> {
  const { data } = await api.delete<BaseResult>(`/sms/admin/mappings/${id}`);
  unwrap(data);
}
