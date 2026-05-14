/** Canonical list for connect / add-more modals (ids stable for localStorage). */
export const ALL_SUBSCRIPTION_APPS = [
  { id: "youtube", label: "YouTube", emoji: "▶️" },
  { id: "spotify", label: "Spotify", emoji: "🎵" },
  { id: "netflix", label: "Netflix", emoji: "🎬" },
  { id: "amazon_prime", label: "Amazon Prime", emoji: "📦" },
  { id: "hotstar", label: "Hotstar", emoji: "📺" },
  { id: "canva", label: "Canva", emoji: "🎨" },
  { id: "chatgpt", label: "ChatGPT", emoji: "🤖" },
  { id: "linkedin", label: "LinkedIn Premium", emoji: "💼" },
  { id: "adobe", label: "Adobe", emoji: "✨" },
  { id: "notion", label: "Notion", emoji: "📝" },
  { id: "perplexity", label: "Perplexity", emoji: "🔮" },
  { id: "figma", label: "Figma", emoji: "🧩" },
  { id: "chatgpt_plus", label: "ChatGPT Plus", emoji: "⚡" },
];

/** First connect screen — matches product spec (10 apps). */
export const INITIAL_CONNECT_APP_IDS = ALL_SUBSCRIPTION_APPS.slice(0, 10).map((a) => a.id);

export function appById(id) {
  return ALL_SUBSCRIPTION_APPS.find((a) => a.id === id);
}

export function labelsForIds(ids) {
  return (ids || []).map((id) => appById(id)?.label || id).filter(Boolean);
}

/** Apps user can add that are not already connected. */
export function getAddableAppIds(connectedIds) {
  const set = new Set(connectedIds || []);
  return ALL_SUBSCRIPTION_APPS.filter((a) => !set.has(a.id)).map((a) => a.id);
}
