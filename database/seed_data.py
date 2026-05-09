import calendar
import importlib.util
import random
import sys
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

import psycopg2
from faker import Faker
from psycopg2.extras import Json, execute_values
from dotenv import load_dotenv


def _load_db_module():
    """Load sibling `db.py` without requiring the repo root on PYTHONPATH."""
    db_path = Path(__file__).resolve().parent / "db.py"
    spec = importlib.util.spec_from_file_location("_smartspend_db", db_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load database helper from {db_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(spec.name, module)
    spec.loader.exec_module(module)
    return module


_db = _load_db_module()
DatabaseConfig = _db.DatabaseConfig
get_db_connection = _db.get_db_connection

random.seed(42)
fake = Faker("en_IN")
Faker.seed(42)


CATEGORIES = {
    "Food & Dining": {
        "merchants": [
            "Swiggy",
            "Zomato",
            "Blinkit",
            "BigBasket",
            "DMart",
            "Zepto",
            "Instamart",
            "McDonald's India",
            "Domino's Pizza",
            "Starbucks India",
            "Cafe Coffee Day",
            "Haldiram's",
            "MTR Foods",
        ],
        "subcategories": ["Food Delivery", "Grocery", "Restaurant", "Coffee"],
        "debit_only": True,
        "amount_range": (80, 2500),
        "frequency_per_month": (8, 25),
    },
    "Transportation": {
        "merchants": [
            "Uber India",
            "Ola Cabs",
            "Rapido",
            "BMTC",
            "Metro Rail",
            "Indian Railways",
            "IndiGo Airlines",
            "Air India",
            "MakeMyTrip",
            "Redbus",
            "Namma Metro",
        ],
        "subcategories": ["Cab", "Metro", "Flight", "Bus"],
        "debit_only": True,
        "amount_range": (50, 18000),
        "frequency_per_month": (5, 20),
    },
    "Shopping": {
        "merchants": [
            "Amazon India",
            "Flipkart",
            "Myntra",
            "Ajio",
            "Nykaa",
            "Meesho",
            "Croma",
            "Reliance Digital",
            "H&M India",
            "Zara India",
            "Nike India",
            "Adidas India",
        ],
        "subcategories": ["Electronics", "Clothing", "Beauty", "Home"],
        "debit_only": True,
        "amount_range": (199, 45000),
        "frequency_per_month": (2, 10),
    },
    "Bills & Utilities": {
        "merchants": [
            "BESCOM",
            "MSEDCL",
            "Tata Power",
            "Jio",
            "Airtel",
            "Vi",
            "BSNL",
            "MahaGas",
            "Indraprastha Gas",
            "Tata Sky",
            "Dish TV",
            "Hathway",
        ],
        "subcategories": ["Electricity", "Mobile", "Internet", "Gas", "DTH"],
        "debit_only": True,
        "amount_range": (200, 4500),
        "frequency_per_month": (3, 8),
    },
    "Entertainment": {
        "merchants": [
            "Netflix India",
            "Prime Video",
            "Hotstar",
            "Spotify India",
            "BookMyShow",
            "PVR Cinemas",
            "INOX Movies",
            "Steam India",
            "PlayStation India",
            "Sony LIV",
        ],
        "subcategories": ["OTT", "Movies", "Gaming", "Events"],
        "debit_only": True,
        "amount_range": (99, 3500),
        "frequency_per_month": (2, 6),
    },
    "Healthcare": {
        "merchants": [
            "Apollo Pharmacy",
            "Medplus",
            "Netmeds",
            "1mg",
            "Practo",
            "Apollo Hospitals",
            "Fortis Healthcare",
            "Manipal Hospitals",
            "Dr. Lal PathLabs",
        ],
        "subcategories": ["Medicine", "Doctor", "Lab Test", "Insurance"],
        "debit_only": True,
        "amount_range": (150, 12000),
        "frequency_per_month": (1, 4),
    },
    "Education": {
        "merchants": [
            "Udemy India",
            "Coursera",
            "upGrad",
            "BYJU's",
            "Unacademy",
            "Scaler Academy",
            "GeeksforGeeks",
            "LeetCode",
        ],
        "subcategories": ["Online Course", "Subscription", "Books"],
        "debit_only": True,
        "amount_range": (299, 25000),
        "frequency_per_month": (0, 3),
    },
    "Finance & Investment": {
        "merchants": [
            "Zerodha",
            "Groww",
            "Upstox",
            "Paytm Money",
            "SBI Mutual Fund",
            "HDFC Mutual Fund",
            "LIC India",
            "PolicyBazaar",
            "CRED",
            "BankBazaar",
        ],
        "subcategories": ["Mutual Fund", "SIP", "Insurance Premium", "Loan EMI"],
        "debit_only": True,
        "amount_range": (500, 50000),
        "frequency_per_month": (1, 5),
    },
    "Salary": {
        "merchants": ["NEFT-SALARY", "IMPS-SALARY", "Employer Transfer"],
        "subcategories": ["Monthly Salary"],
        "debit_only": False,
        "credit_only": True,
        "amount_range": (0, 0),
        "frequency_per_month": (1, 1),
    },
    "Transfer": {
        "merchants": ["PhonePe", "Google Pay", "Paytm", "BHIM UPI", "NEFT Transfer", "IMPS Transfer"],
        "subcategories": ["UPI Transfer", "Bank Transfer"],
        "debit_only": False,
        "amount_range": (500, 50000),
        "frequency_per_month": (2, 8),
    },
}

PAYMENT_METHODS = ["UPI", "UPI", "UPI", "Debit Card", "Credit Card", "NEFT", "IMPS", "Net Banking"]

# In-store / QSR chains: card or UPI only (never bank rails like NEFT/IMPS/Net Banking).
FAST_FOOD_RESTAURANT_MERCHANTS = frozenset(
    {"McDonald's India", "Domino's Pizza", "Cafe Coffee Day"}
)

CITIES = {
    "priya@demo.com": "Pune",
    "arjun@demo.com": "Bangalore",
    "kavya@demo.com": "Hyderabad",
}

FOREIGN_MERCHANTS = ["Amazon.com US", "Apple Store USD", "Netflix US", "PayPal USD"]


USERS = [
    {
        "name": "Priya Sharma",
        "email": "priya@demo.com",
        "monthly_income": 52000,
        "savings_goal": 10000,
        "risk_tolerance": "LOW",
        "start_balance": 50000,
    },
    {
        "name": "Arjun Mehta",
        "email": "arjun@demo.com",
        "monthly_income": 125000,
        "savings_goal": 35000,
        "risk_tolerance": "MEDIUM",
        "start_balance": 150000,
    },
    {
        "name": "Kavya Reddy",
        "email": "kavya@demo.com",
        "monthly_income": 280000,
        "savings_goal": 80000,
        "risk_tolerance": "HIGH",
        "start_balance": 350000,
    },
]


USER_SPENDING_PROFILE = {
    "priya@demo.com": {"count_mult": 0.9, "single_txn_ratio_cap": 0.45, "expense_ratio": (0.80, 0.88)},
    "arjun@demo.com": {"count_mult": 1.0, "single_txn_ratio_cap": 0.65, "expense_ratio": (0.76, 0.84)},
    "kavya@demo.com": {"count_mult": 1.15, "single_txn_ratio_cap": 0.95, "expense_ratio": (0.72, 0.80)},
}

MONTHS = []
start_cursor = date(2025, 1, 1)
while start_cursor <= date(2026, 5, 1):
    MONTHS.append((start_cursor.year, start_cursor.month))
    if start_cursor.month == 12:
        start_cursor = date(start_cursor.year + 1, 1, 1)
    else:
        start_cursor = date(start_cursor.year, start_cursor.month + 1, 1)


@dataclass
class SeedStats:
    users_created: int = 0
    total_transactions: int = 0
    anomalies: dict[str, int] = None
    categories: set[str] = None

    def __post_init__(self) -> None:
        self.anomalies = defaultdict(int)
        self.categories = set()


def pick_day(year: int, month: int, low: int = 1, high: int | None = None) -> int:
    max_day = calendar.monthrange(year, month)[1]
    upper = min(max_day, high or max_day)
    return random.randint(low, upper)


def make_dt(year: int, month: int, day_low: int = 1, day_high: int | None = None, hour_low: int = 7, hour_high: int = 22) -> datetime:
    day = pick_day(year, month, day_low, day_high)
    hour = random.randint(hour_low, hour_high)
    minute = random.randint(0, 59)
    return datetime(year, month, day, hour, minute)


def split_amounts(total: float, count: int, min_amt: float, max_amt: float) -> list[float]:
    if count <= 0:
        return []
    if count == 1:
        return [round(max(min_amt, min(max_amt, total)), 2)]
    weights = [random.uniform(0.3, 1.7) for _ in range(count)]
    denom = sum(weights)
    values = [total * (w / denom) for w in weights]
    clipped = [max(min_amt, min(max_amt, v)) for v in values]
    clipped_total = sum(clipped)
    if clipped_total > 0:
        scale = total / clipped_total
        clipped = [max(min_amt, min(max_amt, v * scale)) for v in clipped]
    return [round(v, 2) for v in clipped]


def payment_method_for(category: str, merchant: str) -> str:
    if merchant in FAST_FOOD_RESTAURANT_MERCHANTS:
        return random.choice(["UPI", "Debit Card", "Credit Card"])
    if category in {"Salary", "Finance & Investment"}:
        return random.choice(["NEFT", "IMPS", "Net Banking"])
    if category == "Shopping":
        return random.choice(["UPI", "Debit Card", "Credit Card"])
    return random.choice(PAYMENT_METHODS)


def create_transaction(
    user_id: int,
    tx_dt: datetime,
    amount: float,
    tx_type: str,
    category: str,
    subcategory: str,
    merchant: str,
    location: str,
    description: str,
    anomaly_flag: bool = False,
    risk_score: int = 0,
    risk_level: str = "LOW",
    anomaly_reason: str | None = None,
) -> dict[str, Any]:
    tx_time = tx_dt.time().replace(second=0, microsecond=0)
    hour = tx_time.hour
    return {
        "user_id": user_id,
        "transaction_date": tx_dt.date(),
        "transaction_time": tx_time,
        "amount": round(amount, 2),
        "type": tx_type,
        "description": description,
        "merchant": merchant,
        "category": category,
        "subcategory": subcategory,
        "payment_method": payment_method_for(category, merchant),
        "location": location,
        "reference_number": f"TXN{fake.numerify('##########')}",
        "anomaly_flag": anomaly_flag,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "anomaly_reason": anomaly_reason,
        "ml_processed": anomaly_flag,
        "hour_of_day": hour,
        "day_of_week": tx_dt.weekday(),
        "is_weekend": tx_dt.weekday() >= 5,
        "is_night_txn": hour >= 23 or hour <= 5,
    }


def generate_user_transactions(user: dict[str, Any], user_id: int) -> tuple[list[dict[str, Any]], dict[str, int], str]:
    profile = USER_SPENDING_PROFILE[user["email"]]
    city = CITIES[user["email"]]
    income = float(user["monthly_income"])
    missing_salary_month = random.choice(MONTHS)
    anomaly_counter: dict[str, int] = defaultdict(int)
    transactions: list[dict[str, Any]] = []

    category_weights = {
        "Food & Dining": 0.24,
        "Transportation": 0.09,
        "Shopping": 0.15,
        "Bills & Utilities": 0.11,
        "Entertainment": 0.08,
        "Healthcare": 0.07,
        "Education": 0.05,
        "Finance & Investment": 0.14,
        "Transfer": 0.07,
    }

    for year, month in MONTHS:
        month_income = round(income * random.uniform(0.98, 1.05), 2)
        salary_missing = (year, month) == missing_salary_month
        if not salary_missing:
            salary_dt = make_dt(year, month, day_low=1, day_high=5, hour_low=10, hour_high=14)
            transactions.append(
                create_transaction(
                    user_id=user_id,
                    tx_dt=salary_dt,
                    amount=month_income,
                    tx_type="CREDIT",
                    category="Salary",
                    subcategory="Monthly Salary",
                    merchant=random.choice(CATEGORIES["Salary"]["merchants"]),
                    location=city,
                    description=f"Monthly salary credit for {calendar.month_name[month]} {year}",
                )
            )

        monthly_expense_target = income * random.uniform(*profile["expense_ratio"])
        rent_amount = round(income * random.uniform(0.27, 0.33), 2)
        monthly_expense_target = max(monthly_expense_target, rent_amount + income * 0.35)
        remaining_budget = max(1000.0, monthly_expense_target - rent_amount)

        rent_tx_dt = make_dt(year, month, day_low=1, day_high=7, hour_low=9, hour_high=20)
        transactions.append(
            create_transaction(
                user_id=user_id,
                tx_dt=rent_tx_dt,
                amount=rent_amount,
                tx_type="DEBIT",
                category="Transfer",
                subcategory="Bank Transfer",
                merchant="House Rent Transfer",
                location=city,
                description="Monthly house rent",
            )
        )

        weight_sum = sum(category_weights.values())
        for category, weight in category_weights.items():
            config = CATEGORIES[category]
            budget = (weight / weight_sum) * remaining_budget
            low_freq, high_freq = config["frequency_per_month"]
            avg_amt = (config["amount_range"][0] + config["amount_range"][1]) / 2
            estimated_count = int(max(low_freq, min(high_freq, round((budget / max(1.0, avg_amt)) * 2.2))))
            count = int(max(low_freq, min(high_freq, round(estimated_count * profile["count_mult"]))))
            min_amt, cat_max = config["amount_range"]
            max_amt = min(cat_max, income * profile["single_txn_ratio_cap"])
            if category == "Transfer":
                max_amt = min(max_amt, income * 0.35)
            amount_splits = split_amounts(budget, count, min_amt, max_amt)

            for amount in amount_splits:
                if category == "Food & Dining":
                    tx_dt = make_dt(year, month, day_low=1, hour_low=8, hour_high=23)
                elif category == "Transportation":
                    tx_dt = make_dt(year, month, day_low=1, hour_low=6, hour_high=22)
                elif category == "Bills & Utilities":
                    tx_dt = make_dt(year, month, day_low=1, day_high=12, hour_low=8, hour_high=20)
                else:
                    tx_dt = make_dt(year, month, day_low=1, hour_low=9, hour_high=22)

                merchant = random.choice(config["merchants"])
                subcategory = random.choice(config["subcategories"])
                transactions.append(
                    create_transaction(
                        user_id=user_id,
                        tx_dt=tx_dt,
                        amount=amount,
                        tx_type="DEBIT",
                        category=category,
                        subcategory=subcategory,
                        merchant=merchant,
                        location=city,
                        description=f"{subcategory} payment at {merchant}",
                    )
                )

    # Inject anomalies: DUPLICATE_CHARGE (3/user)
    base_candidates = [t for t in transactions if t["type"] == "DEBIT" and not t["anomaly_flag"] and t["merchant"] != "House Rent Transfer"]
    for _ in range(3):
        source = random.choice(base_candidates)
        src_dt = datetime.combine(source["transaction_date"], source["transaction_time"])
        dup_dt = src_dt + timedelta(minutes=random.randint(1, 2))
        transactions.append(
            create_transaction(
                user_id=user_id,
                tx_dt=dup_dt,
                amount=float(source["amount"]),
                tx_type="DEBIT",
                category=source["category"],
                subcategory=source["subcategory"],
                merchant=source["merchant"],
                location=city,
                description=f"Possible duplicate charge at {source['merchant']}",
                anomaly_flag=True,
                risk_score=88,
                risk_level="HIGH",
                anomaly_reason="DUPLICATE_CHARGE: Same merchant and amount within 2 minutes",
            )
        )
        anomaly_counter["DUPLICATE_CHARGE"] += 1

    # Inject anomalies: UNUSUAL_AMOUNT (4/user)
    category_avgs = defaultdict(list)
    for tx in transactions:
        if tx["type"] == "DEBIT":
            category_avgs[tx["category"]].append(float(tx["amount"]))
    unusual_categories = ["Food & Dining", "Shopping", "Finance & Investment", "Transfer"]
    for category in unusual_categories:
        avg = sum(category_avgs[category]) / max(1, len(category_avgs[category]))
        base_amount = max(avg * 5, income * random.uniform(0.35, 0.60))
        if user["email"] == "priya@demo.com" and category == "Food & Dining":
            base_amount = 47000.0
        amount = round(min(base_amount, income * 1.4), 2)
        config = CATEGORIES[category]
        tx_dt = make_dt(*random.choice(MONTHS), day_low=1, day_high=26, hour_low=11, hour_high=22)
        transactions.append(
            create_transaction(
                user_id=user_id,
                tx_dt=tx_dt,
                amount=amount,
                tx_type="DEBIT",
                category=category,
                subcategory=random.choice(config["subcategories"]),
                merchant=random.choice(config["merchants"]),
                location=city,
                description=f"Unusually large {category.lower()} transaction",
                anomaly_flag=True,
                risk_score=95,
                risk_level="CRITICAL",
                anomaly_reason="UNUSUAL_AMOUNT: Amount is 5x typical spend for this category",
            )
        )
        anomaly_counter["UNUSUAL_AMOUNT"] += 1

    # Inject anomalies: ODD_HOUR (5/user)
    odd_hour_categories = ["Food & Dining", "Transfer", "Entertainment", "Shopping"]
    for _ in range(5):
        category = random.choice(odd_hour_categories)
        config = CATEGORIES[category]
        year, month = random.choice(MONTHS)
        day = pick_day(year, month, 1, 28)
        odd_dt = datetime(year, month, day, random.choice([2, 3]), random.randint(0, 59))
        min_amt, max_amt = config["amount_range"]
        amount = round(random.uniform(min_amt * 2, min(max_amt, income * 0.25)), 2)
        transactions.append(
            create_transaction(
                user_id=user_id,
                tx_dt=odd_dt,
                amount=amount,
                tx_type="DEBIT",
                category=category,
                subcategory=random.choice(config["subcategories"]),
                merchant=random.choice(config["merchants"]),
                location=city,
                description="Odd hour transaction detected",
                anomaly_flag=True,
                risk_score=74,
                risk_level="MEDIUM",
                anomaly_reason="ODD_HOUR: Transaction between 2:30 AM and 4:00 AM",
            )
        )
        anomaly_counter["ODD_HOUR"] += 1

    # Inject anomalies: FOREIGN_MERCHANT (3/user)
    for _ in range(3):
        year, month = random.choice(MONTHS)
        foreign_dt = make_dt(year, month, day_low=1, day_high=27, hour_low=0, hour_high=23)
        amount = round(random.uniform(income * 0.03, income * 0.18), 2)
        merchant = random.choice(FOREIGN_MERCHANTS)
        transactions.append(
            create_transaction(
                user_id=user_id,
                tx_dt=foreign_dt,
                amount=amount,
                tx_type="DEBIT",
                category="Shopping",
                subcategory="Electronics",
                merchant=merchant,
                location="International",
                description=f"Cross-border card charge by {merchant}",
                anomaly_flag=True,
                risk_score=82,
                risk_level="HIGH",
                anomaly_reason="FOREIGN_MERCHANT: International merchant charge in USD",
            )
        )
        anomaly_counter["FOREIGN_MERCHANT"] += 1

    # Inject anomalies: RAPID_SUCCESSION (2 bursts/user => 12 txns)
    for _ in range(2):
        year, month = random.choice(MONTHS)
        start_day = pick_day(year, month, 1, 25)
        start_dt = datetime(year, month, start_day, random.randint(10, 21), random.randint(0, 40))
        for idx in range(6):
            tx_dt = start_dt + timedelta(minutes=random.randint(0, 14), seconds=idx)
            category = random.choice(["Food & Dining", "Shopping", "Transfer"])
            config = CATEGORIES[category]
            amount = round(random.uniform(config["amount_range"][0], min(config["amount_range"][1], income * 0.12)), 2)
            is_flagged = idx == 5
            transactions.append(
                create_transaction(
                    user_id=user_id,
                    tx_dt=tx_dt,
                    amount=amount,
                    tx_type="DEBIT",
                    category=category,
                    subcategory=random.choice(config["subcategories"]),
                    merchant=random.choice(config["merchants"]),
                    location=city,
                    description="Rapid succession transaction burst",
                    anomaly_flag=is_flagged,
                    risk_score=78 if is_flagged else 0,
                    risk_level="HIGH" if is_flagged else "LOW",
                    anomaly_reason="RAPID_SUCCESSION: 6 transactions within 15 minutes" if is_flagged else None,
                )
            )
        anomaly_counter["RAPID_SUCCESSION"] += 1

    # Inject anomalies: BALANCE_SPIKE (1/user)
    spike_year, spike_month = random.choice(MONTHS)
    spike_dt = make_dt(spike_year, spike_month, day_low=1, day_high=27, hour_low=9, hour_high=17)
    spike_amount = round(income * random.uniform(1.2, 2.0), 2)
    transactions.append(
        create_transaction(
            user_id=user_id,
            tx_dt=spike_dt,
            amount=spike_amount,
            tx_type="CREDIT",
            category="Transfer",
            subcategory="Bank Transfer",
            merchant="Unknown Source Credit",
            location=city,
            description="Unexpected high-value inbound transfer",
            anomaly_flag=True,
            risk_score=91,
            risk_level="CRITICAL",
            anomaly_reason="BALANCE_SPIKE: Large unexpected credit from unknown source",
        )
    )
    anomaly_counter["BALANCE_SPIKE"] += 1

    target_count = random.randint(470, 530)
    normal_candidates = [t for t in transactions if not t["anomaly_flag"] and t["category"] != "Salary"]
    while len(transactions) < target_count:
        year, month = random.choice(MONTHS)
        category = random.choice(["Food & Dining", "Transportation", "Transfer", "Bills & Utilities"])
        config = CATEGORIES[category]
        tx_dt = make_dt(year, month, day_low=1, day_high=28, hour_low=8, hour_high=22)
        amount = round(random.uniform(config["amount_range"][0], min(config["amount_range"][1], income * 0.15)), 2)
        transactions.append(
            create_transaction(
                user_id=user_id,
                tx_dt=tx_dt,
                amount=amount,
                tx_type="DEBIT",
                category=category,
                subcategory=random.choice(config["subcategories"]),
                merchant=random.choice(config["merchants"]),
                location=city,
                description="Regular spend adjustment transaction",
            )
        )
    while len(transactions) > 550 and normal_candidates:
        to_remove = random.choice(normal_candidates)
        normal_candidates.remove(to_remove)
        transactions.remove(to_remove)

    transactions.sort(key=lambda x: datetime.combine(x["transaction_date"], x["transaction_time"]))
    balance = float(user["start_balance"])
    for tx in transactions:
        if tx["type"] == "CREDIT":
            balance += float(tx["amount"])
        else:
            balance -= float(tx["amount"])
        tx["balance_after"] = round(balance, 2)

    missing_label = f"{calendar.month_name[missing_salary_month[1]]} {missing_salary_month[0]}"
    return transactions, anomaly_counter, missing_label


def insert_monthly_summary(cur: psycopg2.extensions.cursor) -> int:
    cur.execute("DELETE FROM monthly_summary;")
    cur.execute(
        """
        WITH tx_month AS (
            SELECT
                user_id,
                EXTRACT(YEAR FROM transaction_date)::int AS yr,
                EXTRACT(MONTH FROM transaction_date)::int AS mn,
                type,
                amount,
                category,
                anomaly_flag,
                risk_level
            FROM transactions
        ),
        month_agg AS (
            SELECT
                user_id,
                yr,
                mn,
                SUM(CASE WHEN type = 'CREDIT' THEN amount ELSE 0 END)::numeric(12,2) AS total_income,
                SUM(CASE WHEN type = 'DEBIT' THEN amount ELSE 0 END)::numeric(12,2) AS total_expense,
                COUNT(*) FILTER (WHERE anomaly_flag) AS anomaly_count,
                COUNT(*) FILTER (WHERE risk_level IN ('HIGH', 'CRITICAL')) AS high_risk_count
            FROM tx_month
            GROUP BY user_id, yr, mn
        ),
        debits_by_cat AS (
            SELECT user_id, yr, mn, category, SUM(amount) AS cat_total
            FROM tx_month
            WHERE type = 'DEBIT'
            GROUP BY user_id, yr, mn, category
        ),
        top_category AS (
            SELECT user_id, yr, mn, category AS top_category
            FROM (
                SELECT
                    user_id,
                    yr,
                    mn,
                    category,
                    cat_total,
                    ROW_NUMBER() OVER (
                        PARTITION BY user_id, yr, mn
                        ORDER BY cat_total DESC
                    ) AS rn
                FROM debits_by_cat
            ) ranked
            WHERE rn = 1
        ),
        category_breakdown AS (
            SELECT
                user_id,
                yr,
                mn,
                COALESCE(
                    jsonb_object_agg(category, ROUND(cat_total::numeric, 2)),
                    '{}'::jsonb
                ) AS category_breakdown
            FROM debits_by_cat
            GROUP BY user_id, yr, mn
        )
        SELECT
            ma.user_id,
            ma.yr AS year,
            ma.mn AS month,
            ma.total_income,
            ma.total_expense,
            ma.anomaly_count,
            ma.high_risk_count,
            tc.top_category,
            cb.category_breakdown
        FROM month_agg ma
        LEFT JOIN top_category tc
            ON tc.user_id = ma.user_id AND tc.yr = ma.yr AND tc.mn = ma.mn
        LEFT JOIN category_breakdown cb
            ON cb.user_id = ma.user_id AND cb.yr = ma.yr AND cb.mn = ma.mn
        ORDER BY ma.user_id, ma.yr, ma.mn;
        """
    )
    rows = cur.fetchall()
    insert_rows = []
    for row in rows:
        total_income = float(row[3] or 0)
        total_expense = float(row[4] or 0)
        total_saved = round(total_income - total_expense, 2)
        savings_rate = round((total_saved / total_income) * 100, 2) if total_income > 0 else 0.0
        anomaly_count = int(row[5] or 0)
        high_risk_count = int(row[6] or 0)
        health_score = int(max(0, min(100, 88 + (savings_rate * 0.25) - (anomaly_count * 2.2) - (high_risk_count * 2.5))))
        if total_income <= 0:
            health_score = min(health_score, 50)
        insert_rows.append(
            (
                row[0],
                row[2],
                row[1],
                total_income,
                total_expense,
                total_saved,
                savings_rate,
                Json(row[8] or {}),
                health_score,
                anomaly_count,
                high_risk_count,
                row[7],
            )
        )

    execute_values(
        cur,
        """
        INSERT INTO monthly_summary (
            user_id, month, year, total_income, total_expense, total_saved, savings_rate,
            category_breakdown, health_score, anomaly_count, high_risk_count, top_category
        )
        VALUES %s
        ON CONFLICT (user_id, month, year) DO UPDATE SET
            total_income = EXCLUDED.total_income,
            total_expense = EXCLUDED.total_expense,
            total_saved = EXCLUDED.total_saved,
            savings_rate = EXCLUDED.savings_rate,
            category_breakdown = EXCLUDED.category_breakdown,
            health_score = EXCLUDED.health_score,
            anomaly_count = EXCLUDED.anomaly_count,
            high_risk_count = EXCLUDED.high_risk_count,
            top_category = EXCLUDED.top_category,
            computed_at = NOW();
        """,
        insert_rows,
    )
    return len(insert_rows)


def insert_spending_patterns(cur: psycopg2.extensions.cursor) -> int:
    cur.execute("DELETE FROM spending_patterns;")
    cur.execute(
        """
        SELECT
            user_id,
            category,
            ROUND(
                SUM(amount) / GREATEST(COUNT(DISTINCT DATE_TRUNC('month', transaction_date)), 1),
                2
            )::numeric(12,2) AS avg_monthly_spend,
            MAX(amount)::numeric(12,2) AS max_single_txn,
            ARRAY(
                SELECT merchant
                FROM (
                    SELECT merchant, COUNT(*) AS cnt
                    FROM transactions t2
                    WHERE t2.user_id = t.user_id
                      AND t2.category = t.category
                      AND t2.type = 'DEBIT'
                    GROUP BY merchant
                    ORDER BY cnt DESC
                    LIMIT 5
                ) m
            ) AS typical_merchants,
            ARRAY(
                SELECT hour_of_day
                FROM (
                    SELECT hour_of_day, COUNT(*) AS cnt
                    FROM transactions t3
                    WHERE t3.user_id = t.user_id
                      AND t3.category = t.category
                      AND t3.type = 'DEBIT'
                    GROUP BY hour_of_day
                    ORDER BY cnt DESC
                    LIMIT 5
                ) h
            ) AS typical_hours
        FROM transactions t
        WHERE type = 'DEBIT'
        GROUP BY user_id, category
        ORDER BY user_id, category;
        """
    )
    rows = cur.fetchall()
    execute_values(
        cur,
        """
        INSERT INTO spending_patterns (
            user_id, category, avg_monthly_spend, max_single_txn, typical_merchants, typical_hours
        )
        VALUES %s
        ON CONFLICT (user_id, category) DO UPDATE SET
            avg_monthly_spend = EXCLUDED.avg_monthly_spend,
            max_single_txn = EXCLUDED.max_single_txn,
            typical_merchants = EXCLUDED.typical_merchants,
            typical_hours = EXCLUDED.typical_hours,
            last_updated = NOW();
        """,
        rows,
    )
    return len(rows)


def delete_all_seed_rows(cur: psycopg2.extensions.cursor) -> None:
    """Clear seed data without TRUNCATE / DROP — DELETE in FK-safe order, then reset SERIALs."""
    cur.execute("DELETE FROM alerts;")
    cur.execute("DELETE FROM transactions;")
    cur.execute("DELETE FROM monthly_summary;")
    cur.execute("DELETE FROM spending_patterns;")
    cur.execute("DELETE FROM users;")
    for table in ("alerts", "transactions", "monthly_summary", "spending_patterns", "users"):
        cur.execute("SELECT pg_get_serial_sequence(%s, 'id');", (table,))
        seq_name = cur.fetchone()[0]
        if seq_name:
            cur.execute("SELECT setval(%s, 1, false);", (seq_name,))


def insert_overspending_alerts(cur: psycopg2.extensions.cursor) -> int:
    """
    If total DEBITs in a calendar month exceed 150% of the user's declared monthly_income,
    insert one OVERSPENDING alert (HIGH) for that user/month.
    """
    cur.execute(
        """
        SELECT sub.user_id, sub.yr, sub.mn, sub.month_debits, u.monthly_income
        FROM (
            SELECT
                user_id,
                EXTRACT(YEAR FROM transaction_date)::int AS yr,
                EXTRACT(MONTH FROM transaction_date)::int AS mn,
                SUM(amount) AS month_debits
            FROM transactions
            WHERE type = 'DEBIT'
            GROUP BY user_id, yr, mn
        ) AS sub
        JOIN users u ON u.id = sub.user_id
        WHERE sub.month_debits > (u.monthly_income * 1.5);
        """
    )
    rows = cur.fetchall()
    if not rows:
        return 0
    alert_rows = []
    for user_id, yr, mn, month_debits, monthly_income in rows:
        alert_rows.append(
            (
                user_id,
                None,
                "HIGH",
                "OVERSPENDING",
                "Monthly debit spend exceeded 150% of declared income",
                (
                    f"Calendar month {int(yr)}-{int(mn):02d}: total debits ₹{float(month_debits):,.2f} "
                    f"vs monthly income ₹{float(monthly_income):,.2f} (threshold 150% = "
                    f"₹{float(monthly_income) * 1.5:,.2f})."
                ),
            )
        )
    execute_values(
        cur,
        """
        INSERT INTO alerts (user_id, transaction_id, severity, alert_type, message, detail)
        VALUES %s;
        """,
        alert_rows,
    )
    return len(alert_rows)


REQUIRED_TABLES = ("users", "transactions", "alerts", "monthly_summary", "spending_patterns")


def _ensure_schema_exists(cur: psycopg2.extensions.cursor, db_name: str) -> None:
    cur.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = ANY(%s);
        """,
        (list(REQUIRED_TABLES),),
    )
    found = {row[0] for row in cur.fetchall()}
    missing = [t for t in REQUIRED_TABLES if t not in found]
    if missing:
        raise RuntimeError(
            "This database has no SmartSpend tables yet (or you connected to the wrong DB).\n"
            f"  Connected database name: {db_name}\n"
            f"  Missing table(s): {', '.join(missing)}\n\n"
            "Create tables by running schema.sql against the SAME database as in your .env (DB_NAME).\n"
            "From your project folder in PowerShell (change 16 if your PostgreSQL version differs):\n\n"
            r'  & "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres -h localhost -p 5432 -d smartspend_db -f "database\schema.sql"'
            "\n\nThen run: python database\\seed_data.py"
        )


def run_seed() -> None:
    load_dotenv()
    config = DatabaseConfig.from_env()
    stats = SeedStats()

    conn = get_db_connection()
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database();")
            db_name = cur.fetchone()[0]
            _ensure_schema_exists(cur, db_name)

            delete_all_seed_rows(cur)
            print("🧹 Cleared existing seed data (DELETE + SERIAL reset, tables kept)")

            user_ids: dict[str, int] = {}
            for user in USERS:
                cur.execute(
                    """
                    INSERT INTO users (name, email, monthly_income, savings_goal, risk_tolerance)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id;
                    """,
                    (user["name"], user["email"], user["monthly_income"], user["savings_goal"], user["risk_tolerance"]),
                )
                user_id = cur.fetchone()[0]
                user_ids[user["email"]] = user_id
                stats.users_created += 1
                print(f"✅ Created user: {user['name']}")

            all_transactions: list[dict[str, Any]] = []
            for user in USERS:
                txns, anomalies_for_user, missing_month = generate_user_transactions(user, user_ids[user["email"]])
                all_transactions.extend(txns)
                print(f"💸 Generated {len(txns)} transactions for {user['name']} (salary missing in {missing_month})")
                for key, value in anomalies_for_user.items():
                    stats.anomalies[key] += value

            tx_rows = [
                (
                    tx["user_id"],
                    tx["transaction_date"],
                    tx["transaction_time"],
                    tx["amount"],
                    tx["type"],
                    tx["description"],
                    tx["merchant"],
                    tx["category"],
                    tx["subcategory"],
                    tx["payment_method"],
                    tx["location"],
                    tx["balance_after"],
                    tx["reference_number"],
                    tx["anomaly_flag"],
                    tx["risk_score"],
                    tx["risk_level"],
                    tx["anomaly_reason"],
                    tx["ml_processed"],
                    tx["hour_of_day"],
                    tx["day_of_week"],
                    tx["is_weekend"],
                    tx["is_night_txn"],
                )
                for tx in all_transactions
            ]

            inserted = execute_values(
                cur,
                """
                INSERT INTO transactions (
                    user_id, transaction_date, transaction_time, amount, type, description,
                    merchant, category, subcategory, payment_method, location, balance_after,
                    reference_number, anomaly_flag, risk_score, risk_level, anomaly_reason,
                    ml_processed, hour_of_day, day_of_week, is_weekend, is_night_txn
                )
                VALUES %s
                RETURNING id, user_id, anomaly_reason, risk_level, merchant, amount;
                """,
                tx_rows,
                fetch=True,
            )
            stats.total_transactions = len(inserted)
            print(f"📊 Inserted {stats.total_transactions} transactions")

            alerts_rows = []
            for tx_id, user_id, anomaly_reason, risk_level, merchant, amount in inserted:
                if not anomaly_reason:
                    continue
                alert_type = anomaly_reason.split(":", maxsplit=1)[0].strip()
                if alert_type == "BALANCE_SPIKE":
                    severity = "HIGH"
                else:
                    severity = "MEDIUM" if risk_level == "LOW" else risk_level
                alerts_rows.append(
                    (
                        user_id,
                        tx_id,
                        severity,
                        alert_type,
                        f"{alert_type.replace('_', ' ').title()} detected for {merchant}",
                        f"Flagged transaction amount ₹{float(amount):,.2f}",
                    )
                )
            if alerts_rows:
                execute_values(
                    cur,
                    """
                    INSERT INTO alerts (user_id, transaction_id, severity, alert_type, message, detail)
                    VALUES %s;
                    """,
                    alerts_rows,
                )
            print(f"🚨 Created {len(alerts_rows)} alert records from flagged transactions")

            overspend_n = insert_overspending_alerts(cur)
            if overspend_n:
                stats.anomalies["OVERSPENDING"] += overspend_n
                print(f"🚨 Added {overspend_n} OVERSPENDING alert(s) (spending velocity)")

            monthly_rows = insert_monthly_summary(cur)
            print(f"📅 Computed {monthly_rows} monthly_summary rows")
            pattern_rows = insert_spending_patterns(cur)
            print(f"🧠 Computed {pattern_rows} spending_patterns rows")

            stats.categories = {tx["category"] for tx in all_transactions}
            conn.commit()
            print("✅ Seed data committed successfully")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print("\n================= Seed Summary =================")
    print(f"Users Created        : {stats.users_created}")
    print(f"Total Transactions   : {stats.total_transactions}")
    print(f"Categories Covered   : {len(stats.categories)} -> {', '.join(sorted(stats.categories))}")
    print("Anomalies Injected   :")
    for anomaly_type in sorted(stats.anomalies.keys()):
        print(f"  - {anomaly_type:<18} {stats.anomalies[anomaly_type]}")
    print("================================================")


if __name__ == "__main__":
    run_seed()
