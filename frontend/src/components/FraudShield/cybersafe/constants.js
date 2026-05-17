/** CyberSafe Connect design tokens — flat dark surfaces, no gradients/shadows */

export const CS = {
  bg: "#0f1117",
  card: "#1a1d27",
  border: "rgba(255,255,255,0.08)",
  purple: "#7c3aed",
  teal: "#0f6e56",
  danger: "#e24b4a",
  warningBg: "#faeeda",
  warningText: "#854f0b",
  text: "#f1f5f9",
  muted: "#94a3b8",
  tertiary: "#64748b",
  radiusCard: "12px",
  radiusBtn: "10px",
  radiusBadge: "20px",
};

export const CASE_REF = "CC-2025-08492";
export const CYBERCELL_ID = "CC-MH-2049821";

export const SCAM_CARDS = [
  {
    id: "upi-fraud",
    title: "UPI Fraud",
    icon: "Smartphone",
    description: "Scammers send fake payment requests or QR codes to drain your account instantly.",
  },
  {
    id: "otp-scam",
    title: "OTP Scam",
    icon: "MessageSquare",
    description: "Never share OTPs — fraudsters pose as bank officials to authorize transfers.",
  },
  {
    id: "fake-kyc",
    title: "Fake KYC",
    icon: "FileWarning",
    description: "Phishing links mimic KYC updates to steal credentials and linked bank details.",
  },
];

export const TIMELINE_STEPS = [
  { id: 1, title: "Report submitted to Cybercell", time: "14 May, 3:52 PM", done: true },
  { id: 2, title: "Case registered: #CC-2025-08492", time: "14 May, 4:10 PM", done: true },
  { id: 3, title: "Bank account freeze requested", time: "15 May, 10:30 AM", done: true },
  { id: 4, title: "Bank confirms freeze", time: "Pending", done: false },
  { id: 5, title: "Money recovery initiated", time: "Pending", done: false },
];
