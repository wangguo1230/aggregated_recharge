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
  realCardLast4: string;
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
  cardLast4: string;
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
  realCardLast4: string;
  externalCode?: string;
  typeLabel?: string;
  status: string;
  message?: string;
  verifyOk?: boolean;
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
