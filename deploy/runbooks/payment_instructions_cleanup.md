# Payment instructions cleanup (manual)

Use this runbook **only** when Alembic migration `0002_pi_unique` fails because of:

- duplicate `payment_instructions.order_id` rows, or
- `NULL` `order_id` values.

The migration **never** deletes data automatically.

## Steps

1. Take a PostgreSQL backup / snapshot.
2. Report conflicts:

```sql
SELECT order_id, COUNT(*), array_agg(id) AS ids
FROM payment_instructions
GROUP BY order_id
HAVING COUNT(*) > 1;

SELECT id FROM payment_instructions WHERE order_id IS NULL;
```

3. Decide keep/archive policy with an operator (usually keep the newest non-deleted PI).
4. Archive extras to a backup table, then delete duplicates **manually**.
5. Re-run `alembic upgrade head`.

Do not run destructive SQL from CI or deploy hooks.
