import hashlib
import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from backend.app.database import get_db
from backend.app.models import ApiKey
from backend.app.auth import get_current_user

router = APIRouter(prefix="/api/settings/api-keys", tags=["api_keys"])

class ApiKeyOut(BaseModel):
    id: int
    name: str
    created_at: datetime
    # We never return the actual key, only the last 4 characters for display if we wanted to
    
    class Config:
        from_attributes = True

class ApiKeyCreate(BaseModel):
    name: str

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
    # Generate a secure key
    raw_key = f"leaka_dev_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    
    api_key = ApiKey(
        owner_id=user["sub"],
        name=body.name,
        key_hash=key_hash
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
