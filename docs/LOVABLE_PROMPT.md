# Building the IncCorpAI frontend in Lovable

The repo already ships a working reference frontend (`frontend/`) in Lovable's own stack:
Vite + React 18 + TypeScript + Tailwind + lucide-react. You have two routes.

## Route A — import the existing frontend (recommended)

1. Push this repo to GitHub, or push just `frontend/` as its own repo.
2. In Lovable, connect GitHub and open the repo. Lovable will edit the existing components,
   so the SSE parsing, citation handling, checklist state and filters keep working while
   you iterate on the look.
3. In Lovable project settings, set the environment variable
   `VITE_API_BASE_URL=https://<your-deployed-api>` and add that origin to the backend's
   `CORS_ORIGINS`.
4. Restyle by changing the CSS variables in `src/index.css` and the components in
   `src/components/`. Keep `src/lib/api.ts`, `src/lib/types.ts` and `src/hooks/` as they are.

## Route B — generate a fresh UI

Copy `frontend/src/lib/types.ts`, `frontend/src/lib/api.ts` and `frontend/src/hooks/` into
the new Lovable project first, then paste the prompt below.

---

### Prompt to paste into Lovable

> Build the web app for **IncCorpAI**, an assistant that answers startup incorporation and
> compliance questions for India (MCA, SPICe+, DPIIT, DPDP Act), Delaware C-Corps, and EU
> GDPR. Every answer is grounded only in indexed regulations and cites the exact clause.
> Users are founders preparing filings. They come back over days to tick off steps.
>
> **Stack:** React + TypeScript + Tailwind + shadcn/ui + lucide-react. Use the files already
> in `src/lib/api.ts`, `src/lib/types.ts` and `src/hooks/` for all data access. Do not
> write a new SSE parser. `streamChat()` in `api.ts` calls `POST /api/chat` and emits typed
> `ChatEvent`s; `useConversations()` turns them into message state and persists history;
> `useChecklist(key)` persists ticked steps.
>
> **Backend:** base URL from `import.meta.env.VITE_API_BASE_URL`. Endpoints:
> `GET /api/taxonomy` (jurisdictions, entity types per jurisdiction, phases, suggested prompts),
> `GET /api/health` (document and clause counts, `offline` flag),
> `POST /api/chat` (SSE events in order: `filters`, `status`, `sources`, `token`…, `widget`, `done` or `error`).
> Never hard-code jurisdictions or entity types; read them from `/api/taxonomy`.
>
> **Layout (desktop):** three columns.
> 1. Left rail "case file": logo, New button, jurisdiction picker (one row per jurisdiction
>    with its code, name and summary), entity-type picker that only shows types for the
>    selected jurisdiction, an optional stage select ("Every stage" + phases), then the list
>    of previous questions with delete, and a footer with indexed document/clause counts.
>    Show "Offline mode: add an Anthropic API key for written answers" when `health.offline`.
> 2. Centre conversation: empty state with the headline "What are you filing in {place}?",
>    one sentence explaining answers come only from the N indexed documents, and the
>    jurisdiction's `suggested_prompts` as a clickable list. Messages: the user's question
>    as a heading; the assistant answer as markdown (GFM tables) in a serif face. Composer at
>    the bottom: auto-growing textarea, Enter sends, Shift+Enter newline, an "Ask" button that
>    becomes "Stop" while streaming, and a hint "Answers use {jurisdiction}, {entity} sources only".
> 3. Right "dossier" panel with tabs **Checklist** and **Sources**.
>
> **Answer rendering rules**
> - While `stage` is retrieving/reranking/generating with no text yet, show a three-step
>   progress row: Searching regulations, Ranking clauses, Drafting answer.
> - Replace `[n]` in the answer with a small citation button when `1 ≤ n ≤ sources.length`.
>   Clicking it opens the Sources tab, scrolls to source n and highlights it.
> - If `filters.note` is present, show it above the answer as an amber notice.
> - If `done.rejected` is true, render the text as a calm "Not covered by the indexed
>   regulations" card, not as an answer.
> - On `error`, show the message with a retry hint.
> - Under finished answers, show "{n} sources, {latency}s, {model}" in small muted text.
>
> **Checklist widget** (from the `widget` event, `template === "checklist"`): title, "x of y
> steps filed", a progress bar, items grouped by `categories` in order, each a numbered
> checkbox row with label, sublines, and "Source n" buttons from `source_refs`. Ticking an
> item stamps it with a circular violet rubber stamp reading "FILED" and the date, with a
> short press-in animation (respect `prefers-reduced-motion`). State persists per message id
> via `useChecklist`. Show the latest checklist in the Checklist tab; on smaller screens also
> show it inline under the answer.
>
> **Source card:** index badge, clause id (or section path), document title, regulator and
> phase tags; expands to show the full clause markdown and an "Open official source" link.
>
> **Visual direction:** calm, official, trustworthy, like a well-kept company register, not
> a generic AI chat. Cool ledger-paper background `#F4F6F5`, white sheets, navy ink text
> `#14213D`, hairline rules `#D6DEDB`, registry green `#0E6B5C` for primary actions and the
> selected jurisdiction, rubber-stamp violet `#4B3FA8` only for citations, progress and filed
> steps, amber `#B54708` only for notices. Public Sans for UI, Source Serif 4 for answer
> text. Sentence-case labels, no all-caps eyebrows, no gradients, modest radii (6px controls,
> 10px panels). Visible keyboard focus everywhere.
>
> **Responsive:** below 1024px the left rail becomes a drawer opened from a top bar showing
> "{jurisdiction}, {entity}"; below 1280px the dossier becomes a right drawer opened from a
> "Dossier" button. Citation clicks open the drawer.
>
> **Copy:** plain and direct. Footer under the composer: "Grounded in indexed regulations,
> not legal advice. Confirm fees and deadlines on the official portal."
