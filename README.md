<p align="center">
  <h1 align="center">py-bsv</h1>
  <p align="center">
    A Python implementation of the BSV Blockchain SPV Wallet — non-custodial server and desktop client.
  </p>
</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+"></a>
  <a href="https://github.com/sethjchalmers/py-spv/actions"><img src="https://img.shields.io/github/actions/workflow/status/sethjchalmers/py-spv/ci.yml?branch=main&label=tests" alt="Tests"></a>
  <a href="https://codecov.io/gh/sethjchalmers/py-spv"><img src="https://img.shields.io/badge/coverage-97%25-brightgreen" alt="Coverage"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT License"></a>
</p>

---

## Overview

**py-bsv** is a Python port of the [bsv-blockchain/spv-wallet](https://github.com/bsv-blockchain/spv-wallet) — the reference open-source, non-custodial wallet for the BSV Blockchain. It validates transactions using Simplified Payment Verification (Merkle proofs against block headers) without running a full node.

The project includes two components:

- **SPV Wallet Server** — async REST API and engine for managing xPubs, transactions, UTXOs, paymails, and contacts
- **Desktop Wallet** — cross-platform PySide6 (Qt6) GUI inspired by [ElectrumSV](https://github.com/electrumsv/electrumsv)

> **Status:** Pre-alpha — Phase 1 (foundation layer) is complete with 233 tests and 97% coverage. Not yet suitable for production use.

---

## Key Features

| Category | Capabilities |
|---|---|
| **SPV Validation** | Merkle proof verification via Block Headers Service (BHS) — no full node required |
| **BEEF Transactions** | Background Evaluation Extended Format with compact ancestry proofs |
| **Paymail** | Human-readable addresses (`user@domain.tld`), P2P payment negotiation, PIKE contact exchange |
| **Multi-Tenant** | Multiple users identified by xPub with role-based access (admin / user) |
| **Dual API** | V1 (draft-based) and V2 (outline-based) transaction workflows |
| **ARC Integration** | Transaction broadcasting, fee policy, async status callbacks |
| **Webhooks** | Event-driven notifications for transaction and contact state changes |
| **Desktop GUI** | Native wallet app with send/receive, history, UTXO browser, contacts, QR codes |

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│           Clients (Web · Mobile · Desktop)       │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│  API Layer — FastAPI (v1 + v2) + Paymail Server  │
├──────────────────────────────────────────────────┤
│  Engine Layer — Services, business logic          │
│  (xPub · Transaction · UTXO · Paymail · Contact) │
├──────────────────────────────────────────────────┤
│  Infrastructure                                   │
│  PostgreSQL/SQLite · Redis · ARC · BHS            │
└──────────────────────────────────────────────────┘
```

---

## Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL 15+ (or SQLite for development)
- Redis 7+ (caching & task queue)

### Install

```bash
git clone https://github.com/sethjchalmers/py-spv.git
cd py-spv
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # server + dev tools
# pip install -e ".[desktop]"    # desktop GUI
# pip install -e ".[all]"        # everything
```

### Run

```bash
py-spv                           # start the server (localhost:3003)
py-spv-desktop                   # start the desktop wallet
```

### Test

```bash
pytest                            # full suite (233 tests)
pytest --cov                      # with coverage report
pytest -m "not slow"              # skip integration tests
```

---

## Project Structure

```
py-spv/
├── pyproject.toml               # Project config & dependencies
├── alembic/                     # Database migrations
├── src/spv_wallet/
│   ├── api/                     # FastAPI routes & middleware
│   ├── engine/                  # Business logic & ORM models
│   │   ├── models/              #   9 V1 models (Xpub, Utxo, Transaction, …)
│   │   ├── services/            #   Service layer (xPub, UTXO, paymail, …)
│   │   └── v2/                  #   V2 engine (outline-based transactions)
│   ├── bsv/                     # BSV primitives (BIP32, scripts, tx, ECDSA)
│   ├── chain/                   # ARC broadcaster + BHS client
│   ├── datastore/               # Async SQLAlchemy (PostgreSQL / SQLite)
│   ├── paymail/                 # Paymail client & server, PIKE protocol
│   ├── cache/                   # Redis / in-memory cache
│   ├── config/                  # Pydantic Settings (env + YAML)
│   ├── errors/                  # Error hierarchy
│   ├── desktop/                 # PySide6 desktop application
│   └── utils/                   # Crypto helpers
├── tests/                       # 233 tests, 97% coverage
└── docker/                      # Dockerfile & compose
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Web Framework | [FastAPI](https://fastapi.tiangolo.com/) + Uvicorn |
| ORM | [SQLAlchemy 2.0](https://docs.sqlalchemy.org/) (async) |
| Migrations | [Alembic](https://alembic.sqlalchemy.org/) |
| Validation | [Pydantic v2](https://docs.pydantic.dev/) |
| HTTP Client | [httpx](https://www.python-httpx.org/) (async) |
| Cache | [Redis](https://redis.io/) (hiredis) |
| Task Queue | [ARQ](https://arq-docs.helpmanual.io/) |
| Logging | [structlog](https://www.structlog.org/) |
| Metrics | [prometheus-client](https://prometheus.github.io/client_python/) |
| Desktop GUI | [PySide6](https://doc.qt.io/qtforpython/) (Qt6) |
| Linting | [Ruff](https://docs.astral.sh/ruff/) |
| Type Checking | [Mypy](https://mypy.readthedocs.io/) (strict) |
| Testing | [pytest](https://docs.pytest.org/) + pytest-asyncio |

---

## Development

```bash
# Set up pre-commit hooks
pre-commit install && pre-commit install --hook-type commit-msg

# Lint & type-check
ruff check src/
mypy src/

# Run pre-commit on all files
pre-commit run --all-files
```

### Commit Convention

This project follows [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/my-feature`)
3. Write tests for new functionality
4. Ensure all checks pass (`pre-commit run --all-files && pytest`)
5. Open a pull request

---

## Acknowledgements

- [bsv-blockchain/spv-wallet](https://github.com/bsv-blockchain/spv-wallet) — the Go reference implementation this project ports
- [ElectrumSV](https://github.com/electrumsv/electrumsv) — inspiration for the desktop wallet UI
- [BSV Blockchain Documentation](https://docs.bsvblockchain.org/) — protocol specifications and standards

---

## License

MIT — see [LICENSE](LICENSE) for details.
