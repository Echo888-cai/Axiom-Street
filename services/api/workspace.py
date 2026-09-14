"""P6A identity & workspace isolation: every strategy belongs to a workspace and
reads/writes are scoped to it. Without a real external identity yet, a local
default user/workspace is auto-provisioned; an explicit ``X-Workspace-Id`` header
selects a workspace (and a ``X-User-Id`` header names the actor).

Enforcement is fail-closed: lookups outside the caller's workspace return 404
(they never confirm existence), and every rejection is audited.
"""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.api.db import get_db
from services.api.models import (
    DEFAULT_WORKSPACE_ID,
    User,
    Workspace,
    WorkspaceMember,
    WorkspaceRole,
)

DEFAULT_SLUG = "default"


def ensure_default_workspace(db: Session) -> tuple[Workspace, User]:
    """Auto-provision the personal workspace + user (no external identity yet)."""
    workspace = db.scalars(select(Workspace).where(Workspace.slug == DEFAULT_SLUG).limit(1)).first()
    if workspace is None:
        workspace = Workspace(id=DEFAULT_WORKSPACE_ID, slug=DEFAULT_SLUG, name="个人工作区")
        db.add(workspace)
        db.flush()
    user = db.scalars(select(User).where(User.email == "local@axiom.local").limit(1)).first()
    if user is None:
        user = User(email="local@axiom.local", display_name="本地用户")
        db.add(user)
        db.flush()
    member = db.scalars(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace.id,
            WorkspaceMember.user_id == user.id,
        )
    ).first()
    if member is None:
        db.add(
            WorkspaceMember(
                workspace_id=workspace.id,
                user_id=user.id,
                role=WorkspaceRole.ADMIN,
            )
        )
    db.commit()
    db.refresh(workspace)
    db.refresh(user)
    return workspace, user


def resolve_workspace(
    db: Session,
    workspace_header: Optional[str] = None,
) -> Workspace:
    slug = (workspace_header or DEFAULT_SLUG).strip() or DEFAULT_SLUG
    workspace = db.scalars(select(Workspace).where(Workspace.slug == slug).limit(1)).first()
    if workspace is None:
        if slug == DEFAULT_SLUG:
            # 个人工作区：首次访问自动创建（无外部身份之前的最小可用形态）。
            workspace, _ = ensure_default_workspace(db)
            return workspace
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"工作区 {slug} 不存在（隔离拒绝：不会创建未知工作区）。",
        )
    return workspace


def require_workspace(
    workspace_header: Optional[str] = Header(default=None, alias="X-Workspace-Id"),
    db: Session = Depends(get_db),
) -> Workspace:
    return resolve_workspace(db, workspace_header)


def audit_denial(
    db: Session, workspace_slug: str, action: str, object_type: str, object_id: str
) -> None:
    """Cross-workspace access attempts must be visible, not silent."""
    from services.api.models import AuditLog

    db.add(
        AuditLog(
            actor=f"workspace:{workspace_slug}",
            action=action,
            object_type=object_type,
            object_id=object_id,
        )
    )
    db.commit()
