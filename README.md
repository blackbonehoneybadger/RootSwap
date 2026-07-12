# RootSwap

**RootSwap** — privacy-focused, non-custodial-where-possible агрегатор криптообмена в виде Telegram Bot + Telegram Mini App + Backend API.

Направления первой версии: `RUB ⇄ XMR`, `RUB ⇄ USDT (TRC20)`, `RUB ⇄ BTC`.

> ⚠️ **Current status: MOCK / SANDBOX ONLY.**
>
> - **Real money is disabled in this version.**
> - **Mock partners are synthetic.**
> - **Sandbox does not move real funds.**
> - **Production launch requires partner contract, security audit, legal review, and operational runbook.**

RootSwap **никогда** не запрашивает seed-фразы или приватные ключи. Формулировки, которые мы используем: *privacy-focused*, *non-custodial where possible*, *partner requirements may vary*, *fiat payments may be identifiable*. Мы **не** обещаем анонимность и **не** обходим KYC/AML — требования партнёров могут различаться.

---

## Что работает (mock/sandbox)

- Telegram-авторизация (проверка HMAC `initData`), JWT-сессии.
- Полный пользовательский flow в Mini App: выбор направления → котировки от нескольких mock-партнёров (best / fastest / lowest fee, RootScore, разбивка комиссий, бейдж DEMO/SANDBOX/REAL) → двойное подтверждение → mock-реквизиты (СБП / банковский перевод / карта) или mock-deposit-address → статусы в реальном времени → история → рефералка.
- Partner Engine: `FiatPartnerAdapter` / `CryptoPartnerAdapter`, `PartnerRegistry`, два детерминированных mock-партнёра + reference mock-crypto адаптер.
- Order state machine с единым transition-сервисом, optimistic locking (`version`), audit-логом запрещённых переходов.
- Webhooks: подпись HMAC, окно timestamp (replay-protection), дедупликация `external_event_id`, идемпотентная обработка, retry + dead-letter.
- Polling fallback для потерянных webhook'ов; авто-EXPIRED по истечении реквизитов.
- Circuit breaker per-partner (CLOSED → OPEN → HALF_OPEN, состояние в БД).
- Immutable ledger c идемпотентными posting_key; reconciliation всегда 0.
- Одноуровневая реферальная система: начисление ровно один раз после COMPLETED, заморозка при DISPUTED, отмена при REFUND.
- Admin API с RBAC (SUPPORT < OPERATIONS < FINANCE < ADMIN) и обязательным AuditLog; emergency stop.
- Шифрование чувствительных полей (Fernet), маскирование в UI и логах, structured JSON-логи с request_id.

## Что НЕ работает (сознательно)

- Реальные деньги, реальные банковские реквизиты, реальные партнёрские API.
- Custodial-кошельки, вывод средств, автоматический вывод в Monero.
- Токены, DAO, NFT, staking, AI-фичи, Treasury.
- Обход KYC/AML (и не будет работать никогда).

---

## Быстрый старт (dev)

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp ../.env.example ../.env   # заполните значения
# локальная БД по умолчанию: postgresql+asyncpg://rootswap:rootswap@localhost:5432/rootswap
alembic upgrade head
uvicorn app.main:app --reload
```

API: `http://localhost:8000`, Swagger: `http://localhost:8000/docs` (отключён в production).

### Mini App

```bash
cd mini-app
npm install
npm run dev        # http://localhost:5173
```

### Bot

```bash
cd bot
pip install -r requirements.txt
TELEGRAM_BOT_TOKEN=... MINI_APP_URL=https://... python bot.py
```

## Тесты

```bash
cd backend
pytest            # 127 тестов: unit + integration + e2e mock flows
ruff check app tests
```

Mini App: `cd mini-app && npm run typecheck && npm run build`.

## Docker

```bash
# dev: наружу открыты API (8000), Mini App (5173), Postgres, Redis
docker compose -f docker-compose.dev.yml up --build

# prod: наружу только nginx 80/443; Postgres/Redis не публикуются
docker compose -f docker-compose.prod.yml up --build -d
```

Production compose **не стартует** без обязательных секретов (`:?`-синтаксис), а backend дополнительно валидирует конфигурацию на старте и **отказывается запускаться**, если: `JWT_SECRET` слабый/дефолтный, нет `ENCRYPTION_KEY`, нет `REDIS_PASSWORD`, нет/слабый `PARTNER_WEBHOOK_SECRET`, включены `ALLOW_MOCK_PARTNERS`/`ALLOW_SANDBOX_PARTNERS`, включён `DEBUG` или `TELEGRAM_AUTH_INSECURE_SKIP`.

---

## Threat model (сокращённо)

| Угроза | Митигация |
|---|---|
| Подделка Telegram-аутентификации | HMAC-проверка `initData` по алгоритму Telegram, max-age, JWT c issuer |
| Подделка / replay partner-webhook | HMAC-подпись `timestamp.body`, окно ±300 c, дедупликация `event_id`, идемпотентные posting_key |
| Двойное списание / двойной reward | Уникальные constraint'ы (idempotency_key, quote_id, posting_key, order_id в rewards) |
| Утечка реквизитов/кошельков | Шифрование Fernet в БД, маскирование в API/логах, тест «sensitive values absent from logs» |
| Злоупотребление admin-доступом | RBAC по ролям, каждый admin-вызов пишет AuditLog (actor, request_id, IP) |
| Отказ партнёра | Circuit breaker, failover на второго партнёра, polling fallback |
| Инцидент | Emergency stop блокирует новые котировки/заявки мгновенно |
| Перебор API | Rate limiting (Redis) + nginx limit_req |

## Privacy limitations (честно)

- **Fiat payments may be identifiable**: банковские переводы/СБП идентифицируемы банками по определению.
- Партнёры могут требовать KYC — **partner requirements may vary**; RootSwap не обходит эти требования.
- Telegram знает факт использования бота.
- Мы не обещаем «анонимность», «untraceable» или «no trace» — это неправда для fiat-потоков.

## Production blockers (не запускать с реальными деньгами, пока не закрыто)

1. Нет договора с реальным партнёром (fiat и crypto), нет их sandbox/production ключей.
2. Не проведён внешний security-аудит (код + инфраструктура + pentest).
3. Не проведён legal/compliance review для целевых юрисдикций (криптообмен, AML/CFT, санкционные списки).
4. Нет HTTPS-сертификатов и домена (nginx 443 закомментирован).
5. Нет мониторинга/алертинга (метрики есть, алертов нет) и on-call процесса.
6. Нет бэкапов Postgres и процедуры восстановления.
7. Реферальные выплаты — только учёт (Ledger/rewards), механизм выплат не реализован.
8. KYC/AML-скрининг и risk-scoring — заготовка (RiskFlag), без реальных провайдеров.

## Runbook: Emergency stop

1. `POST /api/v1/admin/emergency-stop` (роль ADMIN, JSON `{"reason": "..."}`) — новые котировки и заявки отвечают `503 emergency_stop_active`. Активные заявки продолжают обрабатываться.
2. Диагностируйте инцидент: `/api/v1/admin/webhooks` (dead-letter), `/api/v1/admin/partners` (circuit breaker), `/metrics`.
3. При проблеме одного партнёра вместо полного стопа: `POST /api/v1/admin/partners/{code}/disable`.
4. Снятие: `DELETE /api/v1/admin/emergency-stop`. Все действия фиксируются в AuditLog.

## Runbook: Dispute / Refund

1. Пользователь открывает спор из Mini App (`POST /orders/{id}/dispute`) — заявка переходит в `DISPUTED`, referral reward замораживается, realized profit **не** признаётся.
2. Support исследует (admin: order detail, events, webhooks, partner reference).
3. Исходы: admin transition `DISPUTED → PROCESSING/COMPLETED` (спор отклонён/решён в пользу продолжения), либо refund.
4. Refund: `POST /api/v1/admin/orders/{id}/refund` (роль FINANCE) — цепочка `REFUND_REQUESTED → REFUND_PROCESSING → REFUNDED`, ledger получает сторнирующие проводки, reward отменяется, reconciliation остаётся нулевой. `REFUND_FAILED` можно перезапустить транзишеном админа.

## Partner integration guide

1. Реализуйте адаптер: наследуйте `FiatPartnerAdapter` или `CryptoPartnerAdapter` (`backend/app/partners/base.py`) — все методы контракта обязательны, включая `verify_webhook()` и `health_check()`.
2. Зарегистрируйте адаптер в `register_default_partners()` (`app/main.py`) через `registry.register_adapter(...)` — строка в таблице `partners` создастся автоматически.
3. `quote_source_type` адаптера: `SANDBOX` для песочницы партнёра, `REAL` — только после аудита и договора. `MOCK`/`SANDBOX` в production отфильтровываются и заблокированы стартовой валидацией.
4. Секрет webhook'а партнёра — отдельная env-переменная; подпись проверяется в `verify_webhook`.
5. Обязательные тесты перед включением: quote/order happy-path, отказ до создания заявки, webhook подпись/replay/дедуп, refund, лимиты, health check.

## Webhook guide (для партнёров)

- Endpoint: `POST /api/v1/webhooks/partners/{partner_code}`
- Заголовки: `X-Timestamp` (unix seconds), `X-Signature` = `HMAC_SHA256(secret, timestamp + "." + raw_body)` hex.
- Тело: JSON `{"event_id": "...", "event_type": "...", "partner_order_id": "..."}`.
- `event_type`: `payment_detected | payment_confirming | processing | payout_sent | completed | expired | failed | cancelled | refund_processing | refunded | refund_failed`.
- Гарантии на нашей стороне: дедупликация по `event_id`, идемпотентность, retry не создаёт дублей в ledger/rewards. Отдавайте нам повтор события при любом сомнении — это безопасно.

## Legal / compliance warning

Криптообменная деятельность лицензируется/регулируется в большинстве юрисдикций (AML/CFT, KYC, санкционный скрининг, налоговая отчётность). **Запуск этого кода с реальными деньгами без юридической проверки и соответствующих разрешений может быть незаконным.** Эта версия — технологический прототип на синтетических данных.

## Before-real-money checklist

- [ ] Подписан договор с fiat-партнёром и crypto-партнёром; получены production-ключи.
- [ ] Пройден внешний security-аудит и pentest; критические находки закрыты.
- [ ] Legal/compliance review завершён; определены юрисдикции и ограничения.
- [ ] `ENVIRONMENT=production`, `ALLOW_MOCK_PARTNERS=false`, `ALLOW_SANDBOX_PARTNERS=false` — стартовая валидация зелёная.
- [ ] Все секреты сгенерированы заново и хранятся в secret manager (не в .env в репозитории).
- [ ] HTTPS + HSTS включены; CSP проверена.
- [ ] Настроены бэкапы Postgres + восстановление отрепетировано.
- [ ] Мониторинг, алерты, on-call, инцидент-процесс.
- [ ] Runbook'и emergency stop / dispute / refund отрепетированы на sandbox.
- [ ] Лимиты сумм и risk-правила согласованы с партнёром.
- [ ] Проверено: в логах нет полных реквизитов/кошельков (тест + ручная проверка).
