Read AGENTS.md and docs/SPEC.md (the sections relevant to this stage).
Build the design system (tokens, typography, Button, Input, Card, Nav, Footer,
mobile menu, motion primitives) and these public pages:
/, /explore, /categories, /categories/[slug], /experiences/[slug],
/companions/[slug], /about, /safety, /help, /terms, /privacy.
Homepage headline: "Make plans worth remembering." with a working search
widget (category, city, date, budget) that navigates to /explore with query
params. Use sample data served from the backend (fixtures or seed command),
not hardcoded arrays in components. Use local placeholder images with alt text.

Done when: pages render responsively on mobile and desktop, search navigates
with filters in the URL, loading/empty/error states exist, lint and type-check
pass. Commit.
