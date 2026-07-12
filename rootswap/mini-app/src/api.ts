const API_URL = import.meta.env.VITE_API_URL || '/api';

export interface Quote {
  id: string;
  partner_code: string;
  direction: string;
  from_asset: string;
  from_network: string | null;
  to_asset: string;
  to_network: string | null;
  amount_in: number;
  amount_out: number;
  exchange_rate: number;
  service_fee: number;
  partner_fee: number;
  network_fee: number;
  total_fee: number;
  root_score: number;
  quote_source_type: string;
  expires_at: string;
  kyc_required: boolean;
  estimated_time_seconds: number;
}

export interface Order {
  id: string;
  quote_id: string;
  status: string;
  direction: string;
  from_asset: string;
  to_asset: string;
  amount_in: number;
  amount_out: number;
  total_fee: number;
  quote_source_type: string;
  wallet_address_masked: string | null;
  created_at: string;
  payment_instructions?: {
    masked_account: string | null;
    masked_card: string | null;
    masked_phone: string | null;
    deposit_address_masked: string | null;
    payment_method: string;
    bank_name: string | null;
    amount: number;
    currency: string;
    payment_comment: string | null;
    expires_at: string;
  };
}

let token: string | null = localStorage.getItem('rootswap_token');

export function setToken(t: string) {
  token = t;
  localStorage.setItem('rootswap_token', t);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

export async function authTelegram(initData: string, referralCode?: string) {
  const data = await request<{ access_token: string }>('/v1/auth/telegram', {
    method: 'POST',
    body: JSON.stringify({ init_data: initData, referral_code: referralCode }),
  });
  setToken(data.access_token);
  return data;
}

export async function createQuote(body: Record<string, unknown>) {
  return request<{ best: Quote | null; fastest: Quote | null; lowest_fee: Quote | null; all: Quote[] }>(
    '/v1/quotes',
    { method: 'POST', body: JSON.stringify(body) },
  );
}

export async function createOrder(body: Record<string, unknown>) {
  return request<Order>('/v1/orders', { method: 'POST', body: JSON.stringify(body) });
}

export async function getOrders() {
  return request<Order[]>('/v1/orders');
}

export async function getOrder(id: string) {
  return request<Order>(`/v1/orders/${id}`);
}

export async function getReferralStats() {
  return request<{
    referral_code: string;
    referral_link: string;
    referred_count: number;
    total_rewards: number;
    rewards: { order_id: string; amount: number; status: string }[];
  }>('/v1/referral/stats');
}

export async function createDispute(orderId: string, reason: string) {
  return request(`/v1/orders/${orderId}/dispute`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  });
}

export function badgeClass(sourceType: string): string {
  if (sourceType === 'REAL') return 'badge badge-real';
  if (sourceType === 'SANDBOX') return 'badge badge-sandbox';
  return 'badge badge-mock';
}
