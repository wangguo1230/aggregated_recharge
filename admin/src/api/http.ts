import axios, { type AxiosInstance } from 'axios';

export interface ApiClientOptions {
  baseURL?: string;
  getToken?: () => string;
  timeout?: number;
}

export function createApiClient(options: ApiClientOptions = {}): AxiosInstance {
  const client = axios.create({
    baseURL: options.baseURL || '/api',
    timeout: options.timeout ?? 30000,
  });

  client.interceptors.request.use((config) => {
    const token = options.getToken?.();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  });

  client.interceptors.response.use(
    (response) => response,
    (error) => {
      const status = error.response?.status;
      const detail = error.response?.data?.detail || error.response?.data?.message || error.message;
      const message = String(detail || '请求失败');
      return Promise.reject(new Error(status ? `HTTP ${status}: ${message}` : message));
    },
  );

  return client;
}
