# main.py
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from uuid import UUID

from database import get_db, Base, engine
from models import User, UserCredential, Collection, Specimen, Comment
from schemas import (
    UserRegisterRequest, UserLoginRequest, TokenResponse,
    UserUpdateRequest, UserProfile,
    CollectionCreateRequest, CollectionUpdateRequest, CollectionResponse,
    SpecimenCreateRequest, SpecimenUpdateRequest, SpecimenResponse,
    CommentCreateRequest, CommentResponse
)
from auth import (
    hash_password, verify_password, create_access_token, get_current_user
)



# Создаём таблицы
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="MineralSpace API",
    description="REST API for mineral collectors",
    version="1.0.0"
)

# === AUTH ===
@app.post("/auth/register", response_model=UserProfile, status_code=status.HTTP_201_CREATED)
async def register(user: UserRegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    
    hashed_pw = hash_password(user.password)
    db_user = User(email=user.email, name=user.name)
    db.add(db_user)
    db.flush()
    db_cred = UserCredential(user_id=db_user.id, password_hash=hashed_pw)
    db.add(db_cred)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.post("/auth/login", response_model=TokenResponse)
async def login(user: UserLoginRequest, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    cred = db.query(UserCredential).filter(UserCredential.user_id == db_user.id).first()
    if not cred or not verify_password(user.password, cred.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    access_token = create_access_token(data={"sub": str(db_user.id)})
    return {"access_token": access_token}

# === USERS ===
@app.get("/me", response_model=UserProfile)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user

@app.patch("/me", response_model=UserProfile)
async def update_me(
    update: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    for field, value in update.dict(exclude_unset=True).items():
        setattr(current_user, field, value)
    current_user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(current_user)
    return current_user

@app.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db.delete(current_user)
    db.commit()
    return

# === COLLECTIONS ===
@app.post("/collections", response_model=CollectionResponse, status_code=status.HTTP_201_CREATED)
async def create_collection(
    collection: CollectionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_collection = Collection(
        **collection.dict(),
        owner_id=current_user.id
    )
    db.add(db_collection)
    db.commit()
    db.refresh(db_collection)
    return db_collection

@app.patch("/collections/{collection_id}", response_model=CollectionResponse)
async def update_collection(
    collection_id: UUID,
    update: CollectionUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    collection = db.query(Collection).filter(
        Collection.id == collection_id,
        Collection.owner_id == current_user.id
    ).first()
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    for field, value in update.dict(exclude_unset=True).items():
        if value is not None:
            setattr(collection, field, value)
    collection.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(collection)
    return collection

@app.delete("/collections/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(
    collection_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    collection = db.query(Collection).filter(
        Collection.id == collection_id,
        Collection.owner_id == current_user.id
    ).first()
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    db.delete(collection)
    db.commit()
    return

# === SPECIMENS ===
@app.post("/collections/{collection_id}/specimens", response_model=SpecimenResponse, status_code=status.HTTP_201_CREATED)
async def add_specimen(
    collection_id: UUID,
    specimen: SpecimenCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    collection = db.query(Collection).filter(
        Collection.id == collection_id,
        Collection.owner_id == current_user.id
    ).first()
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    db_specimen = Specimen(**specimen.dict(), collection_id=collection_id)
    db.add(db_specimen)
    db.commit()
    db.refresh(db_specimen)
    return db_specimen

@app.patch("/specimens/{specimen_id}", response_model=SpecimenResponse)
async def update_specimen(
    specimen_id: UUID,
    update: SpecimenUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    specimen = db.query(Specimen).join(Collection).filter(
        Specimen.id == specimen_id,
        Collection.owner_id == current_user.id
    ).first()
    if not specimen:
        raise HTTPException(status_code=404, detail="Specimen not found")
    
    for field, value in update.dict(exclude_unset=True).items():
        if value is not None:
            setattr(specimen, field, value)
    specimen.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(specimen)
    return specimen

@app.delete("/specimens/{specimen_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_specimen(
    specimen_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    specimen = db.query(Specimen).join(Collection).filter(
        Specimen.id == specimen_id,
        Collection.owner_id == current_user.id
    ).first()
    if not specimen:
        raise HTTPException(status_code=404, detail="Specimen not found")
    
    db.delete(specimen)
    db.commit()
    return

# === COMMENTS ===
@app.post("/specimens/{specimen_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def add_comment(
    specimen_id: UUID,
    comment: CommentCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    specimen = db.query(Specimen).filter(Specimen.id == specimen_id).first()
    if not specimen:
        raise HTTPException(status_code=404, detail="Specimen not found")
    
    db_comment = Comment(
        specimen_id=specimen_id,
        author_id=current_user.id,
        content=comment.content
    )
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    return db_comment

@app.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    comment_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    comment = db.query(Comment).filter(
        Comment.id == comment_id,
        Comment.author_id == current_user.id
    ).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    db.delete(comment)
    db.commit()
    return