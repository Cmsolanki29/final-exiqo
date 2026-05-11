import React from "react";
import { AlertTriangle } from "lucide-react";

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            minHeight: "100vh",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "#0a0a1a",
            padding: "2rem",
          }}
        >
          <div
            style={{
              maxWidth: 480,
              width: "100%",
              borderRadius: 20,
              border: "1px solid rgba(239,68,68,0.25)",
              background: "rgba(239,68,68,0.05)",
              padding: "2rem",
              textAlign: "center",
            }}
          >
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: 56,
                height: 56,
                borderRadius: 16,
                background: "rgba(239,68,68,0.15)",
                marginBottom: "1rem",
              }}
            >
              <AlertTriangle size={28} color="#f87171" />
            </div>
            <h2 style={{ color: "#fff", fontSize: "1.25rem", fontWeight: 700, marginBottom: "0.5rem" }}>
              Something went wrong
            </h2>
            <p style={{ color: "rgba(200,200,255,0.6)", fontSize: "0.875rem", marginBottom: "1.5rem" }}>
              {this.state.error?.message || "An unexpected error occurred. The page cannot be displayed."}
            </p>
            <button
              type="button"
              onClick={this.handleReset}
              style={{
                padding: "0.5rem 1.25rem",
                borderRadius: 10,
                background: "linear-gradient(135deg,#7c3aed,#ec4899)",
                color: "#fff",
                fontWeight: 600,
                fontSize: "0.875rem",
                border: "none",
                cursor: "pointer",
                marginRight: "0.75rem",
              }}
            >
              Try again
            </button>
            <button
              type="button"
              onClick={() => window.location.reload()}
              style={{
                padding: "0.5rem 1.25rem",
                borderRadius: 10,
                background: "rgba(255,255,255,0.07)",
                color: "rgba(200,200,255,0.8)",
                fontWeight: 600,
                fontSize: "0.875rem",
                border: "1px solid rgba(255,255,255,0.1)",
                cursor: "pointer",
              }}
            >
              Reload page
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
