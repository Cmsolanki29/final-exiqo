/** Client-side EMI math (mirrors backend/services/emi_calculator.py) for live preview. */

export function calculateEmi(principal, annualRatePct, tenureMonths) {
  const p = Math.max(0, Number(principal) || 0);
  const n = Math.max(1, Math.floor(Number(tenureMonths) || 1));
  if (p <= 0) return 0;
  const rate = Number(annualRatePct) || 0;
  if (rate <= 0) return Math.round((p / n) * 100) / 100;
  const r = rate / 12 / 100;
  const factor = (1 + r) ** n;
  return Math.round(((p * r * factor) / (factor - 1)) * 100) / 100;
}

export function buildLoanSummary(productPrice, downPayment, annualRatePct, tenureMonths) {
  const price = Math.max(0, Number(productPrice) || 0);
  const down = Math.max(0, Math.min(Number(downPayment) || 0, price));
  const principal = Math.round((price - down) * 100) / 100;
  const emi = calculateEmi(principal, annualRatePct, tenureMonths);
  const n = Math.max(1, Math.floor(Number(tenureMonths) || 1));
  const r = (Number(annualRatePct) || 0) / 12 / 100;
  let balance = principal;
  let totalInterest = 0;
  const schedule = [];
  for (let month = 1; month <= n; month += 1) {
    const interest = r > 0 ? Math.round(balance * r * 100) / 100 : 0;
    const principalPart =
      month === n ? Math.round(balance * 100) / 100 : Math.round((emi - interest) * 100) / 100;
    const emiRow = month === n ? Math.round((principalPart + interest) * 100) / 100 : emi;
    balance = Math.round(Math.max(0, balance - principalPart) * 100) / 100;
    totalInterest += interest;
    schedule.push({ month, emi: emiRow, principal: principalPart, interest, balance });
  }
  const totalPayable = Math.round(schedule.reduce((s, row) => s + row.emi, 0) * 100) / 100;
  return {
    product_price: price,
    down_payment: down,
    principal,
    annual_interest_rate_pct: Number(annualRatePct) || 0,
    tenure_months: n,
    emi_monthly: emi,
    total_amount_payable: totalPayable,
    total_interest: Math.round((totalPayable - principal) * 100) / 100,
    amortization_schedule: schedule,
  };
}
