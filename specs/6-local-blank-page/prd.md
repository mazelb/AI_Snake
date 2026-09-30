---
title: Mount the app when served by Vite locally, without breaking AI Studio
issue: mazelb/AI_Snake#6
owner: mazelb
status: draft
created: 2026-09-30
domain: greenfield
---

# Mount the app when served by Vite locally, without breaking AI Studio

## Problem

`index.html` loads the Tailwind CDN script, an inline Tailwind config and an import
map, and contains an empty `div#root`, but it has no module script tag that
loads `index.tsx`. `index.tsx` is the only code that calls
`ReactDOM.createRoot(...).render(<App />)`. So `npm run dev` (`vite`, port 3000 per
`vite.config.ts`) serves a page where React never mounts, and `npm run build`
(`vite build`) emits a `dist/` containing only `index.html` — the checked-in `dist/`
shows exactly that. No error is shown. The app renders only inside AI Studio.

## Affected users

The owner, and anyone who clones the repo and follows the README's "Run Locally"
steps (`npm install`, set `GEMINI_API_KEY` in `.env.local`, `npm run dev`). Per the
issue there are no tracked user numbers; this is a hobby project.

## Success metric

- Metric: number of the issue's three "how would we know it worked" checks that pass (local dev renders and is playable; build output contains the bundled app; AI Studio still works)
- Current baseline: 1 of 3 — per the issue, only AI Studio renders the app today
- Target: 3 of 3
- Source: the REQ-001–REQ-003 acceptance checks, run by the owner before merge

## Non-goals

- No change to game logic, controls or styling (`App.tsx`, `gameLogic.ts`, `components/`, `constants.ts`).
- Not replacing the Tailwind CDN script (`https://cdn.tailwindcss.com`) or the inline `tailwind.config`.
- Not removing or changing the import map in `index.html`.
- Not changing how Gemini keys are provided (`GEMINI_API_KEY` in `.env.local`, mapped to `process.env.API_KEY` by `vite.config.ts` `define`).
- Not adding deployment or hosting for `dist/`.
- Not deciding whether `dist/` should be committed to the repo.

## Requirements

### REQ-001 [P0] Local dev server mounts the app

With `npm run dev` running, loading the app in a browser mounts React into
`#root` and shows the game.

**Acceptance:** After `npm install` and `npm run dev` on a fresh clone, opening
http://localhost:3000 shows the Neon Snake game UI (the `#root` element has
rendered children); after a game is started, pressing ArrowUp/ArrowDown/ArrowLeft/
ArrowRight (or W/S/A/D) changes the snake's direction. The browser console shows no
uncaught error during load.

### REQ-002 [P0] Production build contains the bundled app

`npm run build` emits the application JavaScript into `dist/`, referenced from
`dist/index.html`.

**Acceptance:** After `npm run build`, `dist/` contains at least one `.js` file,
and `dist/index.html` contains a module script tag (`type="module"`) whose `src`
points at one of them. Running `npm run preview` and opening the URL it prints shows the same
game UI as REQ-001.

### REQ-003 [P0] AI Studio keeps loading the app exactly once

The change to `index.html` must not stop the app from rendering in AI Studio, and
must not cause it to be loaded or mounted twice there.

**Acceptance:** Opening the app in AI Studio (https://ai.studio/apps/drive/1LTZzAdPYJIr-9uZ2zMl5R71N3liQINZl)
after the change shows exactly one game board, the keyboard controls from REQ-001
work, and the browser console shows no uncaught error. [NEEDS INPUT: how to
observe a double load in AI Studio — e.g. whether AI Studio's own entry for
`index.tsx` appears as a second request/script in DevTools — owner (mazelb), by
trying it in AI Studio]

## Constraints

- Must keep working in AI Studio, where the app was generated and is shared from (source: issue #6; README links the AI Studio app).
- How AI Studio loads the app — whether it injects its own entry for `index.tsx` — is unknown, so a plain module script tag with `src="/index.tsx"` may load the app twice there (source: issue #6).
- No new runtime dependencies (source: issue #6); runtime deps stay `react`, `react-dom`, `@google/genai` (source: `package.json`).
- Stay on Vite 6 with `@vitejs/plugin-react` and the existing `vite.config.ts` port 3000 (source: `package.json`, `vite.config.ts`).
- `npx tsc --noEmit` must keep passing (source: `flow.json` `typecheck`).

## Evidence

## Open questions

| Question | Owner | Blocks |
|---|---|---|
| Does AI Studio inject its own script tag for `index.tsx`, or rely on the one in `index.html`? A branch with the script tag added, opened in AI Studio, answers this — recommend a prototype. | mazelb | REQ-003 |
| If AI Studio does inject its own entry, is a guard against double-mounting (e.g. in `index.tsx`) acceptable, given the non-goal of no game-logic change? | mazelb | REQ-003, plan |
| Can a branch build be previewed in AI Studio before merge, or does it only load from `main`/Drive? | mazelb | REQ-003 |
| Should the README's "Run Locally" steps change at all, or stay as-is once they work? | mazelb | plan |
