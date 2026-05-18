/**
 * NotificationsBell — Bell icon with unread badge and dropdown panel.
 * Every cascade writes a notification; this surfaces them.
 * CyberSafe Connect demo notifications are merged for the Risk Awareness flow.
 */
import React, { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, Bell, BellRing, CheckCircle2, Info, X } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { getNotifications, getSubscriptionRemindersPending, markNotificationsRead } from "../../services/api";
import {
  CYBERSAFE_NOTIFICATION_IDS,
  mergeCyberSafeNotifications,
} from "../FraudShield/cybersafe/cybersafeNotifications";
import {
  enrichReminderRow,
  normalizeRemindersForDisplay,
  reminderCadencePhrase,
  reminderShortTag,
  snoozeRequiresAccountability,
  subscriptionTierBadge,
} from "../../utils/reminderBadges";
import SubscriptionReminderNotifItem from "./SubscriptionReminderNotifItem";

const MARK_ALL_SESSION_KEY = (userId) => `ss_notifs_marked_all_${userId}`;

function subRemindersToNotifs(reminders) {
  const shown = normalizeRemindersForDisplay(reminders).filter(
    (r) => String(r.state || "").toLowerCase() === "shown"
  );
  return shown.map((raw) => {
    const r = enrichReminderRow(raw);
    const cadence = reminderShortTag(r.reminder_type);
    const tier = subscriptionTierBadge(r.reminder_escalation_tier).label;
    const when = reminderCadencePhrase(r.reminder_type);
    const tierNum = Number(r.reminder_escalation_tier ?? 1);
    const locked = snoozeRequiresAccountability(tierNum);
    const isCancel = (r.current_verdict || "").toUpperCase() === "CANCEL";
    const amt = r.monthly_cost ? `₹${Math.round(r.monthly_cost).toLocaleString("en-IN")}/mo` : "";
    return {
      id: `sub-reminder-${r.id}`,
      type: locked ? "alert" : isCancel ? "alert" : "warning",
      title: `${r.merchant || "Subscription"} · ${cadence} · ${tier}`,
      body: `${when}${amt ? ` · ${amt}` : ""}${locked ? " · Tier 2+ — respond below" : isCancel ? " · Consider cancelling" : r.next_billing_date ? ` · Bills on ${r.next_billing_date}` : ""}`,
      is_read: false,
      created_at: r.fire_at,
      _sub_reminder: true,
      _reminder: r,
      _locked: locked,
    };
  });
}

function countUnread(notifications) {
  return (notifications || []).filter((n) => !n.is_read).length;
}

const TYPE_CONFIG = {
  alert: { icon: AlertTriangle, color: "text-rose-300", bg: "bg-rose-500/10 border-rose-500/25" },
  warning: { icon: AlertTriangle, color: "text-amber-300", bg: "bg-amber-500/10 border-amber-500/25" },
  success: { icon: CheckCircle2, color: "text-emerald-300", bg: "bg-emerald-500/10 border-emerald-500/25" },
  info: { icon: Info, color: "text-sky-300", bg: "bg-sky-500/10 border-sky-500/25" },
};

const CYBERSAFE_TYPE_CONFIG = {
  cybersafe_fraud: {
    border: "#e24b4a",
    emoji: "⚠️",
    actionLabel: "Report Now",
    actionTarget: "report",
  },
  cybersafe_case: {
    border: "#0f6e56",
    emoji: "✅",
  },
  cybersafe_reminder: {
    border: "#854f0b",
    emoji: "🕐",
  },
};

function navigateToCyberSafe(screen = "report") {
  try {
    const url = new URL(window.location.href);
    url.searchParams.delete("fraudTab");
    url.searchParams.set("cybersafeScreen", screen);
    window.history.replaceState({}, "", url.toString());
  } catch {
    /* ignore */
  }
  window.dispatchEvent(
    new CustomEvent("smartspend:navigate", {
      detail: { tab: "cybersafe-connect", cybersafeScreen: screen },
    }),
  );
}

function CyberSafeNotifItem({ n, onMarkRead }) {
  const cfg = CYBERSAFE_TYPE_CONFIG[n.type] || CYBERSAFE_TYPE_CONFIG.cybersafe_fraud;
  const ts = n.created_at
    ? new Date(n.created_at).toLocaleString("en-IN", { dateStyle: "short", timeStyle: "short" })
    : "";

  return (
    <motion.div
      className={`rounded-xl border bg-[#1a1d27] p-3 ${!n.is_read ? "ring-1 ring-inset ring-white/10" : "opacity-70"}`}
      style={{ borderLeftWidth: 4, borderLeftColor: cfg.border }}
    >
      <div className="flex gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium leading-relaxed text-[#f1f5f9]">
            {cfg.emoji} {n.title ? `${n.title} — ` : ""}
            {n.body}
          </p>
          <p className="mt-1 text-[10px] text-[#64748b]">{ts}</p>
          {cfg.actionLabel && (
            <button
              type="button"
              onClick={() => navigateToCyberSafe(cfg.actionTarget || "report")}
              className="mt-2 rounded-lg px-3 py-1.5 text-[11px] font-medium text-white"
              style={{ background: "#e24b4a", borderRadius: 10 }}
            >
              {cfg.actionLabel}
            </button>
          )}
        </div>
        {!n.is_read && (
          <button
            type="button"
            onClick={() => onMarkRead(n.id)}
            className="shrink-0 self-start rounded-full p-0.5 text-[#94a3b8] transition hover:text-white"
            title="Mark read"
          >
            <X className="h-3.5 w-3.5" aria-hidden />
          </button>
        )}
      </div>
    </motion.div>
  );
}

function NotifItem({ n, onMarkRead, userId, onReminderResolved, onOpenReminders }) {
  if (n._sub_reminder) {
    return (
      <SubscriptionReminderNotifItem
        n={n}
        userId={userId}
        onResolved={onReminderResolved}
        onOpenReminders={onOpenReminders}
      />
    );
  }

  if (n.type?.startsWith("cybersafe_")) {
    return <CyberSafeNotifItem n={n} onMarkRead={onMarkRead} />;
  }

  const cfg = TYPE_CONFIG[n.type] || TYPE_CONFIG.info;
  const Icon = cfg.icon;
  const ts = n.created_at
    ? new Date(n.created_at).toLocaleString("en-IN", { dateStyle: "short", timeStyle: "short" })
    : "";
  return (
    <motion.div
      className={`flex gap-3 rounded-xl border p-3 ${cfg.bg} ${!n.is_read ? "ring-1 ring-inset ring-white/10" : "opacity-70"}`}
    >
      <span className="mt-0.5 shrink-0">
        <Icon className={`h-4 w-4 ${cfg.color}`} aria-hidden />
      </span>
      <div className="min-w-0 flex-1">
        <p className={`text-xs font-semibold text-white ${!n.is_read ? "" : "opacity-80"}`}>{n.title}</p>
        <p className="mt-0.5 text-[11px] leading-relaxed text-gray-400">{n.body}</p>
        <p className="mt-1 text-[10px] text-gray-600">{ts}</p>
      </div>
      {!n.is_read && (
        <button
          type="button"
          onClick={() => onMarkRead(n.id)}
          className="shrink-0 self-start rounded-full p-0.5 text-exiqo-glow/40 transition hover:text-white"
          title="Mark read"
        >
          <X className="h-3.5 w-3.5" aria-hidden />
        </button>
      )}
    </motion.div>
  );
}

function visibleNotifications(merged, dismissedIds) {
  return merged.filter((n) => n._locked || !dismissedIds.has(n.id));
}

export default function NotificationsBell({ userId }) {
  const { user } = useAuth();
  const subscriptionUserId =
    user?.id != null && Number(user.id) > 0 ? Number(user.id) : null;

  const [open, setOpen] = useState(false);
  const [data, setData] = useState({ unread_count: 0, notifications: [] });
  const [dismissedIds, setDismissedIds] = useState(() => new Set());
  const [cyberSafeSuppressed, setCyberSafeSuppressed] = useState(false);
  const [loading, setLoading] = useState(false);
  const panelRef = useRef(null);

  const load = useCallback(async () => {
    if (!userId && !subscriptionUserId) return;
    setLoading(true);
    try {
      const [res, subRes] = await Promise.allSettled([
        userId ? getNotifications(userId, { limit: 20, unreadOnly: false }) : Promise.resolve({ notifications: [] }),
        subscriptionUserId
          ? getSubscriptionRemindersPending(subscriptionUserId, { include_upcoming: true })
          : Promise.resolve({ reminders: [] }),
      ]);
      const apiNotifs = res.status === "fulfilled" ? (res.value?.notifications || []) : [];
      const subReminders = subRes.status === "fulfilled" ? subRemindersToNotifs(subRes.value?.reminders) : [];

      const merged = mergeCyberSafeNotifications([...apiNotifs, ...subReminders], {
        includeCyberSafe: !cyberSafeSuppressed,
      });
      const filtered = visibleNotifications(merged, dismissedIds);

      setDismissedIds((prev) => {
        const lockedIds = merged.filter((n) => n._locked).map((n) => n.id);
        if (!lockedIds.some((id) => prev.has(id))) return prev;
        const next = new Set(prev);
        for (const id of lockedIds) next.delete(id);
        return next;
      });

      setData({
        notifications: filtered,
        unread_count: countUnread(filtered),
      });
    } catch {
      const merged = mergeCyberSafeNotifications([], { includeCyberSafe: !cyberSafeSuppressed });
      const filtered = visibleNotifications(merged, dismissedIds);
      setData({
        notifications: filtered,
        unread_count: countUnread(filtered),
      });
    } finally {
      setLoading(false);
    }
  }, [userId, subscriptionUserId, dismissedIds, cyberSafeSuppressed]);

  useEffect(() => {
    setData({ unread_count: 0, notifications: [] });
    setDismissedIds(new Set());
    setCyberSafeSuppressed(false);
    setOpen(false);
    if (!userId) return;
    try {
      setCyberSafeSuppressed(sessionStorage.getItem(MARK_ALL_SESSION_KEY(userId)) === "1");
    } catch {
      /* ignore */
    }
  }, [userId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const interval = setInterval(load, 30_000);
    return () => clearInterval(interval);
  }, [load]);

  useEffect(() => {
    const onRemindersChanged = () => {
      void load();
    };
    window.addEventListener("smartspend:reminders-changed", onRemindersChanged);
    return () => window.removeEventListener("smartspend:reminders-changed", onRemindersChanged);
  }, [load]);

  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (panelRef.current && !panelRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const handleReminderResolved = useCallback((notifId) => {
    setDismissedIds((s) => new Set(s).add(String(notifId)));
    setData((d) => {
      const notifications = d.notifications.filter((n) => n.id !== notifId);
      return { notifications, unread_count: countUnread(notifications) };
    });
    void load();
  }, [load]);

  const handleOpenReminders = useCallback(() => {
    setOpen(false);
    window.dispatchEvent(
      new CustomEvent("smartspend:navigate", { detail: { tab: "subscriptions", subView: "reminders" } }),
    );
  }, []);

  const handleMarkRead = async (notifId) => {
    const id = String(notifId);
    const item = (data.notifications || []).find((n) => n.id === notifId);
    if (id.startsWith("sub-reminder-")) {
      if (item?._locked) return;
      setDismissedIds((s) => new Set(s).add(id));
      setData((d) => {
        const notifications = d.notifications.filter((n) => n.id !== notifId);
        return { notifications, unread_count: countUnread(notifications) };
      });
      return;
    }
    if (id.startsWith("cs-")) {
      setDismissedIds((s) => new Set(s).add(id));
      setData((d) => {
        const notifications = d.notifications.filter((n) => n.id !== notifId);
        return { notifications, unread_count: countUnread(notifications) };
      });
      return;
    }
    try {
      await markNotificationsRead(userId, { notification_ids: [notifId] });
      setData((d) => {
        const notifications = d.notifications.map((n) =>
          n.id === notifId ? { ...n, is_read: true } : n,
        );
        return { notifications, unread_count: countUnread(notifications) };
      });
    } catch {
      /* silent */
    }
  };

  const handleMarkAll = async () => {
    const locked = (data.notifications || []).filter((n) => n._locked);
    const dismissable = (data.notifications || []).filter((n) => !n._locked);
    const dismissIds = dismissable.map((n) => n.id);

    setDismissedIds((s) => new Set([...s, ...dismissIds, ...CYBERSAFE_NOTIFICATION_IDS]));
    setCyberSafeSuppressed(true);
    try {
      sessionStorage.setItem(MARK_ALL_SESSION_KEY(userId), "1");
    } catch {
      /* ignore */
    }

    try {
      await markNotificationsRead(userId, { mark_all: true });
    } catch {
      /* silent */
    }

    setData({
      notifications: locked,
      unread_count: countUnread(locked),
    });
    if (locked.length === 0) setOpen(false);
  };

  const unread = data.unread_count ?? 0;
  const notifs = data.notifications || [];
  const badgeLabel = unread > 9 ? "9+" : String(unread);

  return (
    <div className="relative" ref={panelRef}>
      <button
        type="button"
        onClick={() => {
          setOpen((o) => !o);
          if (!open) load();
        }}
        className="relative flex h-9 w-9 items-center justify-center rounded-full border border-white/10 bg-white/[0.05] text-exiqo-glow/80 transition hover:bg-white/[0.10] hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/60"
        aria-label={`Notifications (${unread} unread)`}
      >
        {unread > 0 ? <BellRing className="h-4.5 w-4.5" aria-hidden /> : <Bell className="h-4.5 w-4.5" aria-hidden />}
        <span
          className={`absolute -right-0.5 -top-0.5 flex h-4 min-w-[1rem] items-center justify-center rounded-full px-0.5 text-[10px] font-bold tabular-nums ${
            unread > 0 ? "bg-rose-500 text-white" : "border border-white/20 bg-white/10 text-gray-400"
          }`}
        >
          {badgeLabel}
        </span>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            key="notif-panel"
            initial={{ opacity: 0, y: -8, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.96 }}
            transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
            className="absolute right-0 top-11 z-50 w-80 rounded-2xl border border-white/[0.10] bg-[#0f1117] p-3 backdrop-blur-xl sm:w-96"
          >
            <div className="mb-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <BellRing className="h-4 w-4 text-exiqo-glow/60" aria-hidden />
                <span className="text-sm font-semibold text-white">Notifications</span>
                <span
                  className={`rounded-full px-2 py-0.5 text-[10px] font-bold tabular-nums ${
                    unread > 0 ? "bg-rose-500/20 text-rose-300" : "bg-white/10 text-gray-500"
                  }`}
                >
                  {unread} new
                </span>
              </div>
              {notifs.length > 0 && unread > 0 && (
                <button
                  type="button"
                  onClick={() => void handleMarkAll()}
                  className="text-[11px] text-gray-500 underline transition hover:text-white"
                >
                  Mark all read
                </button>
              )}
            </div>

            <div className="max-h-[380px] space-y-2 overflow-y-auto">
              {loading && notifs.length === 0 && (
                <div className="space-y-2">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="h-16 animate-pulse rounded-xl bg-white/[0.04]" />
                  ))}
                </div>
              )}
              {!loading && notifs.length === 0 && (
                <div className="py-8 text-center text-sm text-gray-500">
                  <Bell className="mx-auto mb-2 h-8 w-8 opacity-30" aria-hidden />
                  No notifications yet
                </div>
              )}
              {notifs.map((n) => (
                <NotifItem
                  key={n.id}
                  n={n}
                  userId={subscriptionUserId ?? userId}
                  onMarkRead={handleMarkRead}
                  onReminderResolved={handleReminderResolved}
                  onOpenReminders={handleOpenReminders}
                />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
