"""
Smart Bank Statement Parser
Automatically detects bank format and parses transactions
Supports: HDFC, SBI, ICICI, Axis, Kotak
"""

from __future__ import annotations

import logging
import re
from datetime import time
from typing import Any, Dict, List, Tuple

import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BankStatementParser:
    """Auto-detects and parses Indian bank statements"""

    CATEGORY_KEYWORDS: dict[str, list[str]] = {
        "Food & Dining": [
            "SWIGGY",
            "ZOMATO",
            "DOMINOS",
            "MCDONALD",
            "KFC",
            "PIZZA",
            "STARBUCKS",
            "CCD",
            "CAFE",
            "RESTAURANT",
            "HALDIRAM",
            "FOOD",
        ],
        "Transport": [
            "UBER",
            "OLA",
            "RAPIDO",
            "PETROL",
            "FUEL",
            "INDIAN OIL",
            "HP PETROL",
            "BHARAT PETROLEUM",
            "IRCTC",
            "RAILWAY",
            "METRO",
            "CAB",
        ],
        "Shopping": [
            "AMAZON",
            "FLIPKART",
            "MYNTRA",
            "AJIO",
            "MEESHO",
            "DMART",
            "RELIANCE",
            "BIGBASKET",
            "BLINKIT",
            "ZEPTO",
            "MALL",
        ],
        "Bills & Utilities": [
            "ELECTRICITY",
            "ADANI",
            "TATA POWER",
            "JIO",
            "AIRTEL",
            "VI",
            "INTERNET",
            "FIBERNET",
            "RECHARGE",
            "BBPS",
            "DTH",
            "TATA SKY",
            "BILL PAYMENT",
        ],
        "Entertainment": [
            "NETFLIX",
            "HOTSTAR",
            "SPOTIFY",
            "PRIME",
            "YOUTUBE",
            "BOOKMYSHOW",
            "PVR",
            "INOX",
            "CINEMA",
        ],
        "Healthcare": [
            "APOLLO",
            "PHARMACY",
            "MEDICAL",
            "HOSPITAL",
            "NETMEDS",
            "PHARMEASY",
            "DOCTOR",
            "CLINIC",
            "FORTIS",
        ],
        "Housing": ["RENT", "SOCIETY", "MAINTENANCE", "LANDLORD"],
        "Investment": ["SIP", "MUTUAL", "ZERODHA", "GROWW", "INSURANCE", "PREMIUM"],
        "Salary": ["SALARY", "PAYROLL", "WAGES"],
        "Finance & Investment": ["CRYPTOX", "BINANCE", "FOREX", "TRADING", "OFFSHORE"],
    }

    def detect_bank(self, df: pd.DataFrame) -> str:
        """Auto-detect bank from column headers"""
        columns = [str(col).strip() for col in df.columns]
        logger.info("Detecting bank from columns: %s", columns)

        if "Narration" in columns and "Chq./Ref.No." in columns:
            return "HDFC"
        if "Transaction Date" in columns and "Withdrawal Amount (INR)" in columns:
            return "ICICI"
        if "Particulars" in columns and "Tran Date" in columns:
            return "Axis"
        if "Txn Date" in columns and "Description" in columns and "Ref No./Cheque No." in columns:
            return "SBI"
        if len(columns) == 6 and "Description" in columns and "Date" in columns and "Ref No." in columns:
            return "Kotak"
        raise ValueError(f"Unknown bank format. Columns: {columns}")

    def extract_merchant_and_mode(self, text: str) -> Tuple[str, str]:
        """Extract merchant name and transaction mode from description"""
        raw = text.strip()
        u = raw.upper()

        if "UPI" in u and "UPI/" in u:
            mode = "UPI"
            m = re.search(r"UPI/(?:CR|DR)?/?\d*/?([A-Z0-9][A-Z0-9\s\.\&\-]{1,40}?)/[a-z0-9@]+", raw, re.I)
            if m:
                return self._clean_merchant(m.group(1)), mode
            m2 = re.search(r"UPI/\d+/([A-Z0-9][A-Z0-9\s\.\&\-]{1,40}?)/", raw, re.I)
            if m2:
                return self._clean_merchant(m2.group(1)), mode
        if "UPI" in u and ("UPI-" in u or raw.upper().startswith("UPI")):
            mode = "UPI"
            m = re.search(r"UPI-([^-/@\n]+)", raw, re.I)
            if m:
                return self._clean_merchant(m.group(1)), mode
        if "UPI P2M" in u:
            mode = "UPI"
            m = re.search(r"UPI P2M\s+([A-Z0-9][A-Z0-9\s]{1,35}?)\s+[A-Z0-9@]+", raw, re.I)
            if m:
                return self._clean_merchant(m.group(1)), mode

        if "NEFT" in u:
            mode = "NEFT"
            m = re.search(r"NEFT\s+(?:CR|INWARD|DR|OUTWARD)?-?\s*([A-Z0-9][A-Z0-9\s\.\&\-]{2,45}?)(?:\s+SALARY|\s+RENT|\s+N\d|-N\d|-[A-Z]{3,}\d)", raw, re.I)
            if m:
                return self._clean_merchant(m.group(1)), mode
            m2 = re.search(r"NEFT-[A-Z]{4}\d+-([A-Z0-9][A-Z0-9\s\.\&\-]{2,45}?)-", raw, re.I)
            if m2:
                return self._clean_merchant(m2.group(1)), mode

        if "IMPS" in u:
            mode = "IMPS"
            m = re.search(r"IMPS[-\s]+(?:P2A|OUT)?[-\s]*\d*[-\s]*([A-Z][A-Z\s]{2,35}?)(?:-|\s+[A-Z]{3,}\b)", raw, re.I)
            if m:
                return self._clean_merchant(m.group(1)), mode
            if "FT TO" in u:
                m2 = re.search(r"FT TO\s+([A-Z][A-Z\s]{2,35}?)\s+IMPS", raw, re.I)
                if m2:
                    return self._clean_merchant(m2.group(1)), mode
            return "IMPS Transfer", mode

        if "POS" in u or "POS PURCHASE" in u:
            mode = "CARD"
            m = re.search(r"POS\s+\d+\s+(.+?)(?:\s+MUMBAI|\s+DELHI|\s+BANGALORE|\s+CARD\b)", raw, re.I)
            if m:
                return self._clean_merchant(m.group(1)), mode
            m2 = re.search(r"POS PURCHASE\s+(.+?)\s+MUMBAI", raw, re.I)
            if m2:
                return self._clean_merchant(m2.group(1)), mode

        if "ECOM" in u:
            mode = "CARD"
            m = re.search(r"ECOM\s+([A-Z0-9\.\s]+?)(?:\s+CARD|\s+TXN)", raw, re.I)
            if m:
                return self._clean_merchant(m.group(1)), mode

        if "BBPS" in u or "BILL PAYMENT" in u:
            mode = "BILL_PAYMENT"
            m = re.search(r"BBPS[/\-]([A-Z\s]+?)[/\-]", raw, re.I)
            if m:
                return self._clean_merchant(m.group(1)), mode
            m2 = re.search(r"BILL PAYMENT\s+(.+?)(?:\s+REF|\s+MUMBAI|$)", raw, re.I)
            if m2:
                return self._clean_merchant(m2.group(1)), mode
            return "Bill Payment", mode

        if "ATM" in u:
            return "ATM Withdrawal", "ATM"

        if "PURCHASE AT" in u:
            mode = "CARD"
            m = re.search(r"PURCHASE AT\s+(.+?)\s+ON\s+", raw, re.I)
            if m:
                return self._clean_merchant(m.group(1)), mode

        return "Unknown", "OTHER"

    @staticmethod
    def _clean_merchant(s: str) -> str:
        x = re.sub(r"\s+", " ", s.strip())
        return x[:120] if x else "Unknown"

    def categorize(self, text: str) -> str:
        """Auto-categorize transaction based on keywords"""
        text_upper = text.upper()
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            if any(keyword in text_upper for keyword in keywords):
                return category
        return "Others"

    def _row_to_txn(
        self,
        *,
        bank: str,
        txn_date: date,
        withdrawal: Any,
        deposit: Any,
        balance: float,
        description: str,
    ) -> Dict[str, Any] | None:
        w = pd.to_numeric(withdrawal, errors="coerce")
        d = pd.to_numeric(deposit, errors="coerce")
        if pd.notna(w) and float(w) > 0:
            txn_type, amount = "DEBIT", float(w)
        elif pd.notna(d) and float(d) > 0:
            txn_type, amount = "CREDIT", float(d)
        else:
            return None
        merchant, mode = self.extract_merchant_and_mode(description)
        category = self.categorize(description)
        return {
            "transaction_date": txn_date,
            "transaction_time": time(0, 0, 0),
            "amount": amount,
            "type": txn_type,
            "description": description,
            "merchant": merchant,
            "category": category,
            "location": "Mumbai",
            "balance_after": float(balance),
            "transaction_mode": mode,
            "bank_name": bank,
        }

    def parse_hdfc(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        logger.info("Parsing HDFC format")
        transactions: List[Dict[str, Any]] = []
        for idx, row in df.iterrows():
            try:
                txn_date = pd.to_datetime(row["Date"], format="%d/%m/%y", errors="coerce")
                if pd.isna(txn_date):
                    continue
                t = self._row_to_txn(
                    bank="HDFC",
                    txn_date=txn_date.date(),
                    withdrawal=row["Withdrawal Amt."],
                    deposit=row["Deposit Amt."],
                    balance=row["Closing Balance"],
                    description=str(row["Narration"]),
                )
                if t:
                    transactions.append(t)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Error parsing HDFC row %s: %s", idx, exc)
        logger.info("Parsed %s HDFC transactions", len(transactions))
        return transactions

    def parse_sbi(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        logger.info("Parsing SBI format")
        transactions = []
        for idx, row in df.iterrows():
            try:
                txn_date = pd.to_datetime(row["Txn Date"], format="%d %b %Y", errors="coerce")
                if pd.isna(txn_date):
                    continue
                t = self._row_to_txn(
                    bank="SBI",
                    txn_date=txn_date.date(),
                    withdrawal=row["Debit"],
                    deposit=row["Credit"],
                    balance=row["Balance"],
                    description=str(row["Description"]),
                )
                if t:
                    transactions.append(t)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Error parsing SBI row %s: %s", idx, exc)
        logger.info("Parsed %s SBI transactions", len(transactions))
        return transactions

    def parse_icici(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        logger.info("Parsing ICICI format")
        transactions = []
        for idx, row in df.iterrows():
            try:
                txn_date = pd.to_datetime(row["Transaction Date"], format="%d-%m-%Y", errors="coerce")
                if pd.isna(txn_date):
                    continue
                t = self._row_to_txn(
                    bank="ICICI",
                    txn_date=txn_date.date(),
                    withdrawal=row["Withdrawal Amount (INR)"],
                    deposit=row["Deposit Amount (INR)"],
                    balance=row["Available Balance (INR)"],
                    description=str(row["Description"]),
                )
                if t:
                    transactions.append(t)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Error parsing ICICI row %s: %s", idx, exc)
        logger.info("Parsed %s ICICI transactions", len(transactions))
        return transactions

    def parse_axis(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        logger.info("Parsing Axis format")
        transactions = []
        for idx, row in df.iterrows():
            try:
                txn_date = pd.to_datetime(row["Tran Date"], format="%d-%m-%Y", errors="coerce")
                if pd.isna(txn_date):
                    continue
                t = self._row_to_txn(
                    bank="Axis",
                    txn_date=txn_date.date(),
                    withdrawal=row["Withdrawal"],
                    deposit=row["Deposit"],
                    balance=row["Closing Balance"],
                    description=str(row["Particulars"]),
                )
                if t:
                    transactions.append(t)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Error parsing Axis row %s: %s", idx, exc)
        logger.info("Parsed %s Axis transactions", len(transactions))
        return transactions

    def parse_kotak(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        logger.info("Parsing Kotak format")
        transactions = []
        for idx, row in df.iterrows():
            try:
                txn_date = pd.to_datetime(row["Date"], format="%d/%m/%Y", errors="coerce")
                if pd.isna(txn_date):
                    continue
                t = self._row_to_txn(
                    bank="Kotak",
                    txn_date=txn_date.date(),
                    withdrawal=row["Debit"],
                    deposit=row["Credit"],
                    balance=row["Balance"],
                    description=str(row["Description"]),
                )
                if t:
                    transactions.append(t)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Error parsing Kotak row %s: %s", idx, exc)
        logger.info("Parsed %s Kotak transactions", len(transactions))
        return transactions

    def parse(self, file_path: str) -> Dict[str, Any]:
        """Main parsing function - auto-detects bank and parses"""
        logger.info("Starting to parse: %s", file_path)
        df = pd.read_csv(file_path)
        df = df.dropna(how="all")
        bank = self.detect_bank(df)
        logger.info("Detected bank: %s", bank)
        if bank == "HDFC":
            transactions = self.parse_hdfc(df)
        elif bank == "SBI":
            transactions = self.parse_sbi(df)
        elif bank == "ICICI":
            transactions = self.parse_icici(df)
        elif bank == "Axis":
            transactions = self.parse_axis(df)
        elif bank == "Kotak":
            transactions = self.parse_kotak(df)
        else:
            raise ValueError(f"Unsupported bank: {bank}")
        dates = [t["transaction_date"] for t in transactions]
        date_range = f"{min(dates)} to {max(dates)}" if dates else "No dates"
        return {
            "bank_name": bank,
            "transactions": transactions,
            "total_count": len(transactions),
            "date_range": date_range,
        }


def parse_bank_csv(file_path: str) -> Dict[str, Any]:
    """Parse any supported bank CSV file"""
    return BankStatementParser().parse(file_path)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        result = parse_bank_csv(sys.argv[1])
        print(f"\n[OK] Parsed {result['bank_name']} statement")
        print(f"   Transactions: {result['total_count']}")
        print(f"   Date range: {result['date_range']}")
        if result["transactions"]:
            print("\n   Sample transaction:")
            print(f"   {result['transactions'][0]}")
    else:
        print("Usage: python bank_parser.py <csv_file_path>")
