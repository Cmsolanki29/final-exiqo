import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { AuthProvider } from "./context/AuthContext";
import { RiskProvider } from "./contexts/RiskContext";
import { ErrorBoundary } from "./components/common/ErrorBoundary";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ErrorBoundary>
      <AuthProvider>
        <RiskProvider>
          <App />
        </RiskProvider>
      </AuthProvider>
    </ErrorBoundary>
  </React.StrictMode>
);
