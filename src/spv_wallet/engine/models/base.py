"""Base model with timestamps, metadata, and lifecycle hooks."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 - SQLAlchemy needs this at runtime for Mapped[datetime]
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, func, inspect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

if TYPE_CHECKING:
    from spv_wallet.engine.client import SPVWalletEngine


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all models."""

    type_annotation_map = {  # noqa: RUF012
        dict[str, Any]: JSON,
    }


class TimestampMixin:
    """Created / updated / soft-deleted timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )


class MetadataMixin:
    """JSON metadata column."""

    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSON,
        nullable=False,
        default=dict,
    )


class ModelOps:
    """Model operations with engine reference and lifecycle hooks.

    This mixin provides:
    - Engine client reference for accessing services
    - New/not_new state tracking
    - Save method with lifecycle hooks
    - Metadata helper methods
    """

    _engine: SPVWalletEngine | None = None

    def __init__(self, *args: Any, engine: SPVWalletEngine | None = None, **kwargs: Any) -> None:
        """Initialize model with optional engine reference."""
        super().__init__(*args, **kwargs)  # type: ignore
        if engine is not None:
            self._engine = engine

    @property
    def engine(self) -> SPVWalletEngine | None:
        """Get the engine client reference."""
        return self._engine

    @engine.setter
    def engine(self, value: SPVWalletEngine) -> None:
        """Set the engine client reference."""
        self._engine = value

    @property
    def is_new(self) -> bool:
        """Check if model is not yet persisted to database."""
        return inspect(self).transient  # type: ignore

    @property
    def not_new(self) -> bool:
        """Check if model is already persisted to database."""
        return not self.is_new

    async def before_save(self) -> None:
        """Lifecycle hook called before save.

        Override in subclasses to add validation, compute fields, etc.
        """
        pass

    async def after_save(self) -> None:
        """Lifecycle hook called after save.

        Override in subclasses to trigger side effects, update cache, etc.
        """
        pass

    async def save(self) -> None:
        """Save model to database with lifecycle hooks.

        Raises:
            RuntimeError: If engine is not set.
        """
        if not self._engine:
            raise RuntimeError("Cannot save: engine not set on model")

        await self.before_save()

        async with self._engine.datastore.session() as session:
            session.add(self)
            await session.commit()
            await session.refresh(self)

        await self.after_save()

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata value by key.

        Args:
            key: Metadata key.
            default: Default value if key not found.

        Returns:
            Metadata value or default.
        """
        if not hasattr(self, "metadata_"):
            return default
        metadata = getattr(self, "metadata_", None)
        if metadata is None:
            return default
        return metadata.get(key, default)

    def set_metadata(self, key: str, value: Any) -> None:
        """Set metadata value by key.

        Args:
            key: Metadata key.
            value: Value to set.
        """
        if not hasattr(self, "metadata_"):
            return
        metadata = getattr(self, "metadata_", None)
        if metadata is None:
            self.metadata_ = {key: value}
        else:
            metadata[key] = value

    def update_metadata(self, updates: dict[str, Any]) -> None:
        """Update multiple metadata values.

        Args:
            updates: Dict of key-value pairs to update.
        """
        if not hasattr(self, "metadata_"):
            return
        metadata = getattr(self, "metadata_", None)
        if metadata is None:
            self.metadata_ = updates.copy()
        else:
            metadata.update(updates)
