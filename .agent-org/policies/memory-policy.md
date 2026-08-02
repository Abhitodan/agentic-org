# Memory Policy

- Feature brain first: agents retrieve from the feature brain before the
  project brain, and from the project brain before the portfolio brain.
- No automatic cross-project reads. Portfolio slices require explicit
  authorization recorded as an event.
- Brains are updated after every accepted change (definition of done).
- Hidden agent memory is never a source of truth; anything load-bearing is
  persisted to the brain, the database, or git.
