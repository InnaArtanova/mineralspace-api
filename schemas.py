# schemas.py
from pydantic import  computed_field  
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID

# Auth
class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    name: str = Field(..., max_length=100)

class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenData(BaseModel):
    user_id: str

# Users
class UserUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    avatar_url: Optional[str] = None
    bio: Optional[str] = Field(None, max_length=1000)
    phone_number: Optional[str] = None

    @validator("phone_number", pre=True, always=True)
    def validate_phone(cls, v):
        if v and not v.startswith("+"):
            raise ValueError("Phone must be in E.164 format")
        return v

class UserProfile(BaseModel):
    id: UUID
    name: str
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

# Collections
class CollectionCreateRequest(BaseModel):
    title: str = Field(..., max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    is_public: bool = False

class CollectionUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    is_public: Optional[bool] = None

class Collection(BaseModel):
    id: UUID
    title: str
    description: Optional[str] = None
    is_public: bool
    owner_id: UUID  # ← Вместо owner_name
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
# Specimens
class GeoJSONPoint(BaseModel):
    type: str = "Point"
    coordinates: List[float]  # [lon, lat]

    @validator("type")
    def must_be_point(cls, v):
        if v != "Point":
            raise ValueError('Only "Point" type allowed')
        return v

    @validator("coordinates")
    def must_have_two_coords(cls, v):
        if len(v) != 2:
            raise ValueError("Must have exactly two coordinates")
        return v

class SpecimenCreateRequest(BaseModel):
    mineral_id: str
    local_name: Optional[str] = Field(None, max_length=100)
    region: str = Field(..., max_length=100)
    location: Optional[GeoJSONPoint] = None
    found_at: Optional[str] = None  # ISO date string
    photo_url: Optional[str] = None

class SpecimenUpdateRequest(BaseModel):
    local_name: Optional[str] = Field(None, max_length=100)
    region: Optional[str] = Field(None, max_length=100)
    location: Optional[GeoJSONPoint] = None
    found_at: Optional[str] = None
    photo_url: Optional[str] = None

class Specimen(BaseModel):
    id: UUID
    collection_id: UUID
    mineral_id: str
    local_name: Optional[str] = None
    region: str
    location: Optional[Dict[str, Any]] = None
    photo_url: Optional[str] = None
    found_at: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    mineral_data: Optional["MineralReference"] = None

# Comments
class CommentCreateRequest(BaseModel):
    specimen_id: UUID
    text: str = Field(..., max_length=1000)

class Comment(BaseModel):
    id: UUID
    specimen_id: UUID
    user_id: UUID
    text: str
    created_at: datetime
    updated_at: Optional[datetime] = None

# Minerals & Reference
class MineralType(BaseModel):
    id: str
    name_ru: str
    name_en: str

class HardnessValue(BaseModel):
    id: str
    value: int
    name_ru: str
    name_en: str

class Cleavage(BaseModel):
    id: str
    name_ru: str
    name_en: str

class CrystalSystem(BaseModel):
    id: str
    name_ru: str
    name_en: str

class CrystalForm(BaseModel):
    id: str
    name_ru: str
    name_en: str

class MineralReference(BaseModel):
    id: str
    name_ru: str
    name_en: str
    chemical_formula: str
    mineral_type: Optional[MineralType] = None
    hardness: Optional[HardnessValue] = None
    cleavage: Optional[Cleavage] = None
    crystal_system: Optional[CrystalSystem] = None
    crystal_form: Optional[CrystalForm] = None
    source: str
    last_synced_at: Optional[datetime] = None

# Error
class Error(BaseModel):
    message: str

# Update forward refs
Specimen.model_rebuild()