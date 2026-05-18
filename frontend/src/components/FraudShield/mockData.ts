export type AlertCardData = {
  id: string;
  badge: "CRITICAL" | "WARNING" | "MONITORING";
  variant: "critical" | "warning" | "monitoring";
  title: string;
  body: string;
  metricLabel: string;
  metricValue: string;
  ctaLabel: string;
};

export type MetricData = {
  id: string;
  label: string;
  value: string;
  trend?: string;
  trendTone?: "rose" | "amber" | "muted";
  subtitle?: string;
  sparkline: number[];
  sparkColor: string;
  icon: "flag" | "users" | "rupee" | "file";
};

export type TypologyId = "mule-chain" | "smurfing" | "ato-mule" | "synthetic-id" | "crypto-exit";

export type TypologyData = {
  id: TypologyId;
  name: string;
  riskScore: number;
  indicators: { text: string; tone: "rose" | "amber" | "purple" | "cyan" }[];
  controls: string[];
  evasion: string[];
};

export type FlaggedTransaction = {
  time: string;
  txnId: string;
  from: string;
  to: string;
  amount: string;
  typology: string;
  riskScore: number;
};

export const ALERT_CARDS: AlertCardData[] = [
  {
    id: "chain",
    badge: "CRITICAL",
    variant: "critical",
    title: "Suspicious chain detected",
    body: "3 accounts forwarded ₹82,000 within 14 minutes. Matches multi-hop mule pattern.",
    metricLabel: "POSSIBLE EXPOSURE",
    metricValue: "₹82,000",
    ctaLabel: "Review →",
  },
  {
    id: "structuring",
    badge: "WARNING",
    variant: "warning",
    title: "Structuring pattern flagged",
    body: "9 transactions just below ₹50,000 threshold detected across linked accounts today.",
    metricLabel: "SAVE UP TO",
    metricValue: "₹4,30,000 frozen",
    ctaLabel: "Alerts →",
  },
  {
    id: "ato",
    badge: "MONITORING",
    variant: "monitoring",
    title: "Account takeover risk",
    body: "New device login followed by beneficiary change and large transfer. Review immediately.",
    metricLabel: "RISK SCORE",
    metricValue: "92/100",
    ctaLabel: "Details →",
  },
];

export const METRICS: MetricData[] = [
  {
    id: "flagged",
    label: "Flagged Today",
    value: "247",
    trend: "+14.2%",
    trendTone: "rose",
    sparkline: [12, 18, 15, 22, 28, 24, 31, 35, 38, 42, 45, 52],
    sparkColor: "#fb7185",
    icon: "flag",
  },
  {
    id: "mules",
    label: "Mule Accounts",
    value: "38",
    trend: "+3 new",
    trendTone: "amber",
    sparkline: [8, 10, 9, 12, 14, 13, 16, 18, 20, 22, 24, 26],
    sparkColor: "#fbbf24",
    icon: "users",
  },
  {
    id: "var",
    label: "Value at Risk",
    value: "₹2.4Cr",
    trend: "+8.1%",
    trendTone: "rose",
    sparkline: [20, 22, 25, 24, 28, 30, 32, 35, 38, 40, 42, 48],
    sparkColor: "#fb7185",
    icon: "rupee",
  },
  {
    id: "sar",
    label: "SAR Pending",
    value: "7",
    subtitle: "3 due today",
    trendTone: "muted",
    sparkline: [7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7],
    sparkColor: "#8b8fa8",
    icon: "file",
  },
];

export const TYPOLOGIES: TypologyData[] = [
  {
    id: "mule-chain",
    name: "Mule Chain",
    riskScore: 94,
    indicators: [
      { text: "3-hop forwarding within 14 min window", tone: "rose" },
      { text: "Dormant account reactivated before burst", tone: "amber" },
      { text: "Beneficiary graph overlap ≥ 0.82", tone: "purple" },
    ],
    controls: ["Velocity caps", "Graph scoring", "Cooling period"],
    evasion: ["Micro-splits", "Weekend timing", "UPI collect loops"],
  },
  {
    id: "smurfing",
    name: "Smurfing",
    riskScore: 88,
    indicators: [
      { text: "9 txns clustered at ₹49,800–₹49,999", tone: "rose" },
      { text: "Shared device fingerprint across payees", tone: "amber" },
      { text: "Round-trip credits within 2 hours", tone: "cyan" },
    ],
    controls: ["Threshold proximity", "Linked account watch"],
    evasion: ["Split across banks", "Cash deposit bridge"],
  },
  {
    id: "ato-mule",
    name: "ATO Mule",
    riskScore: 92,
    indicators: [
      { text: "New device + geo jump > 400 km", tone: "rose" },
      { text: "Beneficiary added < 6 min before transfer", tone: "amber" },
      { text: "Password reset 11 min prior", tone: "purple" },
    ],
    controls: ["Step-up auth", "Beneficiary cooling"],
    evasion: ["SIM swap", "Social engineering"],
  },
  {
    id: "synthetic-id",
    name: "Synthetic ID",
    riskScore: 76,
    indicators: [
      { text: "PAN–mobile mismatch in KYC trail", tone: "amber" },
      { text: "Thin-file credit spike in 30 days", tone: "purple" },
      { text: "Address velocity across 4 PIN codes", tone: "cyan" },
    ],
    controls: ["Document liveness", "Bureau cross-check"],
    evasion: ["Layered nominees", "Shell merchants"],
  },
  {
    id: "crypto-exit",
    name: "Crypto Exit",
    riskScore: 81,
    indicators: [
      { text: "P2P exchange credits after cash deposits", tone: "rose" },
      { text: "Wallet tag matched to flagged VASP", tone: "amber" },
      { text: "INR outflow to offshore card MCC", tone: "purple" },
    ],
    controls: ["VASP denylist", "MCC blocklist"],
    evasion: ["P2P layering", "Gift card bridge"],
  },
];

export const FLAGGED_TRANSACTIONS: FlaggedTransaction[] = [
  {
    time: "14:02 IST",
    txnId: "TXN-9F2A81",
    from: "HDFC ···4821",
    to: "UPI · mule_aj***",
    amount: "₹49,950",
    typology: "Smurfing",
    riskScore: 91,
  },
  {
    time: "13:58 IST",
    txnId: "TXN-7C11B3",
    from: "ICICI ···9033",
    to: "AXIS ···2204",
    amount: "₹28,000",
    typology: "Mule Chain",
    riskScore: 96,
  },
  {
    time: "13:41 IST",
    txnId: "TXN-4D88E0",
    from: "SBI ···1147",
    to: "Beneficiary NEW",
    amount: "₹1,85,000",
    typology: "ATO Mule",
    riskScore: 92,
  },
  {
    time: "13:22 IST",
    txnId: "TXN-2A90FF",
    from: "Kotak ···6612",
    to: "WazirX P2P",
    amount: "₹74,500",
    typology: "Crypto Exit",
    riskScore: 84,
  },
  {
    time: "12:55 IST",
    txnId: "TXN-1B77C2",
    from: "Axis ···0091",
    to: "IMPS · shell_co",
    amount: "₹49,800",
    typology: "Smurfing",
    riskScore: 88,
  },
  {
    time: "12:31 IST",
    txnId: "TXN-0E44A9",
    from: "PNB ···3380",
    to: "UPI · fwd_layer2",
    amount: "₹41,200",
    typology: "Mule Chain",
    riskScore: 79,
  },
];
