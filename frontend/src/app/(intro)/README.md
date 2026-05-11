# SmartSpend Intro Flow

This folder is a **documentation anchor** for the cinematic intro flow that runs before
authentication. The actual implementation lives at:

```
frontend/src/components/intro/
├── AuroraBackground.tsx     # Drifting orbs + starfield, used on every screen
├── GlassCard.tsx            # Glass token (bg-white/5 backdrop-blur-2xl …)
├── GradientButton.tsx       # primary | ghost variants with brand gradient
├── ShieldMark.tsx           # Animated SVG shield (paths, pathLength, fills)
├── RocketTrail.tsx          # Rocket SVG + curving cyan→magenta trail
├── SplashScreen.tsx         # Screen 1 — boot animation (2.6s)
├── IntroStory.tsx           # Screen 2 — three swipeable parallax slides
├── GetStartedScreen.tsx     # Screen 3 — choice screen (Create / Sign in)
├── IntroAuth.tsx            # Screen 4 — tabbed split-screen Sign In / Sign Up
└── IntroFlow.tsx            # Top-level orchestrator + localStorage flag
```

## Flow

```
First-time visitor:
  /splash  ──►  /intro  ──►  /get-started  ──►  /auth/signup  ──►  /dashboard
                                            └►  /auth/signin   ─┘

Returning visitor (smartspend.seenIntro === "true"):
  /auth/signin  ──►  /dashboard
```

The shield logo is the **continuity element** — it morphs from the centered splash
composition all the way through to the navbar logo on every subsequent screen via a
shared Framer Motion `layoutId="ssShieldMark"` and `AnimatePresence`.

## Routing

This project is Create React App (no `react-router-dom`). The flow is implemented as
a tiny **state-based router** inside `IntroFlow.tsx` that mirrors the prompt's URL
structure (`/splash`, `/intro`, `/get-started`, `/auth/signin`, `/auth/signup`)
without adding a new dependency. The orchestrator is mounted from `App.jsx`
whenever the user is not yet authenticated.

If you'd like to migrate to real client-side routing, replace the
`AnimatePresence` switch in `IntroFlow.tsx` with `react-router-dom` `<Routes>`
and route components — the screens themselves are completely route-agnostic.

## localStorage flag

```ts
// Set after the user finishes splash + intro at least once
localStorage.setItem("smartspend.seenIntro", "true");
```

### Resetting the flag

To replay the full splash + intro on the next page load (e.g. for QA or to
demo for judges), run **either** in the browser DevTools console:

```js
window.localStorage.removeItem("smartspend.seenIntro");
location.reload();
```

…or import the constant in code:

```ts
import { SEEN_INTRO_KEY } from "../../components/intro";
window.localStorage.removeItem(SEEN_INTRO_KEY);
```

## Brand tokens

Tailwind has been extended in `frontend/tailwind.config.js`:

| Token            | Value                                                                  |
| ---------------- | ---------------------------------------------------------------------- |
| `ss-bg-deep`     | `#070418`                                                              |
| `ss-bg-rise`     | `#0F0A2E`                                                              |
| `ss-violet`      | `#7C3AED`                                                              |
| `ss-magenta`     | `#EC4899`                                                              |
| `ss-cyan`        | `#22D3EE`                                                              |
| `ss-ink`         | `#F5F3FF`                                                              |
| `ss-mute`        | `#9CA3CF`                                                              |
| `bg-ss-brand`    | `linear-gradient(135deg,#7C3AED 0%,#A855F7 40%,#EC4899 75%,#22D3EE)`   |
| `font-heading`   | `Space Grotesk`                                                        |
| `ease-brand`     | `cubic-bezier(0.22, 1, 0.36, 1)`                                       |
| `shadow-ss-glass`| `0 8px 40px rgba(124,58,237,0.15)`                                     |

Google Fonts (`Inter` + `Space Grotesk`) are loaded once in `frontend/public/index.html`.

## Accessibility notes

- All interactive elements are at least **48×48 px** on mobile.
- Focus rings use `focus-visible:ring-2 ring-cyan-400/60` for keyboard users.
- Headings use `text-[clamp(2rem,6vw,4.5rem)]` (or similar) for fluid sizing.
- `prefers-reduced-motion` is honored everywhere via Framer Motion's
  `useReducedMotion()`: orb drift, parallax, particle bursts, rocket launches and
  starfield twinkle are all disabled — fades and morphs remain.

## Skipping during development

Each screen has a **Skip** affordance:

| Screen        | How to skip                                                  |
| ------------- | ------------------------------------------------------------ |
| Splash        | "Skip" button (top-right) or click anywhere on the surface.  |
| Intro story   | "Skip" pill (top-right) or `Esc` key.                        |
| Get started   | Click "I already have one" to land on `/auth/signin`.        |
| Auth          | Click the "Back" pill to return to get-started.              |
