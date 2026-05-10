# Database Migrations — Canonical Path

This directory (`backend/database/migrations/`) is the **only** path
from which production migrations are read going forward.

## Status as of audit (2026-05-10)

The audit (`CTO_AUDIT.md` issue #7) flagged a risk of multiple
migration directories causing schema drift.  Investigation showed
**only one path actually exists** in the repo — the single root cause
of confusion is that this directory has **two parallel numbering
tracks** rather than two paths.

## Two number tracks

| Number prefix family | Owner | Examples |
| --- | --- | --- |
| `00X_phaseY_*.sql` | Risk / fraud engine (Phase 1-12) | `001_phase1_event_log.sql`, `002_phase2_feature_columns.sql`, ..., `012_phase12_orchestrator.sql` |
| `00X_<feature>.sql` | Product features (auth, banking, etc.) | `001_add_authentication.sql`, `002_bank_connections.sql`, `003_user_important_days.sql` |

This means there are duplicate prefixes like `001_*`, `002_*`,
`003_*` — **that is intentional and harmless** because each migration
is order-independent (creates its own tables / columns) and is applied
exactly once via `apply_migrations.py` tracking against a
`_migration_history` table.

## Numbering convention going forward

Use the next free number in the **risk/fraud track** if your migration
touches the risk-engine subsystem (transactions table, ml_*, gnn_*,
risk_*, orchestration_decisions, etc.).  Otherwise use the next free
number in the **product-features track**.

| Range | Reserved for |
| --- | --- |
| `001-008` | Phase 1-8 risk engine + auth/banking baseline |
| `009-012` | Phase 9-12 (2026 parity) — investigations, GNN, DNN, orchestrator |
| `013+`    | Future — number sequentially within whichever track the migration belongs to |

> Never re-use a migration number that has already been applied to a
> live database.  If a number was assigned but the migration was
> later deleted, leave the number burned and skip it.

## Legacy / non-canonical paths

The repo also contains:

| Path | Contents | Use it? |
| --- | --- | --- |
| `database/` (top-level) | `schema.sql`, `db.py`, `seed_data.py`, `validate.py`, `fraud_schema.sql`, `festival_purchase_schema.sql` | **NO for migrations.** These are the bootstrap "schema as a single file" + Python helper scripts.  They predate the migrations system and remain as a fast path for spinning up a fresh dev database from scratch. |

If you find any other `migrations/` directory in the future, treat it
as legacy and fold its files into this canonical path.

## Applying migrations

### Manual (single migration)

```bash
psql -U postgres -d smartspend_db \
     -f backend/database/migrations/0XX_name.sql
```

### Automated (idempotent)

A helper script ships alongside this directory that applies every
unseen `*.sql` in numerical order and records each one in a
`_migration_history` table.  Re-running is a safe no-op.

```bash
cd backend
python -m scripts.apply_migrations
```

(See `backend/scripts/apply_migrations.py` for the exact logic.)

## Conventions for new migration files

1. **One change per file.**  If you need to add a table AND alter a
   different table, create two files.
2. **Idempotent where possible.**  `CREATE TABLE IF NOT EXISTS`,
   `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, etc.  Makes re-runs
   safe even if `_migration_history` is wiped.
3. **No DDL + DML mixing.**  Schema migrations shouldn't seed data;
   put seed data in `database/seed_data.py` or a separate script.
4. **Forward-only.**  No `DROP TABLE` of a teammate's table without
   a written announcement on the PR + an explicit two-week deprecation
   window.
5. **Header comment** at top of each file: phase, owner, brief
   description, and date.  See `009_phase9_investigations.sql` for
   the format used by the Phase 9-12 batch.
