# main.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi import  FastAPI, Depends, HTTPException, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload, Session
from uuid import UUID
from typing import List, Optional
from sqlalchemy import func, or_, and_
from sqlalchemy import delete, update
from datetime import datetime
from wikidata_service import fetch_mineral_from_wikidata, extract_mineral_data


import schemas 
import collections

from database import get_db
from models import (
    User,
    Collection as CollectionModel,
    Specimen as SpecimenModel,
    Comment,
    MineralReference,
    UserCredentials
)
from schemas import (
    UserRegisterRequest, UserLoginRequest, UserProfile, UserUpdateRequest,
    CollectionCreateRequest, CollectionUpdateRequest, CollectionResponse as CollectionSchema,
    SpecimenCreateRequest, SpecimenUpdateRequest, Specimen as SpecimenSchema,
    CommentCreateRequest, Comment, MineralReference, Error
)
from auth import (
    get_password_hash, verify_password, create_access_token,
    get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES, timedelta
)

app = FastAPI(
    title="MineralSpace API",
    description="RESTful API для коллекционеров минералов.",
    version="1.0.0",
    contact={
        "name": "Инна Артанова",
        "email": "inna.artanova@example.com",
        "url": "https://linkedin.com/in/inna-artanova"
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT"
    }
)
router = APIRouter()
router = APIRouter(prefix="/collections", tags=["Collections"])


bearer_scheme = HTTPBearer()

async def get_collection_by_id(db: AsyncSession, collection_id: UUID):
    result = await db.execute(select(Collection).where(Collection.id == collection_id))
    return result.scalars().first()

# CORS (настройте по необходимости)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === AUTH ===
@app.post("/auth/register", status_code=status.HTTP_201_CREATED, tags=["Auth"])
async def register(user_data: UserRegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == user_data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")
    hashed_pw = get_password_hash(user_data.password)
    new_user = User(
        email=user_data.email,
        name=user_data.name
    )
    db.add(new_user)
    await db.flush()

    # Создаём учётные данные
    from models import UserCredentials
    credentials = UserCredentials(
        user_id=new_user.id,
        password_hash=get_password_hash(user_data.password)
    )
    db.add(credentials)
    await db.commit()
    await db.refresh(new_user)

    access_token = create_access_token(data={"sub": str(new_user.id)})
    return {
        "user": UserProfile(
            id=new_user.id,
            name=new_user.name,
            avatar_url=new_user.avatar_url,
            bio=new_user.bio,
            created_at=new_user.created_at,
            updated_at=new_user.updated_at
        ),
        "accessToken": access_token
    }
@app.post("/auth/login", tags=["Auth"])
async def login(login_data: UserLoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).options(selectinload(User.credentials)) 
    .where(User.email == login_data.email)
)
    
    user = result.scalar_one_or_none()
    if not user or not verify_password(login_data.password, user.credentials.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    access_token = create_access_token(data={"sub": str(user.id)})
    return {
        "user": UserProfile(
            id=user.id,
            name=user.name,
            avatar_url=user.avatar_url,
            bio=user.bio,
            created_at=user.created_at,
            updated_at=user.updated_at
        ),
        "accessToken": access_token
    }

# === USERS ===
@app.get("/me", response_model=UserProfile, tags=["Users"])
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user

@app.patch("/me", response_model=UserProfile, tags=["Users"])
async def update_me(
    update_data: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    for field, value in update_data.dict(exclude_unset=True).items():
        setattr(current_user, field, value)
    await db.commit()
    await db.refresh(current_user)
    return current_user

@app.delete("/me", status_code=status.HTTP_204_NO_CONTENT, tags=["Users"])
async def delete_me(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await db.delete(current_user)
    await db.commit()
    return

# === COLLECTIONS ===
@app.get("/collections", response_model=List[schemas.CollectionResponse], tags=["Collections"])
async def list_collections(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    offset = (page - 1) * limit
    stmt = (
        select(Collection)
        .where(Collection.owner_id == current_user.id)
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    collections = result.scalars().all()
    return collections  # ← Просто возвращаем список

@app.post("/collections", status_code=status.HTTP_201_CREATED, response_model=schemas.CollectionResponse, tags=["Collections"])
async def create_collection(
    collection_create: schemas.CollectionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    new_collection = Collection(
        title=collection_create.title,
        description=collection_create.description,
        is_public=collection_create.is_public,
        owner_id=current_user.id  # ← Передаём ID владельца
    )
    db.add(new_collection)
    await db.commit()
    await db.refresh(new_collection)
    return new_collection  

@router.get("/{collection_id}", response_model=CollectionSchema, tags=["Collections"])
async def get_collection(
    collection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    collection = await get_collection_by_id(db, collection_id)
    if not collection:
        raise HTTPException(status_code=404, detail="Коллекция не найдена")

    # Проверка доступа: владелец или публичная коллекция
    if collection.owner_id != current_user.id and not collection.is_public:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    return collection
app.include_router(router)

@router.delete(
    "/{collection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_collection(  
    collection_id: UUID,      
    db: AsyncSession = Depends(get_db),  
    current_user = Depends(get_current_user),
):
    

# Найти коллекцию
    result = await db.execute(select(Collection).where(Collection.id == collection_id))
    collection = result.scalars().first()

    if not collection:
        raise HTTPException(status_code=404, detail="Коллекция не найдена")

    if collection.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет прав на удаление")

    # Удалить
    await db.execute(delete(Collection).where(Collection.id == collection_id))
    await db.commit()

    return  # 204 No Content

# Редактировать коллекцию
@router.patch(
    "/{collection_id}",
    response_model=CollectionSchema,
    summary="Частичное обновление коллекции",
    description="Обновляет указанные поля коллекции. Доступно только владельцу."
)
async def update_collection(
    collection_id: UUID,
    update_data: CollectionUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    # 1. Найти коллекцию
    result = await db.execute(select(Collection).where(Collection.id == collection_id))
    collection = result.scalars().first()

    if not collection:
        raise HTTPException(status_code=404, detail="Коллекция не найдена")

    # 2. Проверить права
    if collection.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет прав на редактирование")

    # 3. Обновить только переданные поля
    update_dict = update_data.model_dump(exclude_unset=True) 

    if not update_dict:
        raise HTTPException(status_code=400, detail="Нет данных для обновления")

    # Применяем изменения к объекту
    for field, value in update_dict.items():
        setattr(collection, field, value)

    # 4. Сохранить
    db.add(collection)
    await db.commit()
    await db.refresh(collection)

    return collection
app.include_router(router)

# === SPECIMENTS ===
@app.get("/specimens/{specimen_id}", response_model=schemas.Specimen, tags=["Specimens"])
async def get_specimen(
    specimen_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    specimen = await db.get(SpecimenModel, specimen_id)
    if not specimen:
        raise HTTPException(status_code=404, detail="Specimen not found")
    
    # Проверка доступа к коллекции (если нужно)
    collection = await db.get(CollectionModel, specimen.collection_id)
    if not collection.is_public and collection.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Опционально: подгрузить mineral_data
    if specimen.mineral_id:
        mineral_ref = await db.get(MineralReference, specimen.mineral_id)
        specimen.mineral_data = mineral_ref  # Добавляем как атрибут

    return specimen  # ← Просто возвращаем SQLAlchemy-объект!


# POST /collections/{collectionId}/specimens
@app.post(
    "/collections/{collection_id}/specimens",
    status_code=status.HTTP_201_CREATED,
    response_model=SpecimenSchema,  # ← Pydantic-схема для ответа
    tags=["Specimens"]
)
async def add_specimen_to_collection(
    collection_id: UUID,
    specimen_data: SpecimenCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    collection = await db.get(CollectionModel, collection_id)  # ← CollectionModel
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    if collection.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not own this collection")

    # Создаём SQLAlchemy-модель (НЕ Pydantic!)
    specimen = SpecimenModel(
        collection_id=collection_id,
        **specimen_data.dict(exclude_unset=True)
    )
    db.add(specimen)
    await db.commit()
    await db.refresh(specimen)  # ← Теперь specimen содержит id, created_at и т.д.
    
    # Опционально: подгрузить mineral_data
    if specimen.mineral_id:
        mineral_ref = await db.get(MineralReference, specimen.mineral_id)
        specimen.mineral_data = mineral_ref
    
    return specimen  # ← Возвращаем SQLAlchemy-объект, FastAPI сам конвертирует в SpecimenSchema


# GET /specimens/{id}
@app.get("/specimens/{specimen_id}", response_model=SpecimenSchema, tags=["Specimens"])
async def get_specimen(
    specimen_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    specimen = await db.get(SpecimenSchema, specimen_id)
    if not specimen:
        raise HTTPException(status_code=404, detail="Specimen not found")

    collection = await db.get(Collection, specimen.collection_id)
    if not collection.is_public and collection.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied to private collection")

    # Опционально: подгрузить mineralData
    mineral_ref = None
    if specimen.mineral_id:
        mineral_ref = await db.get(MineralReference, specimen.mineral_id)

    return SpecimenModel(
        id=specimen.id,
        collection_id=specimen.collection_id,
        mineral_id=specimen.mineral_id,
        local_name=specimen.local_name,
        region=specimen.region,
        location=specimen.location,
        photo_url=specimen.photo_url,
        found_at=specimen.found_at,
        created_at=specimen.created_at,
        updated_at=specimen.updated_at,
        mineral_data=mineral_ref
    )


# PATCH /specimens/{id}
@app.patch("/specimens/{specimen_id}", response_model=SpecimenSchema, tags=["Specimens"])
async def update_specimen(
    specimen_id: UUID,
    update_data: SpecimenUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    specimen = await db.get(SpecimenSchema, specimen_id)
    if not specimen:
        raise HTTPException(status_code=404, detail="Specimen not found")

    collection = await db.get(Collection, specimen.collection_id)
    if collection.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="You cannot edit specimens in others' collections")

    for field, value in update_data.dict(exclude_unset=True).items():
        setattr(specimen, field, value)
    await db.commit()
    await db.refresh(specimen)

    mineral_ref = None
    if specimen.mineral_id:
        mineral_ref = await db.get(MineralReference, specimen.mineral_id)

    return SpecimenSchema(
        id=specimen.id,
        collection_id=specimen.collection_id,
        mineral_id=specimen.mineral_id,
        local_name=specimen.local_name,
        region=specimen.region,
        location=specimen.location,
        photo_url=specimen.photo_url,
        found_at=specimen.found_at,
        created_at=specimen.created_at,
        updated_at=specimen.updated_at,
        mineral_data=mineral_ref
    )


# DELETE /specimens/{id}
@app.delete("/specimens/{specimen_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Specimens"])
async def delete_specimen(
    specimen_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    specimen = await db.get(SpecimenModel, specimen_id)
    if not specimen:
        raise HTTPException(status_code=404, detail="Specimen not found")

    collection = await db.get(Collection, specimen.collection_id)
    if collection.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="You cannot delete specimens in others' collections")

    await db.delete(specimen)
    await db.commit()
    return

# === COMMENTS ===

# POST /comments
@app.post("/comments", status_code=status.HTTP_201_CREATED, response_model=Comment, tags=["Comments"])
async def create_comment(
    comment_data: CommentCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    specimen = await db.get(SpecimenSchema, comment_data.specimen_id)
    if not specimen:
        raise HTTPException(status_code=404, detail="Specimen not found")

    # Проверка доступа к образцу (через коллекцию)
    collection = await db.get(Collection, specimen.collection_id)
    if not collection.is_public and collection.owner_id != current_user.id:
        # Можно разрешить комментировать публичные коллекции даже не владельцам
        # Но если коллекция приватная — только владелец может видеть → комментировать нельзя
        pass  # В текущей логике: любой авторизованный пользователь может комментировать ЛЮБОЙ видимый образец
        # Но мы не знаем, видит ли он его. Для упрощения — разрешаем всем авторизованным.
        # Если нужно строже — проверяйте, как в get_specimen

    comment = Comment(
        specimen_id=comment_data.specimen_id,
        user_id=current_user.id,
        text=comment_data.text
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return comment


# DELETE /comments/{commentId}
@app.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Comments"])
async def delete_comment(
    comment_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    comment = await db.get(Comment, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    if comment.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only delete your own comments")
    await db.delete(comment)
    await db.commit()
    return



# === REFERENCE DATA ===
@app.get("/reference/mineral-types", response_model=List[schemas.MineralType], tags=["Reference Data"])
async def get_mineral_types(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(schemas.MineralType))
    return result.scalars().all()

# Аналогично для /reference/hardness, /cleavages и др.

# === MINERALS ===
@app.get("/minerals/{mineral_id}", response_model=schemas.MineralReference, tags=["Minerals"])
async def get_mineral(mineral_id: str, db: AsyncSession = Depends(get_db)):
    # Проверяем, есть ли запись в БД
    mineral = await db.get(MineralReference, mineral_id)
    
    if mineral:
        return mineral

    # Если нет — пробуем загрузить из Wikidata
    if mineral_id.startswith("wikidata:"):
        wikidata_key = mineral_id.split(":", 1)[1]  # "Q123456"
        entity = fetch_mineral_from_wikidata(wikidata_key)
        
        if not entity:
            raise HTTPException(status_code=404, detail="Mineral not found in Wikidata")
        
        data = extract_mineral_data(entity)
        
        # Создаём новую запись
        new_mineral = MineralReference(
            id=mineral_id,
            name_ru=data["name_ru"],
            name_en=data["name_en"],
            chemical_formula=data["chemical_formula"],
            mineral_type_id=data["mineral_type_id"],
            hardness_id=data["hardness_id"],
            cleavage_id=data["cleavage_id"],
            crystal_system_id=data["crystal_system_id"],
            crystal_form_id=data["crystal_form_id"],
            source="wikidata",
            last_synced_at=datetime.utcnow()
        )
        db.add(new_mineral)
        await db.commit()
        await db.refresh(new_mineral)
        return new_mineral
    
    raise HTTPException(status_code=404, detail="Mineral not found")