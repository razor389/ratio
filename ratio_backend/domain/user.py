"""Admin user domain types for authenticated backend workflows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class AdminUserRecord:
    """Admin user account details retained by the backend."""

    email: str
    name: str
    role: str
    status: str = "active"
    password_hash: str | None = None
    auth_subject: str | None = None
    created_at: datetime | None = None
    last_login_at: datetime | None = None
    id: int | None = None
