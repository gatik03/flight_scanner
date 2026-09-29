# Design — Visual System & UI Rules

| | |
|---|---|
| **Version** | 1.0 · 2026-09-29 |
| **Applies to** | Phase 10 frontend (React + Vite + TypeScript + Tailwind). Nothing here blocks backend phases. |
| **Priority** | Legibility of *money, time, and trust* over decoration. The UI is a thin, honest window onto the backend. |

---

## 1. Scope and brief

- **Subject:** a flight fare comparison that shows what *you* will actually pay after your card offers, then sends you to book.
- **Primary audience:** an Indian traveler holding 2+ cards, comparing DEL → BOM-style domestic and short international routes; secondary audience: the developer demoing it live.
- **Primary job of the UI:** let someone scan ranked fares in seconds, understand the arithmetic (`fare − card offer = you pay`) without doing math, know how fresh the data is, and click through to book.
- **Tone:** plain, precise, calm. No hype, no urgency tricks ("only 2 seats left!"). Trust is the product.
- **Not designing:** a booking flow, seat maps, payment forms. We never show a card-number field.

## 2. Concept — "the honest ledger"

Fares are money and time. The design borrows from two things travelers already trust: **the printed boarding pass** (a stub you tear off) and **a receipt** (line items that add up).

**The one memorable element:** each result row ends in a *fare ledger stub*, separated from the itinerary by a perforation (a dashed divider with two half-circle notches). The stub reads like a receipt:

```
Fare                 ₹7,200        (struck through when a card offer applies)
HDFC Regalia         −₹750
You pay              ₹6,450        ← the largest, boldest number in the row
```

Everything else stays quiet so this stub carries the identity. **Spend boldness in one place.**

**Guiding principles**
1. **Show the arithmetic.** The user never mentally subtracts. (The server supplies every number; the client only formats.)
2. **Freshness is part of the price.** Age and source status are always visible, never hidden in a tooltip.
3. **Assumptions are visible and short.** "Assumes booking on the airline's site."
4. **Structure encodes information.** Dividers, borders, and order exist because they mean something (ranked order, perforation = "your price"), not to decorate.
5. **Quiet everywhere else.** One accent for action, one color meaning "savings," one meaning "caution."

## 3. Color

Named tokens. Light theme is the default; dark theme redefines the same names. Contrast ratios below are hand-computed approximations for the light theme — **verify all pairs with a contrast checker in Phase 10** and record results.

### 3.1 Base palette (light)
| Token | Name | Hex | Role |
|---|---|---|---|
| `--ink` | Ink Navy | `#14213D` | Primary text, headings |
| `--slate` | Slate | `#5B6B82` | Secondary text, labels (≈ 5:1 on mist) |
| `--mist` | Mist | `#F2F5F9` | Page background |
| `--surface` | Paper | `#FFFFFF` | Result list, forms, popovers |
| `--line` | Rule | `#D5DDE8` | Dividers, input borders, perforation |
| `--cobalt` | Cobalt | `#2F4BD0` | Primary actions, links, focus ring (≈ 6.3:1 on mist; white on cobalt ≈ 6.9:1) |
| `--jade` | Jade | `#0E7C66` | Savings, "You pay" numeral, success (large text/icons; ≈ 4.7:1 on mist) |
| `--jade-strong` | Deep Jade | `#0A6A57` | Small text on jade tint (≈ 5.7:1) |
| `--jade-tint` | Jade Tint | `#E3F3EE` | Background of savings chip |
| `--marigold` | Marigold | `#E8A317` | Caution/stale/partial **as a background or border only** (text on it: Ink ≈ 7.4:1). Never as text on light backgrounds (≈ 2:1). |
| `--marigold-tint` | Marigold Tint | `#FDF3D9` | Banner background |
| `--signal-red` | Signal Red | `#C43D3D` | Errors (≈ 4.7:1 on mist) |

### 3.2 Dark theme (redefine, don't invent new names)
| Token | Hex |
|---|---|
| `--ink` (text) | `#E6ECF5` |
| `--slate` | `#9DB0CB` (≈ 7.9:1 on `--mist`) |
| `--mist` (page bg) | `#0F1A2E` |
| `--surface` | `#16233B` |
| `--line` | `#2A3A57` |
| `--cobalt` | `#8FA3FF` |
| `--jade` / `--jade-strong` | `#3DCFA8` / `#7FE0C4` |
| `--jade-tint` | `#12332F` |
| `--marigold` | `#F0B429` · tint `#3A2E10` |
| `--signal-red` | `#FF8B85` |

### 3.3 Usage rules
- **Semantic, not decorative:** jade = money saved / you pay; marigold = "be careful" (stale, partial); red = failure; cobalt = something you can do.
- **Never color alone.** Every status pairs color with an icon **and** words (colorblind-safe).
- No gradients as decoration. No colored shadows.
- Text on tinted backgrounds uses the `-strong` variants.
- Background is Mist (cool light grey-blue), not cream or pure white; surfaces are white.

## 4. Typography

Two families with distinct jobs.

| Role | Family | Weights | Used for |
|---|---|---|---|
| **Signage sans** | **IBM Plex Sans** | 400, 500, 600 | All UI, body, times, labels, buttons, tables — reads like airport signage; excellent tabular numerals. |
| **Ledger serif** | **Source Serif 4** | 600, 700 | Page titles and the **"You pay"** amount only — reads like print on a ticket/receipt. |

Fallback stacks (mandatory; fonts can fail or lack glyphs):
```css
--font-sans:  "IBM Plex Sans", system-ui, "Segoe UI", "Noto Sans", sans-serif;
--font-serif: "Source Serif 4", "Iowan Old Style", Georgia, "Noto Serif", serif;
```

**Phase 10 verification task (do not skip):** render `₹1,23,456.50` and `06:05 → 08:20` in both families at all used weights. Confirm the **rupee sign (₹) glyph exists** and `font-variant-numeric: tabular-nums lining-nums` works. If the serif lacks `₹`, apply the sans `₹` via a `unicode-range` `@font-face` or fallback order. Record the result in `learning.md`. (Selected as a starting point; verified availability is not assumed.)

### Type scale (ratio 1.25, base 16 px)
| Token | Size / line-height | Family · weight | Use |
|---|---|---|---|
| `--text-xs` | 12.8 px / 1.4 | Sans 500 | Meta text, timestamps (never below 12 px) |
| `--text-sm` | 14 px / 1.45 | Sans 400/500 | Secondary info, table cells |
| `--text-base` | 16 px / 1.5 | Sans 400 | Body |
| `--text-lg` | 20 px / 1.35 | Sans 600 | Times (departure/arrival), row headings |
| `--text-xl` | 25 px / 1.25 | Serif 600 | Section titles |
| `--text-2xl` | 31 px / 1.2 | Serif 700 | Page title |
| `--text-price` | 31–39 px / 1.1 | **Serif 700** | The "You pay" amount |

Rules
- Body line length ≤ **70 characters** (`max-width: 70ch` on prose).
- Sentence case everywhere. **No ALL-CAPS labels**, no tracked-out eyebrows.
- All numerals in data are **tabular and lining**: `font-variant-numeric: tabular-nums lining-nums;`
- Letter-spacing 0 for body; −0.01 em only on the serif price/title.
- Do not emphasize a single word in a headline with color/italics.

## 5. Layout, spacing, shape

- **Spacing scale (4 px base):** 4 · 8 · 12 · 16 · 24 · 32 · 48 · 64.
- **Breakpoints:** 360 (min supported) · 640 · 960 · 1200. Content max-width 1040 px, centered; page gutters 16 px (mobile) / 24 px (desktop).
- **Alignment:** left-aligned text and data. Numbers in the ledger are **right-aligned** to a shared edge. Nothing center-aligned except empty states.
- **Shape hierarchy (deliberately unequal):**
  - Result list container: `radius 8px`, 1 px `--line` border, **no shadow**.
  - Inputs and buttons: `radius 6px`.
  - Chips/badges: fully rounded (pill).
  - Ledger stub: square outer corners + two 10 px notches.
  - Only popovers and dialogs get elevation (`0 8px 24px rgb(20 33 61 / 0.16)`).
- **Results are a single ruled list, not a grid of separate cards.** Rows are separated by 1 px `--line` dividers.

## 6. Wireframes (ASCII)

### 6.1 Desktop — search results
```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Flight Deal Aggregator                                    [ Cards ] [ Watches ]│
├──────────────────────────────────────────────────────────────────────────────┤
│  From [ Delhi (DEL) ]  To [ Mumbai (BOM) ]  On [ 15 Oct 2026 ]  [ 1 adult ▾ ] │
│  [ Economy ▾ ]                                              [  Search flights ]│
├──────────────────────────────────────────────────────────────────────────────┤
│  ⚠ 2 of 3 sources responded. Results may be incomplete.   Checked 42 s ago   │
│  Sorted by: [ You pay, lowest first ▾ ]        Sources: A ✓  B ✓  C ⏱ timed out│
├──────────────────────────────────────────────────────────────────────────────┤
│  06:05  DEL ──────────── 2h 15m ──────────── 08:20  BOM ┊  ₹7,200  (struck)  │
│  Air India AI 887          Non-stop                    ◖┊  HDFC Regalia −₹750│
│                                                         ┊  You pay    ₹6,450 │
│                                                         ┊  [ Book on Air India ]│
│ ─────────────────────────────────────────────────────── ┊ ───────────────────│
│  07:30  DEL ──────────── 2h 10m ──────────── 09:40  BOM ┊  ₹6,800            │
│  IndiGo 6E 2041            Non-stop                     ┊  No card offer applies│
│                                                         ┊  You pay    ₹6,800 │
│                                                         ┊  [ Book on IndiGo ] │
├──────────────────────────────────────────────────────────────────────────────┤
│ Prices are cached and may differ on the airline's site. Offers verified 27 Sep.│
└──────────────────────────────────────────────────────────────────────────────┘
        (┊ = perforation: dashed line with notches at top and bottom)
```

### 6.2 Mobile (360 px) — row
```
┌────────────────────────────────┐
│ 06:05  DEL ─── 2h 15m ─── 08:20 BOM │
│ Air India AI 887               │   ← meta on separate lines,
│ Non-stop                       │     not dot-joined strings
├╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌┤   ← perforation turns horizontal
│ Fare                    ₹7,200 │
│ HDFC Regalia             −₹750 │
│ You pay                 ₹6,450 │
│ [        Book on Air India    ]│   ← full-width, ≥ 44 px tall
└────────────────────────────────┘
```
(On mobile, render the meta as two short lines — airline/flight number, then stops — not a dot-separated string.)

### 6.3 Cards page
```
Your cards
We never ask for card numbers. Add only the card's bank, network, and type.

 HDFC Regalia, Visa credit card                                   [ Remove ]
 ICICI Amazon Pay, Visa credit card                               [ Remove ]

 Add a card
 Bank [ HDFC ▾ ]  Card name [ Regalia ]  Network [ Visa ▾ ]  Type [ Credit ▾ ]
                                                            [ Save card ]
```

### 6.4 Watch detail
```
Delhi to Mumbai, 15 Oct 2026, 1 adult                          Target ₹6,000
 ₹8,000 ┤                        ╭╮
        │    ╭──╮      ╭─╮     ╭╯╰╮
 ₹6,500 ┤────╯  ╰──────╯ ╰─────╯   ╰──● lowest so far ₹6,120
 target ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄  (dashed line, labeled)
        Sep 15        Sep 22        Sep 29
 Last checked 4 hours ago          [ Stop watching ]
```

## 7. Components

Components render **API fields**; they never compute money.

| Component | Data source (API field) | Notes |
|---|---|---|
| `SearchBar` | request model | Airport inputs accept IATA or city; validation messages inline. Submit disabled while loading. |
| `FreshnessBadge` | `metadata.oldest_data_at` | "Checked 42 seconds ago" → "9 minutes ago" → absolute time after 30 min. Marigold tint + "Refreshing" when any provider `origin=cache_stale`. |
| `ProviderStatusStrip` | `metadata.providers` | One item per source: icon + name + word ("responded", "timed out", "unavailable", "showing older prices"). Always visible when any source ≠ OK. |
| `ResultRow` | `results[]` | Two zones: **Itinerary** (left) and **FareLedger** (right stub). |
| `Itinerary` | `departure`, `arrival`, `duration_minutes`, `stops`, `airline`, `flight_numbers` | Times use airport-local; show `+1` if arrival date differs. Route line is an SVG track; stops sit as small ticks on it with airport codes. |
| `FareLedger` | `list_price`, `discount`, `effective_price`, `applied_offer` | List price struck through only when `discount > 0`. Offer name is a button opening `OfferPopover`. "You pay" is the serif price. |
| `OfferPopover` | `applied_offer`, `considered_offers`, `assumptions` | Explains: which card, why it applies, offer source link, **verified date**, `terms_note`, assumptions. Also lists other eligible offers considered. |
| `BookButton` | handoff | Cobalt filled. Label: "Book on {channel}". External-link icon (SVG, `aria-hidden`). Opens the tab synchronously (see §14). |
| `SortSelect` | `metadata.ranking` | Reflects the API's echoed rule; option labels in plain language. |
| `CardForm` / `CardList` | payment-methods API | Static reassurance text above the form. **No free-text field that could take a card number** (nickname field, if any, rejects long digit runs client-side too). |
| `WatchRow` / `PriceHistoryChart` | watch API | Chart: line = lowest list price; dashed line = target (labeled, not color-only); marker on latest. |
| `StateMessage` | (varies) | Empty, error, rate-limited — see §8. |
| `Toast` | (actions) | Confirms actions using the action's own verb ("Card saved"). |

**Buttons:** primary (cobalt fill, white text), secondary (surface fill, `--line` border, ink text), destructive text-button in red with confirmation. Min height 44 px. Visible focus ring: 2 px cobalt with 2 px offset.

**Inputs:** label always visible above the field (no placeholder-as-label). Error text below, red with icon, referencing how to fix.

## 8. Response states (every one must be reachable in Phase 10)

| State | Trigger | UI |
|---|---|---|
| **Idle** | Before first search | Search bar only + one-line hint of what results will show. |
| **Loading (cold)** | Awaiting `/search` | Route strip locked in; skeleton rows (3); status line "Checking prices… 3 s" with elapsed time. Announced politely to screen readers. |
| **Fresh** | All sources OK, data < TTL | Results + "Checked N seconds ago". |
| **Stale, refreshing** | `origin: cache_stale` present | Marigold banner: "Some prices are from {age} ago and are refreshing." Results still usable. |
| **Partial** | `partial_results=true` | Status strip lists the source(s) that failed and why (plain words). "Results may be incomplete." |
| **Empty** | 200 with zero results | "No flights found for Delhi to Mumbai on 15 Oct." + actions: try nearby dates, change cabin. |
| **Offers unavailable** | `offers.available=false` | Small note: "Card offers are unavailable right now, so you see fare prices only." |
| **No cards declared** | Signed in, no methods | Inline prompt in the ledger area: "Add a card to see what you'd pay." |
| **Signed out** | Anonymous | Fare prices only, with "Sign in and add a card to see card offers." |
| **Offer data old** | offer `stale=true` | Offer shows "Last verified {N} days ago" in the popover and a small warning icon. |
| **Rate-limited** | 429 | "Too many searches. Try again in {Retry-After} seconds." Countdown, button re-enables. |
| **All sources failed** | 502/504 | "We couldn't reach any flight source. Your search isn't lost — try again." Per-source reasons in a details toggle. |
| **Expired result on book** | handoff 410 | "These results have expired. Search again to get current prices." |
| **Link refused** | handoff 422 | "We couldn't open a safe booking link for this fare." (No detail about internals.) |
| **Network error** | fetch fails | Distinguish from server error; offer retry. |
| **Price changed** | handoff `price_changed=true` | Before leaving: "The airline now shows ₹X (we showed ₹Y). Continue?" |

## 9. Motion

- **One orchestrated moment:** when results arrive, rows settle into place top-to-bottom in ranked order (opacity + 8 px translate, 40 ms stagger, first 8 rows only, once per search). It communicates *ordering*.
- Everything else moves only **in response to a user action** (opening the offer popover, expanding details, confirming a save), 120–180 ms ease-out, showing what changed.
- No hover animations on every row, no looping shimmer beyond skeleton loading, no page-load fades on sections.
- **`prefers-reduced-motion: reduce`** → no transitions/animations; state changes are instant.

## 10. Voice and microcopy

Plain verbs, sentence case, specific, no filler. Name things the way the traveler thinks.

| Concept (API) | UI wording |
|---|---|
| `effective_price` | **You pay** |
| `list_price` | Fare |
| `applied_offer` | Card offer (name the card: "HDFC Regalia") |
| `partial_results` | "2 of 3 sources responded" |
| `origin: cache_stale` | "Showing prices from 9 minutes ago" |
| provider `TIMEOUT` | "took too long to respond" |
| provider `QUOTA_EXHAUSTED` / `RATE_LIMITED` | "unavailable right now" |
| `assumptions[]` | "Assumes you book on the airline's own site." |

Rules
- Buttons say what happens: **Search flights**, **Save card**, **Book on IndiGo**, **Watch this fare**, **Stop watching**. The same action keeps the same name in its toast ("Card saved").
- Errors never apologize and never blame; they say what happened and what to do next.
- Empty states invite action.
- Disclosure near every Book button, in `--text-sm` slate: "Price may differ on {channel}'s site."
- Never write "live," "guaranteed," "best price," "hurry," or countdowns.
- Don't suffix buttons/links with `→`. The external-link icon is the only affordance for leaving the site.
- Don't join meta with middle dots (`A · B · C`); use separate lines or structured layout.

## 11. Data display rules

- **Money:** API strings only. Format with `Intl.NumberFormat("en-IN", { style: "currency", currency })` (Indian digit grouping: ₹1,23,456). Show `.00` only when non-zero paise exist. **Never add/subtract/compare money in JavaScript** — the server provides `discount` and `effective_price`. Negative amounts (discount) use a true minus `−` and the word "offer" in context.
- **Times:** 24-hour `06:05`, in the **airport's local time**, with the airport code. Add `+1` when arrival is on a later local date. Hover/tap reveals the time zone.
- **Duration:** `2h 15m`. **Stops:** "Non-stop", "1 stop", "2 stops" (with layover airport codes when known).
- **Dates:** `15 Oct 2026` (en-IN) with weekday in the search summary.
- **Age:** relative under 30 minutes; absolute (`10:12`) beyond, with the date if not today.
- **Offer verification:** "Verified 27 Sep 2026". If stale, show the age in days.
- **Source names:** show provider display names; never show internal ids.

## 12. Accessibility (target WCAG 2.2 AA)

- Contrast: text ≥ 4.5:1, large text/icons ≥ 3:1, focus indicators ≥ 3:1. Verify both themes.
- Full keyboard operation; logical tab order (search → sort → each row's offer button → Book); visible focus everywhere; no keyboard traps in popovers/dialogs (Esc closes, focus returns).
- Semantics: results are a list (`<ol>` — order is meaningful); headings in order; labelled form controls; buttons vs links used correctly (Book opens a new context → say so in the accessible name: "Book on IndiGo, opens in a new tab").
- Live regions: loading/result-count/partial-source changes announced with `aria-live="polite"`; errors with `role="alert"`.
- Never rely on color alone (icon + text on every status). Strike-through fare also announced: "Fare ₹7,200, before card offer".
- Touch targets ≥ 44 × 44 px; supports 200 % zoom and 360 px width without horizontal scroll (except charts, which scroll within their own container).
- `prefers-reduced-motion` and `prefers-color-scheme` respected; manual theme toggle via `data-theme`.
- Chart has a table alternative (toggle "View as table").

## 13. Anti-patterns for this project (self-critique checklist)

Reject the design if it contains any of these:
- Identical rounded cards with the same soft shadow for every result.
- Gradient washes, glassmorphism, or decorative blobs.
- A hero section with a big number + gradient accent (the hero **is** the search bar and the first result).
- ALL-CAPS eyebrow labels above headings; "WORD — fragment" labels.
- Monospace for small data labels (use tabular sans numerals instead).
- Urgency/scarcity language, countdowns, fake "deal" badges.
- Color as the only signal for stale/partial/error.
- Any UI element that looks like a payment form or asks for card digits.
- A warm-cream + terracotta look, or a black + acid-accent look (both are generic defaults for this kind of page).

**Before finishing a screen:** take a screenshot at 360 px and 1200 px in light and dark, then remove one decorative element.

## 14. Implementation notes

### 14.1 Tokens as CSS variables
```css
:root {
  --ink:#14213D; --slate:#5B6B82; --mist:#F2F5F9; --surface:#FFFFFF; --line:#D5DDE8;
  --cobalt:#2F4BD0; --jade:#0E7C66; --jade-strong:#0A6A57; --jade-tint:#E3F3EE;
  --marigold:#E8A317; --marigold-tint:#FDF3D9; --signal-red:#C43D3D;

  --font-sans:"IBM Plex Sans", system-ui, "Segoe UI", "Noto Sans", sans-serif;
  --font-serif:"Source Serif 4", "Iowan Old Style", Georgia, "Noto Serif", serif;

  --space-1:4px; --space-2:8px; --space-3:12px; --space-4:16px; --space-6:24px; --space-8:32px;
  --radius-container:8px; --radius-control:6px; --radius-pill:999px;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --ink:#E6ECF5; --slate:#9DB0CB; --mist:#0F1A2E; --surface:#16233B; --line:#2A3A57;
    --cobalt:#8FA3FF; --jade:#3DCFA8; --jade-strong:#7FE0C4; --jade-tint:#12332F;
    --marigold:#F0B429; --marigold-tint:#3A2E10; --signal-red:#FF8B85;
  }
}
:root[data-theme="dark"] { /* same values as the dark block above */ }
body { background:var(--mist); color:var(--ink); font:400 16px/1.5 var(--font-sans);
       font-variant-numeric: tabular-nums lining-nums; }
:focus-visible { outline:2px solid var(--cobalt); outline-offset:2px; }
@media (prefers-reduced-motion: reduce) { * { animation:none !important; transition:none !important; } }
```

### 14.2 Tailwind mapping
Extend `theme.colors` with the token names pointing at `var(--…)` so components use `text-ink`, `bg-surface`, `border-line`, `text-jade-strong`, etc. Don't hard-code hex values in components.

### 14.3 Ledger stub notches (CSS idea)
Draw the perforation as `border-left: 2px dashed var(--line)` on the stub, with two 10 px circles positioned at the top and bottom edge of that border, filled with `var(--mist)` (the page background) so they read as cut-outs in both themes. On narrow screens, rotate to a horizontal dashed rule with notches at the left and right edges.

### 14.4 Handoff click (browser popup rule)
Browsers only allow `window.open` from a direct user gesture. In the Book click handler: **synchronously** open `about:blank` in a new tab (`noopener`), then `await POST /handoff`, then set that tab's location to the returned URL. On failure, close the tab and show the error state. Show `price_changed` confirmation *before* navigating when applicable.

### 14.5 Checks to record in `learning.md` at Phase 10
Font glyph test (`₹`, tabular figures) · contrast results for every token pair in both themes · keyboard walkthrough · 360 px and 200 % zoom screenshots · reduced-motion behavior · screen-reader pass on the results list and offer popover.
