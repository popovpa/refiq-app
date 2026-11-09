# RefIQ UI Kit 1.1 — Navy Navigation

## Decision

From the supplied reference adopt **only** the dark navy left navigation and its bright blue active state. Preserve the light workspace and existing UI components from v1.0. Reference content, partner logos and sample metrics are not design requirements.

### Navigation design tokens

| Token | Value | Purpose |
|---|---|---|
| `--nav-bg` | `#172F4B` | Sidebar top |
| `--nav-bg-bottom` | `#244360` | Subtle sidebar depth |
| `--nav-active` | `#2C73DA` | Active sidebar item only |
| `--nav-text` | `#B6C9DE` | Sidebar text |
| `--nav-text-bright` | `#F6FAFF` | Active and high-emphasis text |
| `--color-primary` | `#586AD9` | Primary actions, as in v1.0 |
| `--color-canvas` | `#F7F9FC` | Workspace background, as in v1.0 |

The menu uses 242px expanded, 76px collapsed. On mobile, it opens as an off-canvas drawer. The UI includes an interactive dark/light sidebar comparison switch, an icon-collapse toggle, and the v1.0 interactions.

## Files

- `refiq-ui-kit-v1.1.html`: standalone interactive prototype, open directly in a browser.
- `refiq-ui-v1.1.css`: full component stylesheet including v1.0 rules and navigation additions.
- `refiq-tokens-v1.1.json`: platform style and semantics including role and Betting constraints.
- `refiq-tokens-v1.1.css`: foundation + navigation CSS variables.

## Implementation guidance for Cursor

1. Introduce navigation CSS variables and apply only to `Sidebar`, `NavItem`, `Brand` and `AccountSwitcher`. Avoid global color replacements.
2. Preserve all API calls, routes, permissions, role distinctions, conversions and finance semantics.
3. Keep desktop sidebar expanded by default. Support collapsed 76px state with tooltip labels, keyboard focus and active indicator.
4. On mobile, use an off-canvas drawer with close button, backdrop, focus management and scroll lock. The prototype shows an example, but production accessibility needs refinement.
5. Maintain `OPEN` prohibition for restricted Betting offers; do not publish gambling offers. The sample offers in prototype are illustrative and not third-party brand endorsements.
6. Validate visual screenshots at desktop 1440, tablet 768 and mobile 390 widths; test contrast and interactions.

## Contrast in UI

Avoid using the dark sidebar palette in charts, forms, tables or modals: navy is a **structural layer**, not a universal dark theme. Keep semantic green/orange/red states for their intended meaning.
