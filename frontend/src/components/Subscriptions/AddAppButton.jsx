import React, { useState } from "react";
import { Plus } from "lucide-react";
import AppSelectionModal from "./AppSelectionModal";
import PermissionModal from "./PermissionModal";
import { mergeSubscriptionApps } from "../../utils/subscriptionFlowStorage";
import { syncLinkedAppsToBackend } from "../../services/subscriptionDeviceSync";
import { useToast } from "../common/Toast";

/**
 * @param {object} props
 * @param {number} props.ownerId
 * @param {string[]} props.connectedIds
 * @param {"default"|"small"} props.variant
 * @param {() => void} [props.onAppsUpdated]
 */
export default function AddAppButton({ ownerId, connectedIds, variant = "default", onAppsUpdated }) {
  const { showToast } = useToast();
  const [showPick, setShowPick] = useState(false);
  const [showPerm, setShowPerm] = useState(false);
  const [pending, setPending] = useState([]);

  const small = variant === "small";

  const afterAllow = async () => {
    if (!ownerId) {
      showToast("You must be signed in to add apps.", "error");
      return;
    }
    mergeSubscriptionApps(ownerId, pending);
    setShowPerm(false);
    setPending([]);
    try {
      await syncLinkedAppsToBackend(ownerId);
      showToast("Apps updated — syncing workspace…", "success");
    } catch (e) {
      showToast(e?.message || "Could not sync new apps to the server.", "error");
    }
    onAppsUpdated?.();
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setShowPick(true)}
        className={`inline-flex items-center justify-center gap-2 rounded-xl border border-cyan-400/35 bg-cyan-500/15 font-semibold text-cyan-200 transition hover:bg-cyan-500/25 ${
          small ? "px-3 py-2 text-xs" : "px-4 py-2.5 text-sm"
        }`}
      >
        <Plus className={small ? "h-3.5 w-3.5" : "h-4 w-4"} aria-hidden />
        Add apps
      </button>

      <AppSelectionModal
        open={showPick}
        variant="add"
        connectedIds={connectedIds}
        onClose={() => setShowPick(false)}
        onConfirm={(ids) => {
          setPending(ids);
          setShowPick(false);
          setShowPerm(true);
        }}
      />

      <PermissionModal
        open={showPerm}
        appIds={pending}
        onDeny={() => {
          setShowPerm(false);
          setPending([]);
        }}
        onAllow={() => {
          void afterAllow();
        }}
      />
    </>
  );
}
