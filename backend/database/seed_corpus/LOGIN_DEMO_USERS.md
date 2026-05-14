# Fixed demo logins (pre-seeded DB)

Run once after DB is up (from `backend/`):

```bash
python -m scripts.seed_judge_demo_users
```

## Credentials (same password for all)

| # | Email | Password |
|---|-------|----------|
| 1 | judgedemo1@judge.smartspend.example.com | Pass@123 |
| 2 | judgedemo2@judge.smartspend.example.com | Pass@123 |
| 3 | judgedemo3@judge.smartspend.example.com | Pass@123 |
| 4 | judgedemo4@judge.smartspend.example.com | Pass@123 |
| 5 | judgedemo5@judge.smartspend.example.com | Pass@123 |
| 6 | judgedemo6@judge.smartspend.example.com | Pass@123 |

Use **Sign in** on the app (not sign up). Dashboard month picker should match **current calendar month** for MTD numbers.

Re-run the script anytime to reset these six users to a fresh ~1113 transactions + demo goals/festival rows.

## If you see “Invalid email or password”

- **Counts in pgAdmin are misleading:** having six (or more) rows in `users` does not mean those rows are the judge accounts or that `password_hash` matches `Pass@123`. Only accounts created/updated by this script get the known hash.
- **Fix:** from `backend/`, run `python -m scripts.seed_judge_demo_users` again (uses project root `.env` for `DB_*`). Then sign in with the table above — **not** sign up.
- **Email domain:** use `@judge.smartspend.example.com` only. Legacy `@demo.smartspend.local` is rewritten when you run this script; do not rely on `.local` for new sign-ins after seeding.
