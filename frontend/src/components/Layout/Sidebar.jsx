import React, { useMemo } from "react";
import { motion } from "framer-motion";
import {
  Bell,
  ChevronLeft,
  ChevronRight,
  CreditCard,
  LayoutDashboard,
  LogOut,
  Shield,
  ShoppingBag,
  Sparkles,
  TrendingUp,
} from "lucide-react";

const BASE_NAV = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "emi", label: "EMI Tracker", icon: CreditCard },
  { id: "fraud", label: "Fraud Shield", icon: Shield },
  { id: "subscriptions", label: "Subscriptions", icon: Bell },
  { id: "dark-patterns", label: "Analytics", icon: TrendingUp },
  { id: "purchase", label: "Purchase Planner", icon: ShoppingBag },
  { id: "festival", label: "Festival Planner", icon: Sparkles },
];

const sidebarWidth = (collapsed) => (collapsed ? 84 : 280);

const Sidebar = ({ collapsed, onToggle, activeTab, onTabChange, onLogout, fraudBadgeCount }) => {
  const navItems = useMemo(() => {
    return BASE_NAV.map((item) =>
      item.id === "fraud" &&
      typeof fraudBadgeCount === "number" &&
      fraudBadgeCount > 0
        ? { ...item, badge: fraudBadgeCount }
        : item
    );
  }, [fraudBadgeCount]);

  return (
    <motion.aside
      initial={{ x: -280 }}
      animate={{ x: 0, width: sidebarWidth(collapsed) }}
      transition={{ type: "spring", stiffness: 280, damping: 32 }}
      className="fixed left-0 top-0 z-50 flex h-screen flex-col overflow-hidden border-r border-exiqo-purple/20 bg-gradient-to-b from-exiqo-navy via-exiqo-dark/80 to-exiqo-navy"
    >
      <div className="flex h-20 items-center justify-between border-b border-exiqo-purple/15 px-5">
        {!collapsed ? (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center gap-3">
            <div className="relative h-10 w-10">
              <div className="absolute -inset-1 rounded-xl bg-gradient-to-br from-exiqo-purple to-exiqo-pink opacity-40 blur-md" />
              <div className="absolute inset-0 flex items-center justify-center rounded-xl bg-gradient-to-br from-exiqo-purple to-exiqo-pink shadow-lg shadow-purple-glow">
                <Shield size={20} className="text-white" />
              </div>
            </div>
            <div>
              <h3 className="text-base font-bold text-white">SmartSpend</h3>
              <p className="text-xs font-medium text-exiqo-glow">EXIQO Analytics</p>
            </div>
          </motion.div>
        ) : (
          <div className="relative mx-auto h-10 w-10">
            <div className="absolute inset-0 flex items-center justify-center rounded-xl bg-gradient-to-br from-exiqo-purple to-exiqo-pink shadow-purple-glow">
              <Shield size={20} className="text-white" />
            </div>
          </div>
        )}

        <button
          type="button"
          onClick={onToggle}
          className={`rounded-lg p-1.5 text-exiqo-glow/80 transition hover:bg-exiqo-purple/15 hover:text-white ${
            collapsed ? "ml-auto" : ""
          }`}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
        </button>
      </div>

      <nav className="flex-1 space-y-1 px-3 py-5">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <motion.button
              key={item.id}
              type="button"
              onClick={() => onTabChange(item.id)}
              whileHover={{ x: 4 }}
              whileTap={{ scale: 0.98 }}
              className={`group relative flex w-full items-center gap-3 rounded-xl px-3 py-2.5 transition-all duration-200 ${
                isActive
                  ? "bg-exiqo-purple/15 text-white shadow-md shadow-exiqo-purple/10"
                  : "text-exiqo-glow/70 hover:bg-exiqo-purple/10 hover:text-white"
              }`}
            >
              {isActive ? (
                <motion.div
                  layoutId="active-indicator"
                  transition={{ type: "spring", stiffness: 500, damping: 30 }}
                  className="absolute left-0 top-1/2 h-7 w-1 -translate-y-1/2 rounded-r-full bg-gradient-to-b from-exiqo-purple to-exiqo-pink shadow-purple-glow"
                />
              ) : null}
              <Icon
                size={18}
                className={`${collapsed ? "mx-auto" : ""} ${isActive ? "text-exiqo-glow" : ""}`}
              />
              {!collapsed ? <span className="flex-1 text-left text-sm font-medium">{item.label}</span> : null}
              {!collapsed && item.badge ? (
                <span className="rounded-md bg-exiqo-pink px-2 py-0.5 text-xs font-bold text-white shadow-pink-glow">
                  {item.badge}
                </span>
              ) : null}
              {collapsed ? (
                <span className="pointer-events-none absolute left-full ml-2 whitespace-nowrap rounded-lg border border-exiqo-purple/30 bg-exiqo-dark px-3 py-1.5 text-sm text-white opacity-0 shadow-xl transition-opacity group-hover:opacity-100">
                  {item.label}
                  {item.badge ? (
                    <span className="ml-2 rounded-md bg-exiqo-pink px-1.5 py-0.5 text-xs text-white">
                      {item.badge}
                    </span>
                  ) : null}
                </span>
              ) : null}
            </motion.button>
          );
        })}
      </nav>

      <div className="px-3 pb-6">
        <motion.button
          type="button"
          onClick={onLogout}
          whileHover={{ x: 4 }}
          whileTap={{ scale: 0.98 }}
          className="group relative flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-rose-400 transition-all duration-200 hover:bg-rose-500/10 hover:text-rose-300"
        >
          <LogOut size={18} className={collapsed ? "mx-auto" : ""} />
          {!collapsed ? <span className="text-sm font-medium">Logout</span> : null}
          {collapsed ? (
            <span className="pointer-events-none absolute left-full ml-2 whitespace-nowrap rounded-lg border border-exiqo-purple/30 bg-exiqo-dark px-3 py-1.5 text-sm text-white opacity-0 shadow-xl transition-opacity group-hover:opacity-100">
              Logout
            </span>
          ) : null}
        </motion.button>
      </div>
    </motion.aside>
  );
};

export default Sidebar;
