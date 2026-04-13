# Vendor Data

`installed_packages.db` is a lightweight local JSON registry used by the MVP control plane.

It tracks:

- installed package names
- versions
- installation timestamps
- package state

This file is intentionally simple for local development. A future production backend can replace it with SQLite, PostgreSQL, or a remote package registry.
