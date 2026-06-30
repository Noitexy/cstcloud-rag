# Security Policy

## Secret handling

- Never commit `backend/.env`, API tokens, passwords, private keys, database files, uploaded documents, Chroma data, or conversation logs.
- Copy `backend/.env.example` to `backend/.env` and fill the token only on the local machine.
- The frontend must not receive or persist `CSTCLOUD_API_KEY`.
- If a credential is exposed in a file, screenshot, issue, commit, or log, revoke and rotate it immediately. Deleting the visible text alone does not make an exposed credential safe.

## Private knowledge data

Runtime data is stored under `backend/data/` and is excluded from Git. Documents and retrieved chunks are sent through the backend to the configured CSTCloud models when embeddings or answers are generated. Do not ingest material that is not allowed to be processed by that external service.

## Deployment boundary

- This portfolio project has no user authentication or tenant isolation. The provided launch scripts and Docker Compose ports bind to `127.0.0.1`; do not expose the API directly to the internet.
- Chroma is used only through the in-process `PersistentClient`. The project does not start or expose the Chroma HTTP server.
- Chroma product telemetry is replaced with an in-process no-op client, so no product event invokes an external telemetry SDK.
- `chromadb` is temporarily constrained to `<1.0` because CVE-2026-45829 affects the Python Chroma server from version 1.0.0 onward and no fixed version is currently listed. Do not replace the embedded client with a network-accessible Chroma Python server.

## Reporting a vulnerability

Do not include credentials, private documents, or personal data in a public GitHub issue. Provide a minimal reproduction with synthetic data and rotate any credential that may have been exposed.
