"""All error definitions ported from spverrors/definitions.go."""

from __future__ import annotations

from spv_wallet.errors.spv_errors import SPVError

# -- Authentication --------------------------------------------------------

ErrUnauthorized = SPVError("unauthorized", status_code=401, code="unauthorized")
ErrAdminRequired = SPVError("admin authentication required", status_code=403, code="admin-required")

# -- Validation ------------------------------------------------------------

ErrMissingFieldXPub = SPVError("missing required field: xpub", status_code=400, code="missing-xpub")
ErrInvalidXPub = SPVError("invalid xpub key", status_code=400, code="invalid-xpub")

# -- Not Found -------------------------------------------------------------

ErrXPubNotFound = SPVError("xpub not found", status_code=404, code="xpub-not-found")
ErrTransactionNotFound = SPVError(
    "transaction not found", status_code=404, code="transaction-not-found"
)
ErrUTXONotFound = SPVError("utxo not found", status_code=404, code="utxo-not-found")
ErrContactNotFound = SPVError("contact not found", status_code=404, code="contact-not-found")

# -- Transaction -----------------------------------------------------------

ErrNotEnoughFunds = SPVError("not enough funds", status_code=422, code="not-enough-funds")
ErrDraftNotFound = SPVError("draft transaction not found", status_code=404, code="draft-not-found")
ErrTransactionRejected = SPVError(
    "transaction rejected by network", status_code=422, code="transaction-rejected"
)
