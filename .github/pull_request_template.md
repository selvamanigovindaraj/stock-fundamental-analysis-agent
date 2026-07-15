## Verification

- [ ] I inspected all unresolved review threads, not only top-level conversation comments.
- [ ] I tested external payloads with missing, malformed, duplicated, and out-of-order data.
- [ ] No database connection, lock, or transaction is held across network/vendor I/O.
- [ ] Cache/database writes are atomic and idempotent, with stale/failure behavior tested.
- [ ] Full tests, lint, and type checks pass.
- [ ] I exercised changed service behavior through its real API and inspected logs.
- [ ] I updated both `AGENTS.md` and `CLAUDE.md` when adding a durable project invariant.
