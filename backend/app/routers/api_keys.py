import hashlib
import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from ..database import get_db
from ..models import ApiKey
from ..auth import get_current_user

router = APIRouter(prefix="/api/settings/api-keys", tags=["api_keys"])

from datetime import datetime, timedelta

class ApiKeyOut(BaseModel):
    id: int
    name: str
    scope: str
    expires_at: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class ApiKeyCreate(BaseModel):
    name: str
    scope: str = "developer"
    expires_in_days: Optional[int] = None

class ApiKeyCreateOut(BaseModel):
    id: int
    name: str
    key: str # The actual raw key, only shown once!

@router.get("", response_model=List[ApiKeyOut])
def list_api_keys(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    keys = db.query(ApiKey).filter(ApiKey.owner_id == user["sub"]).order_by(ApiKey.created_at.desc()).all()
    return keys

@router.post("", response_model=ApiKeyCreateOut)
def create_api_key(body: ApiKeyCreate, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    # Generate a secure key based on scope prefixing
    prefix = "leaka_dev_" if body.scope == "developer" else "leaka_run_"
    raw_key = f"{prefix}{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    
    expires_at = None
    if body.expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=body.expires_in_days)
    
    api_key = ApiKey(
        owner_id=user["sub"],
        name=body.name,
        key_hash=key_hash,
        scope=body.scope,
        expires_at=expires_at
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    
    return {
        "id": api_key.id,
        "name": api_key.name,
        "key": raw_key
    }

@router.delete("/{key_id}")
def delete_api_key(key_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    api_key = db.query(ApiKey).filter(ApiKey.id == key_id, ApiKey.owner_id == user["sub"]).first()
    if not api_key:
        raise HTTPException(status_code=404, detail="API Key not found")
        
    db.delete(api_key)
    db.commit()
    return {"ok": True}
