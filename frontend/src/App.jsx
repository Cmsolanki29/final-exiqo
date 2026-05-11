import React, { lazy, Suspense, useEffect, useMemo, useState } from "react";
import OnboardingPage from "./app/onboarding/page";
import Dashboard from "./components/Dashboard/Dashboard";
import FestivalPredictor from "./components/Festival/FestivalPredictor";
import FraudShieldPage from "./components/FraudShield/FraudShieldPage";
import PurchasePlanner from "./components/Purchase/PurchasePlanner";
import DarkPatternDetector from "./components/DarkPatterns/DarkPatternDetector";
import EMITrapDetector from "./components/EMI/EMITrapDetector";
import Sidebar from "./components/Layout/Sidebar";
import TopBar from "./components/Layout/TopBar";
import SubscriptionGraveyard from "./components/Subscriptions/SubscriptionGraveyard";
import IntroFlow from "./components/intro/IntroFlow";
import { ToastProvider } from "./components/common/Toast";
import { SkeletonCard } from "./components/common/SkeletonCard";
import { useAuth } from "./context/AuthContext";
import { getUsers } from "./services/api";
// Phase 1-8 Risk Engine pages
const TrustCenter = lazy(() => import("./pages/risk/TrustCenter"));
const AIPerformance = lazy(() => import("./pages/risk/AIPerformance"));
const AlertsCenter = lazy(() => import("./pages/risk/AlertsCenter"));
const BehaviorProfile = lazy(() => import("./pages/risk/BehaviorProfile"));
const DeviceTrust = lazy(() => import("./pages/risk/DeviceTrust"));

// Phase 9-12 pages
const InvestigationViewer = lazy(() => import("./pages/risk/InvestigationViewer"));
const OrchestratorDashboard = lazy(() => import("./pages/risk/OrchestratorDashboard"));
const DNNShadowReport = lazy(() => import("./pages/risk/DNNShadowReport"));
const GNNTrainingPanel = lazy(() => import("./pages/risk/GNNTrainingPanel"));

const App = () => {
  const { user, loading: authLoading, logout, isAuthenticated } = useAuth();
  const [users, setUsers] = useState([]);
  const [selectedUserId, setSelectedUserId] = useState(1);
  const [darkMode, setDarkMode] = useState(true);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [activeTab, setActiveTab] = useState("dashboard");
  const [loadingUsers, setLoadingUsers] = useState(true);
  const [userError, setUserError] = useState("");

  const today = useMemo(() => new Date(), []);
  const [month, setMonth] = useState(today.getMonth() + 1);
  const [year, setYear] = useState(today.getFullYear());

  const selectedUser = useMemo(
    () => (users || []).find((u) => u.id === selectedUserId),
    [users, selectedUserId]
  );

  useEffect(() => {
    document.documentElement.classList.toggle("light", !darkMode);
    document.body.classList.toggle("light", !darkMode);
  }, [darkMode]);

  useEffect(() => {
    if (!isAuthenticated || !user) {
      setUsers([]);
      setLoadingUsers(false);
      return;
    }
    let cancelled = false;
    (async () => {
      setLoadingUsers(true);
      setUserError("");
      setSelectedUserId(user.id);
      try {
        const response = await getUsers();
        if (cancelled) return;
        setUsers(response || []);
        if (response?.length && !response.find((u) => u.id === user.id)) {
          setSelectedUserId(response[0].id);
        }
      } catch (error) {
        if (!cancelled) setUserError(error.message || "Unable to load users");
      } finally {
        if (!cancelled) setLoadingUsers(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, user]);

  if (authLoading) {
    return (
      <ToastProvider>
        <div className="app-shell">
          <div style={{ marginTop: 24 }}>
            <SkeletonCard lines={4} height={88} />
          </div>
        </div>
      </ToastProvider>
    );
  }

  if (!isAuthenticated) {
    // Cinematic intro flow: splash -> intro story -> get started -> auth -> dashboard.
    // Returning users (smartspend.seenIntro=true) skip straight to /auth/signin.
    return (
      <ToastProvider>
        <IntroFlow
          onComplete={() => {
            /* AuthContext flips isAuthenticated, which unmounts the flow. */
          }}
        />
      </ToastProvider>
    );
  }

  if (user && user.onboarding_completed !== true) {
    return (
      <ToastProvider>
        <OnboardingPage />
      </ToastProvider>
    );
  }

  return (
    <ToastProvider>
      <div className="relative min-h-screen overflow-hidden bg-exiqo-navy">
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div
            className="exiqo-bg-orb absolute -right-20 -top-20 h-[600px] w-[600px] rounded-full bg-exiqo-purple/8 blur-[140px]"
            style={{ animation: "exiqo-orb-pulse 8s ease-in-out infinite" }}
          />
          <div
            className="exiqo-bg-orb absolute -bottom-20 -left-20 h-[500px] w-[500px] rounded-full bg-exiqo-pink/6 blur-[120px]"
            style={{ animation: "exiqo-orb-pulse 8s ease-in-out infinite 1s" }}
          />
        </div>

        <Sidebar
          collapsed={sidebarCollapsed}
          onToggle={() => setSidebarCollapsed((v) => !v)}
          activeTab={activeTab}
          onTabChange={setActiveTab}
          onLogout={logout}
        />

        <div
          style={{ marginLeft: sidebarCollapsed ? 84 : 280 }}
          className="relative z-10 min-h-screen transition-all duration-300"
        >
          <TopBar
            userName={selectedUser?.name || user?.name || user?.email || "User"}
            month={month}
            year={year}
            onMonthChange={setMonth}
            onYearChange={setYear}
          />

          <div className="p-5 lg:p-7">
            {loadingUsers ? (
              <div style={{ marginTop: 4 }}>
                <SkeletonCard lines={4} height={88} />
              </div>
            ) : userError ? (
              <div className="error-card glass-card" style={{ marginTop: 4 }}>
                <p>Could not load users: {userError}</p>
                <button type="button" onClick={() => window.location.reload()}>
                  Retry
                </button>
              </div>
            ) : (
              <div key={activeTab} className="tab-panel-enter">
                {activeTab === "dashboard" && (
                  <Dashboard
                    userId={selectedUserId}
                    month={month}
                    year={year}
                    onMonthChange={setMonth}
                    onYearChange={setYear}
                    onOpenFraudShield={() => setActiveTab("fraud")}
                    onOpenFestival={() => setActiveTab("festival")}
                    onOpenPurchase={() => setActiveTab("purchase")}
                    userName={selectedUser?.name}
                    setActiveTab={setActiveTab}
                  />
                )}
                {activeTab === "emi" && <EMITrapDetector userId={selectedUserId} />}
                {activeTab === "subscriptions" && <SubscriptionGraveyard userId={selectedUserId} />}
                {activeTab === "dark-patterns" && <DarkPatternDetector userId={selectedUserId} />}
                {activeTab === "fraud" && (
                  <FraudShieldPage userId={selectedUserId} userName={selectedUser?.name} />
                )}
                {activeTab === "purchase" && <PurchasePlanner userId={selectedUserId} />}
                {activeTab === "festival" && <FestivalPredictor userId={selectedUserId} />}

                {/* Phase 1-8 Risk Engine */}
                {activeTab === "trust-center" && (
                  <Suspense fallback={<SkeletonCard lines={4} height={88} />}>
                    <TrustCenter userId={selectedUserId} />
                  </Suspense>
                )}
                {activeTab === "ai-performance" && (
                  <Suspense fallback={<SkeletonCard lines={4} height={88} />}>
                    <AIPerformance userId={selectedUserId} />
                  </Suspense>
                )}
                {activeTab === "alerts-center" && (
                  <Suspense fallback={<SkeletonCard lines={4} height={88} />}>
                    <AlertsCenter userId={selectedUserId} />
                  </Suspense>
                )}
                {activeTab === "behavior-profile" && (
                  <Suspense fallback={<SkeletonCard lines={4} height={88} />}>
                    <BehaviorProfile userId={selectedUserId} />
                  </Suspense>
                )}
                {activeTab === "device-trust" && (
                  <Suspense fallback={<SkeletonCard lines={4} height={88} />}>
                    <DeviceTrust userId={selectedUserId} />
                  </Suspense>
                )}

                {/* Phase 9-12 AI Phases */}
                {activeTab === "investigations" && (
                  <Suspense fallback={<SkeletonCard lines={4} height={88} />}>
                    <InvestigationViewer userId={selectedUserId} />
                  </Suspense>
                )}
                {activeTab === "orchestrator" && (
                  <Suspense fallback={<SkeletonCard lines={4} height={88} />}>
                    <OrchestratorDashboard userId={selectedUserId} />
                  </Suspense>
                )}
                {activeTab === "dnn-shadow" && (
                  <Suspense fallback={<SkeletonCard lines={4} height={88} />}>
                    <DNNShadowReport userId={selectedUserId} />
                  </Suspense>
                )}
                {activeTab === "gnn-training" && (
                  <Suspense fallback={<SkeletonCard lines={4} height={88} />}>
                    <GNNTrainingPanel userId={selectedUserId} />
                  </Suspense>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </ToastProvider>
  );
};

export default App;
