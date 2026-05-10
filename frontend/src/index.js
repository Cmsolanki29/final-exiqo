import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { AuthProvider } from "./context/AuthContext";
import { RiskProvider } from "./contexts/RiskContext";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <AuthProvider>
      <RiskProvider>
        <App />
      </RiskProvider>
    </AuthProvider>
  </React.StrictMode>
);
