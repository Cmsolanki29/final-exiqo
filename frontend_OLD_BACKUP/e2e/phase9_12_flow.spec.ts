import { test, expect, request as pwRequest } from '@playwright/test';

const API_BASE = process.env.API_BASE_URL || 'http://localhost:8001/api';
const ADMIN_TOKEN = process.env.ADMIN_TOKEN || 'dev-admin-secret';
const TEST_JWT = process.env.TEST_JWT || '';
const TEST_EMAIL = process.env.TEST_EMAIL || 'abc@gmail.com';
const TEST_PASSWORD = process.env.TEST_PASSWORD || 'Pass@123';

const adminHeaders: Record<string, string> = {
  'X-Admin-Token': ADMIN_TOKEN,
  ...(TEST_JWT ? { Authorization: `Bearer ${TEST_JWT}` } : {}),
};

// ── TEST 1 — public health probes for all 4 phases ─────────────────────────
test('Phase 9-12 health endpoints all return enabled:true', async () => {
  const ctx = await pwRequest.newContext();

  const inv = await ctx.get(`${API_BASE}/risk/investigations/health`);
  expect(inv.status(), 'investigations health status').toBe(200);
  const invBody = await inv.json();
  expect(
    invBody.feature_flag_enabled === true || invBody.enabled === true,
    `Phase 9 expected enabled flag === true; got body=${JSON.stringify(invBody)}`,
  ).toBeTruthy();

  const gnn = await ctx.get(`${API_BASE}/risk/gnn/health`);
  expect(gnn.status(), 'gnn health status').toBe(200);
  const gnnBody = await gnn.json();
  expect(
    gnnBody.enabled === true || gnnBody.feature_flag_enabled === true,
    `Phase 10 expected enabled flag === true; got body=${JSON.stringify(gnnBody)}`,
  ).toBeTruthy();

  const dnn = await ctx.get(`${API_BASE}/risk/dnn/health`);
  expect(dnn.status(), 'dnn health status').toBe(200);
  const dnnBody = await dnn.json();
  expect(dnnBody.enabled, `Phase 11 enabled; got ${JSON.stringify(dnnBody)}`).toBe(true);

  const orch = await ctx.get(`${API_BASE}/risk/orchestrator/health`);
  expect(orch.status(), 'orchestrator health status').toBe(200);
  const orchBody = await orch.json();
  expect(
    orchBody.enabled,
    `Phase 12 enabled; got ${JSON.stringify(orchBody)}`,
  ).toBe(true);

  await ctx.dispose();
});

// ── TEST 2 — Phase 9 investigation trigger via API ─────────────────────────
test('Phase 9 investigation trigger returns a valid decision', async () => {
  const ctx = await pwRequest.newContext({ extraHTTPHeaders: adminHeaders });

  const queueRes = await ctx.get(
    `${API_BASE}/risk/review-queue?status=pending&limit=1`,
  );
  if (queueRes.status() !== 200) {
    test.skip(true, `review-queue returned ${queueRes.status()}; cannot derive a txn id`);
  }
  const queueBody = await queueRes.json();
  const items = queueBody?.items ?? (Array.isArray(queueBody) ? queueBody : []);
  if (!items.length) {
    test.skip(true, 'review queue is empty — nothing to investigate');
  }
  const txnId =
    items[0].transaction_id ??
    items[0].txn_id ??
    items[0].id ??
    null;
  if (!txnId) {
    test.skip(true, `review queue first item has no transaction_id: ${JSON.stringify(items[0])}`);
  }

  const runRes = await ctx.post(
    `${API_BASE}/risk/investigations/${txnId}/run?triggered_by=e2e_test`,
    { timeout: 90_000 },
  );
  expect(runRes.status(), `investigation/run for ${txnId}`).toBe(200);

  const decision = await runRes.json();
  const action = String(
    decision.recommended_action ?? decision.action ?? '',
  ).toUpperCase();
  expect(['ALLOW', 'FLAG', 'BLOCK', 'INVESTIGATE']).toContain(action);

  const cost = Number(decision.cost_usd ?? decision.cost ?? -1);
  expect(Number.isFinite(cost) && cost >= 0).toBeTruthy();

  const reasoning = String(
    decision.reasoning ?? decision.agent_reasoning ?? decision.narrative ?? '',
  );
  expect(reasoning.length, 'reasoning text length').toBeGreaterThan(0);

  await ctx.dispose();
});

// ── TEST 3 — Phase 12 route preview at scores 0, 50, 100 ───────────────────
test('Phase 12 orchestrator route preview returns a tier across the range', async () => {
  const ctx = await pwRequest.newContext({ extraHTTPHeaders: adminHeaders });

  const fetchPreview = async (score: number) => {
    const r = await ctx.get(
      `${API_BASE}/risk/orchestrator/route/preview?risk_score=${score}`,
    );
    expect(r.status(), `route/preview score=${score}`).toBe(200);
    const body = await r.json();
    expect(body.tier, `tier for score=${score}: ${JSON.stringify(body)}`).toBeTruthy();
    return body;
  };

  const lo = await fetchPreview(0);
  expect(String(lo.tier).toLowerCase()).toContain('tier_0');

  const mid = await fetchPreview(50);
  expect(String(mid.tier ?? '').length).toBeGreaterThan(0);

  const hi = await fetchPreview(100);
  expect(String(hi.tier).toLowerCase()).toContain('tier_4');

  // tier_label is the new field added by routing_policy.py — non-empty
  // string confirms the fix shipped.
  for (const body of [lo, mid, hi]) {
    expect(typeof body.tier_label === 'string' && body.tier_label.length > 0).toBeTruthy();
  }

  await ctx.dispose();
});

// ── TEST 4 — Phase 12 costs/today endpoint shape ───────────────────────────
test('Phase 12 costs/today returns a valid spend payload', async () => {
  const ctx = await pwRequest.newContext({ extraHTTPHeaders: adminHeaders });

  const r = await ctx.get(`${API_BASE}/risk/orchestrator/costs/today`);
  expect(r.status(), 'costs/today status').toBe(200);
  const body = await r.json();

  expect(typeof body.total_cost_usd).toBe('number');
  expect(typeof body.daily_cap_usd).toBe('number');
  expect(body.daily_cap_usd).toBeGreaterThan(0);
  expect(typeof body.remaining_usd).toBe('number');
  expect(Array.isArray(body.by_model)).toBe(true);
  expect(typeof body.phase_9_investigations).toBe('number');
  expect(body.phase_9_investigations).toBeGreaterThanOrEqual(0);
  expect(typeof body.phase_12_judge_calls).toBe('number');
  expect(body.phase_12_judge_calls).toBeGreaterThanOrEqual(0);

  await ctx.dispose();
});

// ── TEST 5 — Browser smoke test for Investigations UI ──────────────────────
test('UI: Investigations page loads and shows the queue', async ({ page }) => {
  await page.goto('http://localhost:3001');

  // Sign in if landed on the auth page.
  const emailField = page
    .locator('input[type="email"], input[name="email"]')
    .first();
  if (await emailField.isVisible({ timeout: 3_000 }).catch(() => false)) {
    await emailField.fill(TEST_EMAIL);
    await page
      .locator('input[type="password"], input[name="password"]')
      .first()
      .fill(TEST_PASSWORD);
    const submit = page
      .locator('button[type="submit"], button:has-text("Sign in"), button:has-text("Sign In"), button:has-text("Login")')
      .first();
    await submit.click().catch(() => {});
  }

  // Wait until we're off the auth page.
  try {
    await page.waitForURL((url) => !url.toString().includes('/auth'), {
      timeout: 10_000,
    });
  } catch {
    test.skip(true, 'Could not get past /auth — login probably failed');
  }

  // Open Investigations from the sidebar.
  const navLink = page
    .locator('a:has-text("Investigations"), button:has-text("Investigations")')
    .first();
  await navLink.click({ timeout: 5_000 }).catch(() => {});

  // Wait for the queue to render.
  const queue = page.locator('[data-testid="investigation-queue"]').first();
  const seen =
    (await queue.isVisible({ timeout: 10_000 }).catch(() => false)) ||
    (await page
      .getByText(/In review queue|Phase 9/i)
      .first()
      .isVisible({ timeout: 5_000 })
      .catch(() => false));
  expect(seen, 'Phase 9 investigations UI never rendered').toBeTruthy();

  await expect(page.getByText(/Phase 9/i).first()).toBeVisible();

  const runBtn = page
    .getByRole('button', { name: /Run Investigation|Re-run Investigation/i })
    .first();
  expect(await runBtn.count()).toBeGreaterThan(0);
});
