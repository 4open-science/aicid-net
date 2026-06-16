from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.http_signature import compute_fingerprint
from app.database import get_db
from app.models.ssh_key import SSHKey
from app.models.user import User
from app.schemas.ssh_key import SSHKeyCreate, SSHKeyRead

router = APIRouter()


@router.get("/ssh-keys", response_model=List[SSHKeyRead])
async def list_ssh_keys(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(SSHKey).where(SSHKey.user_id == current_user.id).order_by(SSHKey.created_at.desc())
    )
    return result.scalars().all()


@router.post("/ssh-keys", response_model=SSHKeyRead, status_code=status.HTTP_201_CREATED)
async def add_ssh_key(
    body: SSHKeyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        fingerprint = compute_fingerprint(body.public_key)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Could not parse public key: {e}")

    existing = await db.execute(select(SSHKey).where(SSHKey.key_fingerprint == fingerprint))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A key with this fingerprint already exists")

    key = SSHKey(
        user_id=current_user.id,
        label=body.label.strip(),
        public_key=body.public_key.strip(),
        key_fingerprint=fingerprint,
        is_active=True,
    )
    db.add(key)
    await db.commit()
    await db.refresh(key)
    return key


@router.delete("/ssh-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ssh_key(
    key_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(SSHKey).where(SSHKey.id == key_id, SSHKey.user_id == current_user.id)
    )
    key = result.scalar_one_or_none()
    if key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SSH key not found")
    await db.delete(key)
    await db.commit()
