# schemas.py
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime, date

# === Auth ===
class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str

class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

# === Users ===
class UserUpdateRequest(BaseModel):
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    phone_number: Optional[str] = None

class UserProfile(BaseModel):
    id: UUID
    name: str
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

# === Collections ===
class CollectionCreateRequest(BaseModel):
    title: str
    description: Optional[str] = None
    is_public: bool = False

class CollectionUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    is_public: Optional[bool] = None

class CollectionResponse(BaseModel):
    id: UUID
    title: str
    description: Optional[str] = None
    is_public: bool
    owner_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# === Specimens ===
class SpecimenCreateRequest(BaseModel):
    mineral_id: str
    local_name: Optional[str] = None
    region: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    photo_url: Optional[str] = None
    found_at: Optional[date] = None
    description: Optional[str] = None

class SpecimenUpdateRequest(BaseModel):
    local_name: Optional[str] = None
    region: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    photo_url: Optional[str] = None
    found_at: Optional[date] = None
    description: Optional[str] = None

class SpecimenResponse(BaseModel):
    id: UUID
    collection_id: UUID
    mineral_id: str
    local_name: Optional[str] = None
    region: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    photo_url: Optional[str] = None
    found_at: Optional[date] = None
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# === Comments ===
class CommentCreateRequest(BaseModel):
    content: str

class CommentResponse(BaseModel):
    id: UUID
    specimen_id: UUID
    author_id: UUID
    content: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True