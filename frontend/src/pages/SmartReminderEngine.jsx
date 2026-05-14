import React from "react";
import SmartReminders from "./SmartReminders";

/** Feature B — dedicated smart reminder / renewal surface (wraps existing implementation). */
export default function SmartReminderEngine(props) {
  return <SmartReminders {...props} />;
}
