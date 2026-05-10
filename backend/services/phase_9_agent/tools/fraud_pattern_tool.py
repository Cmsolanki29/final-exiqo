"""FraudPatternTool — match a transaction against a curated list of known
Indian-context fraud patterns (KYC update scam, OTP phishing, lottery fraud,
fake refund scam, etc.).

This is intentionally a *static* dictionary, not a vector search.  It's
deterministic, auditable, and adds zero latency.  When we have richer
fraud-typology data we'll back this with a vector index.
"""

from __future__ import annotations

from typing import Any

from services.phase_9_agent.tools.base_tool import BaseTool, ToolOutput


# ---------------------------------------------------------------------- #
# Curated patterns.  Keep keywords lower-case; matching is case-insensitive.
# ---------------------------------------------------------------------- #
_PATTERNS: list[dict[str, Any]] = [
    {
        "id": "kyc_update_scam",
        "name": "Fake KYC Update Scam",
        "description": (
            "Caller pretends to be from the bank / RBI and asks the user to "
            "transfer money to 'update KYC'.  Hallmark: small-amount UPI "
            "transfer to an unknown personal merchant or VPA."
        ),
        "keywords": ["kyc", "kyc update", "kyc verification", "kyc pending"],
        "amount_band": (100, 10000),
        "category_hints": ["transfer", "upi"],
    },
    {
        "id": "otp_phishing",
        "name": "OTP Phishing",
        "description": (
            "Fraudster collects OTP via fake call/SMS and drains the account. "
            "Hallmark: sudden high-value withdrawal/transfer right after a "
            "short 'verification' interaction."
        ),
        "keywords": ["otp", "verify", "verification", "code"],
        "amount_band": (5000, 500000),
        "category_hints": ["transfer", "withdrawal"],
    },
    {
        "id": "lottery_prize_scam",
        "name": "Lottery / Prize Scam",
        "description": (
            "User is told they won a prize (KBC, lucky draw, lottery) and "
            "must pay 'processing fee' to claim it."
        ),
        "keywords": ["lottery", "prize", "winner", "kbc", "lucky draw", "reward"],
        "amount_band": (500, 50000),
        "category_hints": ["transfer", "upi", "payment"],
    },
    {
        "id": "fake_refund_scam",
        "name": "Fake Refund / Customer Care Scam",
        "description": (
            "User is contacted by 'customer care' offering a refund, then "
            "tricked into installing screen-share apps and approving a "
            "reverse transfer."
        ),
        "keywords": ["refund", "customer care", "support", "anydesk", "teamviewer"],
        "amount_band": (1000, 200000),
        "category_hints": ["transfer", "withdrawal"],
    },
    {
        "id": "loan_app_extortion",
        "name": "Loan App Extortion",
        "description": (
            "Predatory loan-app spam.  Sudden small deposit followed by "
            "harassment and high-interest repayment demands."
        ),
        "keywords": ["loan", "instant loan", "personal loan", "emi"],
        "amount_band": (1000, 50000),
        "category_hints": ["loan", "transfer"],
    },
    {
        "id": "fuel_pump_overcharge",
        "name": "Fuel Pump Overcharge",
        "description": (
            "Card-skimming / overcharge at fuel stations.  Hallmark: "
            "round-number large amount at a petrol pump merchant."
        ),
        "keywords": ["fuel", "petrol", "diesel", "pump", "iocl", "hpcl", "bpcl"],
        "amount_band": (3000, 50000),
        "category_hints": ["fuel", "transport"],
    },
    {
        "id": "investment_scam",
        "name": "Investment / Crypto Scam",
        "description": (
            "Fake investment platform promising guaranteed high returns. "
            "Hallmark: large transfer to an unknown trading or crypto VPA."
        ),
        "keywords": ["invest", "crypto", "bitcoin", "trading", "stock tip"],
        "amount_band": (5000, 1000000),
        "category_hints": ["transfer", "investment"],
    },
]


class FraudPatternTool(BaseTool):
    name = "check_fraud_patterns"
    description = (
        "Match the flagged transaction against known fraud patterns "
        "(KYC scam, OTP phishing, lottery scam, fake refund, loan app, "
        "investment scam, fuel pump overcharge).  Returns matched patterns "
        "with reasoning.  Empty list = no known pattern matched."
    )

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "merchant": {"type": "string"},
                "category": {"type": "string"},
                "description": {"type": "string"},
                "amount": {"type": "number"},
            },
            "required": ["amount"],
        }

    async def execute(self, input_data: dict[str, Any]) -> ToolOutput:
        try:
            amount = float(input_data.get("amount") or 0)
        except (TypeError, ValueError):
            amount = 0.0

        haystack_parts = [
            str(input_data.get("merchant") or ""),
            str(input_data.get("category") or ""),
            str(input_data.get("description") or ""),
        ]
        haystack = " ".join(haystack_parts).lower()

        matches: list[dict[str, Any]] = []
        for pat in _PATTERNS:
            keyword_hit = any(k in haystack for k in pat["keywords"])
            amount_lo, amount_hi = pat["amount_band"]
            amount_in_band = amount_lo <= amount <= amount_hi
            category_hit = any(
                hint in haystack for hint in pat["category_hints"]
            )
            score = 0
            evidence = []
            if keyword_hit:
                score += 60
                evidence.append("keyword_match")
            if amount_in_band:
                score += 25
                evidence.append("amount_in_typical_band")
            if category_hit:
                score += 15
                evidence.append("category_or_payment_match")
            if score >= 60:
                matches.append({
                    "id": pat["id"],
                    "name": pat["name"],
                    "match_score": score,
                    "description": pat["description"],
                    "evidence": evidence,
                })

        matches.sort(key=lambda m: m["match_score"], reverse=True)
        return ToolOutput(
            success=True,
            data={
                "matches": matches,
                "match_count": len(matches),
                "checked_patterns": len(_PATTERNS),
            },
        )
