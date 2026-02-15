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

# -- Paymail ---------------------------------------------------------------

ErrPaymailNotFound = SPVError(
    "paymail address not found", status_code=404, code="paymail-not-found"
)
ErrInvalidPaymail = SPVError(
    "invalid paymail address format", status_code=400, code="invalid-paymail"
)
ErrPaymailDuplicate = SPVError(
    "paymail address already exists", status_code=409, code="paymail-duplicate"
)
ErrPaymailDomainNotAllowed = SPVError(
    "paymail domain not allowed by server configuration",
    status_code=400,
    code="paymail-domain-not-allowed",
)
ErrPaymailCapabilitiesNotFound = SPVError(
    "paymail capabilities not found for domain",
    status_code=502,
    code="paymail-capabilities-not-found",
)
ErrPaymailSRVFailed = SPVError(
    "SRV record lookup failed for paymail domain",
    status_code=502,
    code="paymail-srv-failed",
)
ErrPaymailPKIFailed = SPVError(
    "failed to resolve PKI for paymail", status_code=502, code="paymail-pki-failed"
)
ErrPaymailP2PFailed = SPVError(
    "P2P payment destination request failed",
    status_code=502,
    code="paymail-p2p-failed",
)
ErrPaymailP2PSendFailed = SPVError(
    "P2P transaction send failed", status_code=502, code="paymail-p2p-send-failed"
)

# -- Contact ---------------------------------------------------------------

ErrContactDuplicate = SPVError("contact already exists", status_code=409, code="contact-duplicate")
ErrContactInvalidStatus = SPVError(
    "invalid contact status transition", status_code=400, code="contact-invalid-status"
)

# -- V2 User ---------------------------------------------------------------

ErrUserNotFound = SPVError("user not found", status_code=404, code="user-not-found")
ErrUserAlreadyExists = SPVError("user already exists", status_code=409, code="user-already-exists")
ErrInvalidPubKey = SPVError("invalid public key", status_code=400, code="invalid-pubkey")
ErrMissingFieldPubKey = SPVError(
    "missing required field: public key", status_code=400, code="missing-pubkey"
)

# -- V2 Address ------------------------------------------------------------

ErrAddressNotFound = SPVError("address not found", status_code=404, code="address-not-found")

# -- V2 Transaction --------------------------------------------------------

ErrOutlineInvalid = SPVError(
    "transaction outline is invalid", status_code=400, code="outline-invalid"
)
ErrOutlineNoOutputs = SPVError(
    "transaction outline has no outputs", status_code=400, code="outline-no-outputs"
)
ErrRecordTxInvalid = SPVError(
    "recorded transaction is invalid", status_code=400, code="record-tx-invalid"
)

# -- V2 Operation ----------------------------------------------------------

ErrOperationNotFound = SPVError("operation not found", status_code=404, code="operation-not-found")
