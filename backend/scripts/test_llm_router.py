"""Quick LLM router smoke tests. Run: cd backend && python -m scripts.test_llm_router"""
from __future__ import annotations

import json
import sys
import time

from services.llm_router import LLMRouter, get_llm_router


def main() -> int:
    print("=== Test 1: Provider init ===")
    router = get_llm_router(required=True)
    print("Providers:", list(router.providers.keys()))

    print("\n=== Test 2: Groq bulk extraction ===")
    start = time.time()
    txns = router.extract_transactions_bulk(
        "16-Apr-2026 AMAZON PAY INDIA 1285.00\n17-Apr-2026 SWIGGY MUMBAI 586.00\n18-Apr-2026 HPCL PETROL PUMP 1700.00",
        {"institution_name": "Axis Bank"},
        0,
        1,
    )
    print(f"Extracted {len(txns)} in {time.time() - start:.1f}s")
    print(json.dumps(txns, indent=2))

    print("\n=== Test 3: Document understanding (OpenAI primary) ===")
    doc = router.understand_document(
        "AXIS BANK CREDIT CARD STATEMENT\nCardholder: Vikram Singh\n"
        "Billing Period: 16 Apr 2026 - 15 May 2026\nTotal Amount Due: INR 20,173.00"
    )
    print(json.dumps(doc, indent=2))

    print("\n=== Test 4: Categorization ===")
    sample = [
        {"description": "SWIGGY MUMBAI", "amount": 586, "type": "debit", "date": "2026-04-17"},
        {"description": "NETFLIX INDIA", "amount": 649, "type": "debit", "date": "2026-04-18"},
        {"description": "HPCL PETROL PUMP", "amount": 1700, "type": "debit", "date": "2026-04-19"},
        {"description": "EMI AUTO DEBIT CAR LOAN", "amount": 16842, "type": "debit", "date": "2026-04-20"},
    ]
    cat = router.categorize_transactions(sample)
    for t in cat:
        print(f"  {t['description']}: {t.get('category')}")

    print("\n=== Test 5: Fallback (Groq disabled) ===")
    router.providers.pop("groq", None)
    fb = router.extract_transactions_bulk("01-May-2026 TEST MERCHANT 100.00", {"institution_name": "Test"}, 0, 1)
    print(f"Fallback extracted {len(fb)} txn(s)")
    print("\nUsage log:", router.usage_summary())
    return 0


if __name__ == "__main__":
    sys.exit(main())
