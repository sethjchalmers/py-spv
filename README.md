# py-spv

**Python feature-parity SPV Wallet for BSV Blockchain — server + desktop.**

A complete Python port of the [bsv-blockchain/spv-wallet](https://github.com/bsv-blockchain/spv-wallet) (Go) with an [ElectrumSV](https://github.com/electrumsv/electrumsv)-inspired desktop wallet GUI.

> ⚠️ **Status: Pre-Alpha** — under active development. Not yet suitable for production.

---

## Features

### Server (SPV Wallet Engine + REST API)

- **SPV-based transaction validation** — Merkle proofs against block headers (no full node)
- **BEEF transactions** — Background Evaluation Extended Format with ancestry proofs
- **Paymail** — Human-readable addresses (`user@domain.tld`) with P2P payment negotiation
- **PIKE protocol** — Contact exchange between paymail providers
- **Multi-tenant** — Multiple users (xPubs) with role-based access (admin / user)
- **Dual API** — V1 (REST, draft-based) + V2 (OpenAPI, outline-based) transaction workflows
- **ARC integration** — Transaction broadcasting & status callbacks
- **BHS integration** — Block Headers Service for Merkle root verification
- **Webhook notifications** — Event-driven webhook subscriptions
- **PostgreSQL + SQLite** — Async database support via SQLAlchemy 2.0

### Desktop (ElectrumSV-style GUI)

- **PySide6 (Qt6)** native cross-platform desktop application
- **Wallet management** — Create, open, encrypt wallets with wizard-driven setup
- **Send & Receive** — Multi-output send, paymail support, QR codes, payment requests
- **Transaction history** — Sortable, filterable, exportable history view
- **Key management** — BIP32 HD key derivation, address display, key details
- **Contact list** — Paymail-based contact cards with identity management
- **UTXO browser** — Inspect and select individual unspent outputs
- **Interactive console** — Embedded Python console with wallet context
- **Preferences** — Fee policy, fiat display, exchange rates, theming

---

## Architecture

See [CONTEXT.md](CONTEXT.md) for the full architecture document, data models, API surface, subsystem details, and phased implementation roadmap.

```
Clients (Web · Mobile · Desktop · Admin)
        │
   REST API (FastAPI)  +  Paymail Server
        │
   Engine Layer (services, business logic)
        │
   Infrastructure (Postgres/SQLite · Redis · ARC · BHS)
```

---

## Quick Start

### Prerequisites

- **Python 3.12+**
- **PostgreSQL 15+** (or SQLite for development)
- **Redis 7+** (for caching & task queue)

### Installation

```bash
# Clone
git clone https://github.com/sethjchalmers/py-spv.git
cd py-spv

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install with all dependencies (server + desktop + dev tools)
pip install -e ".[all]"

# Or server-only
pip install -e ".[dev]"

# Or desktop-only
pip install -e ".[desktop]"
```

### Development Setup

```bash
# Install pre-commit hooks
pre-commit install
pre-commit install --hook-type commit-msg

# Run the hook suite once to verify
pre-commit run --all-files
```

### Running

```bash
# Start the server
py-spv

# Start the desktop app
py-spv-desktop
```

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov

# Skip slow / integration / desktop tests
pytest -m "not slow and not integration and not desktop"

# Only desktop tests
pytest -m desktop
```

---

## Project Structure

```
py-spv/
├── CONTEXT.md              # Architecture doc & roadmap
├── pyproject.toml           # Project config & dependencies
├── .pre-commit-config.yaml  # Pre-commit hooks
├── alembic/                 # Database migrations
├── src/spv_wallet/          # Main package
│   ├── api/                 #   FastAPI routes & middleware
│   ├── engine/              #   Core business logic & models
│   ├── chain/               #   ARC + BHS chain services
│   ├── paymail/             #   Paymail client & server
│   ├── bsv/                 #   BSV crypto primitives
│   ├── datastore/           #   Database abstraction
│   ├── cache/               #   Redis / in-memory cache
│   ├── taskmanager/         #   Background tasks
│   ├── notifications/       #   Webhooks & events
│   ├── desktop/             #   PySide6 desktop app
│   ├── config/              #   Settings & configuration
│   ├── errors/              #   Error hierarchy
│   └── utils/               #   Shared utilities
├── tests/                   # Test suite (pytest)
└── docker/                  # Dockerfile & compose
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Web Framework | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.0 (async) |
| Migrations | Alembic |
| Validation | Pydantic v2 |
| HTTP Client | httpx (async) |
| Cache | Redis (hiredis) |
| Task Queue | ARQ |
| Logging | structlog |
| Metrics | prometheus-client |
| Desktop GUI | PySide6 (Qt6) |
| QR Codes | qrcode + Pillow |
| Linting | Ruff |
| Type Checking | Mypy (strict) |
| Testing | Pytest + pytest-asyncio |

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/my-feature`)
3. Commit using [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, etc.)
4. Ensure `pre-commit run --all-files` passes
5. Ensure `pytest` passes
6. Open a pull request

---

## License

MIT — see [LICENSE](LICENSE) for details.
