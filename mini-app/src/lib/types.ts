export type Direction = 'BUY' | 'SELL'

export type PaymentMethod = 'SBP' | 'bank_transfer' | 'card_transfer'

export type QuoteSourceType = 'MOCK' | 'SANDBOX' | 'REAL'

export type OrderStatus =
  | 'CREATED'
  | 'QUOTE_CONFIRMED'
  | 'AWAITING_PAYMENT'
  | 'PAYMENT_DETECTED'
  | 'PAYMENT_CONFIRMING'
  | 'PROCESSING'
  | 'PAYOUT_SENT'
  | 'COMPLETED'
  | 'EXPIRED'
  | 'FAILED'
  | 'DISPUTED'
  | 'REFUND_REQUESTED'
  | 'REFUND_PROCESSING'
  | 'REFUNDED'
  | 'REFUND_FAILED'
  | 'CANCELLED'

export interface AuthUser {
  id: string
  telegram_id: number
  username: string | null
  first_name: string | null
  referral_code: string
}

export interface AuthResponse {
  access_token: string
  user: AuthUser
}

export interface QuoteRequest {
  direction: Direction
  from_asset: string
  from_network: string | null
  to_asset: string
  to_network: string | null
  amount_in: string
  payment_method: PaymentMethod | null
  bank: string | null
}

export interface Quote {
  quote_id: string
  partner_code: string
  partner_name: string
  amount_in: string
  amount_out: string
  exchange_rate: string
  service_fee: string
  partner_fee: string
  network_fee: string
  total_fee: string
  root_score: number
  quote_source_type: QuoteSourceType
  expires_at: string
  kyc_required: boolean
  estimated_time_minutes: number
  labels: string[]
}

export interface QuotesResponse {
  quotes: Quote[]
}

export interface PayoutDetails {
  payment_method: string
  bank: string
  account: string
}

export interface CreateOrderRequest {
  quote_id: string
  idempotency_key: string
  wallet_address: string | null
  payout_details: PayoutDetails | null
}

export interface PaymentInstructions {
  payment_method: string
  bank_name: string
  masked_recipient_name: string
  masked_account: string | null
  masked_card: string | null
  masked_phone: string | null
  amount: string
  currency: string
  payment_comment: string
  expires_at: string
}

export interface OrderEvent {
  status: string
  message: string
  created_at: string
}

export interface Order {
  id: string
  status: OrderStatus
  direction: Direction
  from_asset: string
  from_network: string | null
  to_asset: string
  to_network: string | null
  amount_in: string
  amount_out: string
  exchange_rate: string
  service_fee: string
  partner_fee: string
  network_fee: string
  total_fee: string
  quote_source_type: QuoteSourceType
  wallet_address_masked: string | null
  payout_details_masked: string | null
  created_at: string
  payment_instructions: PaymentInstructions | null
  deposit_address: string | null
  deposit_network: string | null
  events: OrderEvent[]
}

export interface OrdersResponse {
  orders: Order[]
}

export interface RewardTotal {
  currency: string
  amount: string
}

export interface ReferralReward {
  order_id: string
  reward_amount: string
  reward_currency: string
  status: string
  created_at: string
}

export interface ReferralStats {
  referral_code: string
  referral_link: string
  referred_count: number
  active_referred_count: number
  total_rewards: RewardTotal[]
  rewards: ReferralReward[]
}
