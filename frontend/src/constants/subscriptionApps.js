/**
 * Canonical list for connect / add-more modals (ids stable for localStorage).
 *
 * logo.slug + logo.color → Simple Icons CDN: https://cdn.simpleicons.org/{slug}/{hex}
 * emoji                  → shown inside the tile when the CDN image fails to load
 *
 * Notion uses white (#FFFFFF) so its black-on-transparent logo is visible on dark bg.
 */
export const ALL_SUBSCRIPTION_APPS = [
  { id: "youtube",      label: "YouTube",          emoji: "▶️",  logo: { slug: "youtube",    color: "FF0000" } },
  { id: "spotify",      label: "Spotify",          emoji: "🎵",  logo: { slug: "spotify",    color: "1DB954" } },
  { id: "netflix",      label: "Netflix",          emoji: "🎬",  logo: { slug: "netflix",    color: "E50914" } },
  { id: "amazon_prime", label: "Amazon Prime",     emoji: "📦",  logo: { slug: "primevideo", color: "00A8E1" } },
  { id: "hotstar",      label: "Hotstar",          emoji: "📺",  logo: { slug: "hotstar",    color: "1F80E0" } },
  { id: "canva",        label: "Canva",            emoji: "🎨",  logo: { slug: "canva",      color: "00C4CC" } },
  { id: "chatgpt",      label: "ChatGPT",          emoji: "🤖",  logo: { slug: "openai",     color: "10A37F" } },
  { id: "linkedin",     label: "LinkedIn Premium", emoji: "💼",  logo: { slug: "linkedin",   color: "0A66C2" } },
  { id: "adobe",        label: "Adobe",            emoji: "✨",  logo: { slug: "adobe",      color: "FF0000" } },
  { id: "notion",       label: "Notion",           emoji: "📝",  logo: { slug: "notion",     color: "FFFFFF" } },
  { id: "perplexity",   label: "Perplexity",       emoji: "🔮",  logo: { slug: "perplexity", color: "20B2AA" } },
  { id: "figma",        label: "Figma",            emoji: "🧩",  logo: { slug: "figma",      color: "F24E1E" } },
  { id: "chatgpt_plus", label: "ChatGPT Plus",     emoji: "⚡",  logo: { slug: "openai",     color: "10A37F" } },
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
