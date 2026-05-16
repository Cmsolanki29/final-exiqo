import React, { useEffect } from "react";
import { PageHeader } from "../../components/Dashboard/shared/PageHeader";
import TripPlannerChat from "../../components/AIActions/TripPlannerChat";

const ACCENT = "#22D3EE";

/**
 * Trip Planner — AI Actions › Trip Planner.
 *
 * Backed by /api/ai-actions/trip-planner/chat which runs an OpenAI
 * function-calling agent against the user's real SmartSpend finances and
 * live providers (weather, flights, hotels, places).
 */
export default function TripPlannerPage() {
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "instant" });
  }, []);

  return (
    <div>
      <PageHeader
        eyebrow="AI ACTIONS · TRIP PLANNER"
        title="Plan trips that fit your money"
        subtitle="An AI travel agent that reads your real savings, EMIs and surplus — then orchestrates live weather, flight and hotel intelligence to recommend dates, hotels and a budget that actually works for you."
        accentHex={ACCENT}
      />

      <TripPlannerChat />
    </div>
  );
}
