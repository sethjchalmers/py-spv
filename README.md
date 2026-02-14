<p align="center">
  <img src="https://img.shields.io/badge/₿SV-py--spv-eab308?style=for-the-badge&logo=bitcoin&logoColor=white" alt="py-spv" height="48">
</p>

<h1 align="center">py-spv</h1>

<p align="center">
  <strong>A pure-Python SPV Wallet for the BSV Blockchain</strong><br>
  Non-custodial server &amp; native desktop client — validate transactions with Merkle proofs, no full node required.
</p>

<p align="center">
  <a href="https://github.com/sethjchalmers/py-spv/actions/workflows/ci.yml"><img src="https://github.com/sethjchalmers/py-spv/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI"></a>
  <a href="https://github.com/sethjchalmers/py-spv/actions/workflows/release.yml"><img src="https://github.com/sethjchalmers/py-spv/actions/workflows/release.yml/badge.svg" alt="Release"></a>
  <a href="https://sethjchalmers.github.io/py-spv/"><img src="https://img.shields.io/badge/docs-GitHub%20Pages-blue?logo=github" alt="Docs"></a>
  <a href="https://codecov.io/gh/sethjchalmers/py-spv"><img src="https://img.shields.io/badge/coverage-94%25-brightgreen" alt="Coverage"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.12+-3776ab?logo=python&logoColor=white" alt="Python 3.12+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT"></a>
</p>

<p align="center">
  <a href="#-features">Features</a> ·
  <a href="#-quick-start">Quick Start</a> ·
  <a href="#%EF%B8%8F-desktop-wallet">Desktop Wallet</a> ·
  <a href="#-architecture">Architecture</a> ·
  <a href="#-downloads">Downloads</a> ·
  <a href="#-contributing">Contributing</a>
</p>

---

## ✨ Features

| | Feature | Description |
|---|---|---|
| 🔐 | **Non-Custodial** | Private keys never leave your device — BIP39 seed phrase generation with secure backup flow |
| ⚡ | **SPV Validation** | Merkle proof verification via Block Headers Service — no full node required |
| 🥩 | **BEEF Transactions** | Background Evaluation Extended Format with compact ancestry proofs |
| 📬 | **Paymail** | Human-readable addresses (`user@domain.tld`) with P2P payment negotiation |
| 👥 | **Multi-Tenant** | Multiple users via xPub with admin / user role separation |
| 🔄 | **Dual API** | V1 (draft-based) and V2 (outline-based) transaction workflows |
| 📡 | **ARC Integration** | Broadcasting, fee policy, and async status callbacks |
| 🖥️ | **Desktop App** | Dark-themed Qt6 wallet — send, receive, history, QR codes, BIP39 seed wizard |
| 📱 | **Mobile-Ready** | Architecture designed for easy porting to mobile platforms |

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.12+**
- PostgreSQL 15+ (or SQLite for development)
- Redis 7+ (caching & task queue)

### Install

```bash
git clone https://github.com/sethjchalmers/py-spv.git
cd py-spv
python -m venv .venv && source .venv/bin/activate

pip install -e ".[dev]"          # server + dev tools
pip install -e ".[desktop]"      # desktop wallet
pip install -e ".[all]"          # everything
```

### Run the Server

```bash
py-spv                           # starts on localhost:3003
```

### Test

```bash
pytest                           # 491 tests, ~13 seconds
pytest --cov                     # with coverage (94%)
pytest -m "not slow"             # skip integration tests
```

---

## 🖥️ Desktop Wallet

A cross-platform PySide6 (Qt6) desktop wallet with a VSCode-inspired dark theme and BSV gold accents.

```bash
pip install -e ".[desktop]"
py-spv-desktop
```

### Wallet Setup Wizard

The wizard guides non-technical users through wallet creation:

1. **Choose wallet file** — select where to store your wallet data
2. **Create or Import** —
   - 🆕 **Create New Wallet** — generates a 12-word BIP39 seed phrase for backup
   - 📥 **Import Existing** — restore from seed phrase or paste an xPub (watch-only)
3. **Backup confirmation** — verify you've saved your seed phrase before proceeding

### Main Wallet Interface

| Panel | Description |
|---|---|
| **Overview** | Balance display, recent transactions, engine health |
| **Send** | Address input, BSV/sats amount, OP_RETURN data, draft creation |
| **Receive** | Address display with QR code and one-click copy |
| **Transactions** | Full history table with colour-coded status |
| **Settings** | Wallet info, engine health, network configuration |

---

## 📐 Architecture

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
│  BSV Primitives                                   │
│  BIP32/39 Keys · Scripts · Transactions · Merkle  │
├──────────────────────────────────────────────────┤
│  Infrastructure                                   │
│  PostgreSQL/SQLite · Redis · ARC · BHS            │
└──────────────────────────────────────────────────┘
```

### Project Structure

```
py-spv/
├── src/spv_wallet/
│   ├── api/                     # FastAPI routes & middleware
│   ├── engine/                  # Business logic & ORM models
│   │   ├── models/              #   9 V1 models (Xpub, Utxo, Transaction, …)
│   │   ├── services/            #   Service layer (xPub, UTXO, paymail, …)
│   │   └── v2/                  #   V2 engine (outline-based transactions)
│   ├── bsv/                     # BSV primitives (BIP32/39, scripts, tx, ECDSA)
│   ├── chain/                   # ARC broadcaster + BHS client
│   ├── datastore/               # Async SQLAlchemy (PostgreSQL / SQLite)
│   ├── desktop/                 # PySide6 desktop application
│   │   ├── views/               #   5 panels (overview, send, receive, history, settings)
│   │   ├── widgets/             #   Reusable components (amount, QR, status bar)
│   │   ├── wallet_wizard.py     #   BIP39 seed generation wizard
│   │   └── app.py               #   Application entry point
│   ├── paymail/                 # Paymail client & server, PIKE protocol
│   ├── cache/                   # Redis / in-memory cache
│   └── config/                  # Pydantic Settings (env + YAML)
├── tests/                       # 491 tests, 94% coverage
├── .github/workflows/           # CI/CD pipelines
├── docker/                      # Dockerfile & compose
└── docs/                        # OpenAPI spec & project site
```

### Tech Stack

| Layer | Technology |
|---|---|
| Web Framework | [FastAPI](https://fastapi.tiangolo.com/) + Uvicorn |
| ORM | [SQLAlchemy 2.0](https://docs.sqlalchemy.org/) (async) |
| Migrations | [Alembic](https://alembic.sqlalchemy.org/) |
| Validation | [Pydantic v2](https://docs.pydantic.dev/) |
| HTTP Client | [httpx](https://www.python-httpx.org/) (async) |
| Cache | [Redis](https://redis.io/) (hiredis) |
| Desktop GUI | [PySide6](https://doc.qt.io/qtforpython/) (Qt6) |
| BIP39 Seeds | [mnemonic](https://pypi.org/project/mnemonic/) |
| Linting | [Ruff](https://docs.astral.sh/ruff/) |
| Type Checking | [Mypy](https://mypy.readthedocs.io/) (strict) |
| Testing | [pytest](https://docs.pytest.org/) + pytest-asyncio |
| CI/CD | GitHub Actions — lint, test, build, release |

---

## 📦 Downloads

Pre-built desktop binaries are published automatically on every tagged release:

| Platform | Architecture | Download |
|---|---|---|
| 🍎 macOS | Intel + Apple Silicon | [Latest Release](https://github.com/sethjchalmers/py-spv/releases/latest) |
| 🪟 Windows | x64 | [Latest Release](https://github.com/sethjchalmers/py-spv/releases/latest) |
| 🐧 Linux | x64 | [Latest Release](https://github.com/sethjchalmers/py-spv/releases/latest) |

### Create a Release

```bash
git tag v0.1.0
git push origin v0.1.0
# → GitHub Actions builds binaries for all platforms and creates a Release
```

---

## 🛡️ CI/CD Pipeline

Every push and pull request runs through:

| Workflow | Trigger | What it does |
|---|---|---|
| **CI** | Push / PR to `main` | Lint (Ruff) → Type check (Mypy) → Test (pytest, 3 Python versions) → Coverage upload |
| **Release** | Tag `v*` push | Build desktop binaries (macOS, Windows, Linux) → Create GitHub Release with assets |
| **Pages** | Push to `main` | Deploy coverage report + project site to GitHub Pages |

---

## 🧪 Test Suite

```
491 tests — 94% code coverage — ~13 seconds
```

| Category | Tests | Description |
|---|---|---|
| BSV Primitives | 131 | BIP32 keys, addresses, scripts, transactions, Merkle paths |
| Engine Services | 99 | xPub, UTXO, destination, access key, transaction services |
| Infrastructure | 37 | Datastore, cache, config, migrations |
| Chain Integration | 76 | ARC broadcaster, BHS client, chain service |
| API & Errors | 23 | Health endpoint, error hierarchy |
| Integration | 9 | Full engine lifecycle with real SQLite database |
| Desktop | 8 | Theme system, widget formatting |
| Other | 108 | Model ORM, entry points, edge cases |

---

## 💻 Development

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

This project follows [Conventional Commits](https://www.conventionalcommits.org/):
`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/my-feature`)
3. Write tests for new functionality
4. Ensure all checks pass (`pre-commit run --all-files && pytest`)
5. Open a pull request

---

## 🏗️ Roadmap

- [x] **Phase 1** — Foundation layer (BSV primitives, datastore, config)
- [x] **Phase 2** — Engine core (services, cache, model operations)
- [x] **Phase 3** — Transactions & chain (ARC, BHS, Merkle, tx service)
- [x] **Desktop** — Native wallet app with BIP39 seed wizard
- [ ] **Phase 4** — Paymail & contacts
- [ ] **Phase 5** — V2 engine (outline-based transactions)
- [ ] **Phase 6** — Webhooks & notifications
- [ ] **Phase 7** — Admin API & metrics dashboard
- [ ] **Phase 8** — Production hardening & deployment

---

## 📄 Acknowledgements

- [bsv-blockchain/spv-wallet](https://github.com/bsv-blockchain/spv-wallet) — the Go reference implementation
- [ElectrumSV](https://github.com/electrumsv/electrumsv) — desktop wallet UI inspiration
- [BSV Blockchain Documentation](https://docs.bsvblockchain.org/) — protocol specifications

## License

MIT — see [LICENSE](LICENSE) for details.
