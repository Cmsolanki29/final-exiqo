import React, { createContext, useCallback, useContext, useMemo, useState } from "react";

const ToastContext = createContext({
  showToast: () => {},
});

export const ToastProvider = ({ children }) => {
  const [toast, setToast] = useState(null);

  const showToast = useCallback((message, type = "success") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  }, []);

  const value = useMemo(() => ({ showToast }), [showToast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastDisplay toast={toast} />
    </ToastContext.Provider>
  );
};

export const useToast = () => useContext(ToastContext);

export const ToastDisplay = ({ toast }) => {
  if (!toast) return null;

  const colors = {
    success: "#10b981",
    error: "#ef4444",
    warning: "#f59e0b",
    info: "#3b82f6",
  };

  const bg = colors[toast.type] || colors.info;

  return (
    <div
      role="status"
      className="toast-display"
      style={{
        position: "fixed",
        bottom: "24px",
        right: "24px",
        padding: "12px 20px",
        borderRadius: "12px",
        background: bg,
        color: "white",
        fontSize: "14px",
        fontWeight: "500",
        zIndex: 9999,
        boxShadow: "0 8px 24px rgba(0,0,0,0.3)",
        animation: "fadeIn 0.3s ease",
        maxWidth: "min(420px, 92vw)",
      }}
    >
      {toast.type === "success" && "✅ "}
      {toast.type === "error" && "❌ "}
      {toast.type === "warning" && "⚠️ "}
      {toast.message}
    </div>
  );
};
