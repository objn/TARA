# Frontend guidance

## Tara frontend navigation concept

- The `tara-frontend` application uses a top bar for its primary sections.
- Each top-bar section owns its own side bar and side-bar navigation items.
- When the selected top-bar section has no side-bar navigation, render an empty side-bar area rather than reusing another section's menu or removing the side bar.
- Keep the active top-bar section and its side-bar content in sync when navigating.

### Overview section

- The Overview top-bar section has these side-bar items, in this order: `Dashboard`, `TARA Activity`, and `Service Health`.

Apply this concept to future frontend implementation and design work in `stack/tara-frontend`.
