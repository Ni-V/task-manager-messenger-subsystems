import mimetypes
import string
import random
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Annotated, Optional, List
import logging
import aiofiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_mail import MessageSchema, FastMail
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import selectinload
from database.database_init import get_db
from database.models import User, Project, Task, MessageType
from mail.mail_config import conf
from database.crud import AsyncORM
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, Body
import socketio
from security import security
import uvicorn
from database import schemas, models

app = FastAPI()
app.add_middleware(CORSMiddleware,
                   allow_origins="*",
                   allow_credentials=True,
                   allow_methods=["*"],
                   allow_headers=["*"],
                   )
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
sio = socketio.AsyncServer(cors_allowed_origins='*', async_mode='asgi')
socket_app = socketio.ASGIApp(sio, app)
logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.DEBUG)
UPLOAD_DIR = Path("uploads/")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@app.post("/registration/")
async def register(user: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    query = select(User).where(User.email == user.email)
    user_db = (await db.execute(query)).scalars().first()
    if user_db:
        raise HTTPException(status_code=409, detail="Email already registered")
    confirmation_code = ''.join(random.choices(string.digits, k=4))
    await AsyncORM.create_user(user=user, confirmation_code=confirmation_code)

    message = MessageSchema(
        subject="Confirm your registration",
        recipients=[user.email],
        body=f"Your confirmation code is: {confirmation_code}",
        subtype="plain"
    )
    fm = FastMail(conf)
    await fm.send_message(message)
    return 201


@app.post("/confirm")
async def confirm_registration(email: str, code: str):
    user = await AsyncORM.get_user_by_email(email)
    if not user or user.confirmation_code != code:
        raise HTTPException(status_code=400, detail="Invalid confirmation code")

    await AsyncORM.confirm_user(email)
    return {"msg": "Registration confirmed"}


@app.post("/login", response_model=schemas.Token)
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    user = await AsyncORM.get_user_by_email(form_data.username)
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=400,
            detail="Registration is not confirmed"
        )
    access_token_expires = timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/user/", response_model=schemas.UserSearchResult)
async def read_user(current_user: Annotated[models.User, Depends(security.get_current_user)]):
    return current_user


@app.get("/chats/", response_model=schemas.UserChats)
async def get_all_chats(curr_user: User = Depends(security.get_current_user)):
    if curr_user is None:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated"
        )
    return await AsyncORM.get_all_chats(curr_user.id)


@app.post("/chats/", response_model=schemas.ChatOut)
async def create_chat(photo: UploadFile = File(None), name: Optional[str] = Form(),
                      type: str = Form(),
                      members: List[int] = Form(),
                      curr_user: User = Depends(
                          security.get_current_user)):
    if curr_user is None:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated"
        )
    if photo:
        unique_suffix = uuid.uuid4().hex
        original_filename = Path(photo.filename)
        filename = f"{original_filename.stem}_{unique_suffix}{original_filename.suffix}"
        file_location = UPLOAD_DIR / filename
        async with aiofiles.open(file_location, "wb") as buffer:
            while True:
                chunk = await photo.read(1024)
                if not chunk:
                    break
                await buffer.write(chunk)
    photo_chat = str(file_location) if photo else None
    chat_db = await AsyncORM.create_chat(name=name, members=members, photo=photo_chat,
                                         type=type)
    return chat_db


@app.get("/projects", response_model=schemas.UserProjects)
async def ret_all_prj(curr_user: User = Depends(security.get_current_user)):
    user = await AsyncORM.get_users_projects(curr_user.id)
    return user


@app.get("/user/{user_id}", response_model=schemas.UserSearchResult)
async def search(user_id: int, curr_user: User = Depends(security.get_current_user),
                 db: AsyncSession = Depends(get_db)):
    if curr_user is None:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated"
        )
    query = select(User).where(User.id == user_id)
    user_db = (await db.execute(query)).scalars().first()
    if user_db:
        user = schemas.UserSearchResult.from_orm(user_db).dict()
        return user
    else:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )


@app.put("/user/", response_model=schemas.UserSearchResult)
async def user_update(photo: UploadFile = File(None), first_name: str = Form(None), second_name: str = Form(None),
                      email: str = Form(None), old_password=Form(None), new_password=Form(None),
                      curr_user: User = Depends(security.get_current_user),
                      db: AsyncSession = Depends(get_db)):
    if curr_user is None:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated"
        )
    user = (await db.execute(select(User).where(User.id == curr_user.id))).scalars().first()
    if photo:
        unique_suffix = uuid.uuid4().hex
        original_filename = Path(photo.filename)
        filename = f"{original_filename.stem}_{unique_suffix}{original_filename.suffix}"
        file_location = UPLOAD_DIR / filename
        async with aiofiles.open(file_location, "wb") as buffer:
            while True:
                chunk = await photo.read(1024)  # read file chunk
                if not chunk:
                    break
                await buffer.write(chunk)
        user.photo = str(file_location)
    if first_name:
        user.first_name = first_name
    if second_name:
        user.second_name = second_name
    if email:
        user.email = email
    if new_password and old_password:
        if not security.verify_password(old_password, user.hashed_password):
            raise HTTPException(
                status_code=400,
                detail="Passwords dont match"
            )
        user.hashed_password = security.get_password_hash(new_password)
    db.add(user)
    await db.commit()
    return user


@app.post("/projects/{project_id}/user")
async def add_user_to_prj(project_id: int, user_email: schemas.UserEmail = Body(...),
                          curr_user: User = Depends(security.get_current_user)):
    if curr_user is None:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated"
        )
    await AsyncORM.add_user_to_prj(project_id, user_email.email)
    return 201


@app.post("/projects", response_model=schemas.ProjectOut)
async def create_project(new_project: schemas.ProjectCreate, curr_user: User = Depends(security.get_current_user)):
    if curr_user is None:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated"
        )
    project_db = await AsyncORM.create_project(new_project, curr_user.id)
    return project_db


@app.post("/projects/{project_id}/task", response_model=schemas.TaskOut)
async def create_task(project_id: int, new_task: schemas.TaskCreate, curr_user: User = Depends(
    security.get_current_user), db: AsyncSession = Depends(get_db)):
    query = select(Project).options(selectinload(Project.owner).load_only(User.id)).where(Project.id == project_id)
    res = await db.execute(query)
    result = res.scalars().first()
    if result.owner.id != curr_user.id:
        raise HTTPException(
            status_code=403,
            detail="Only owner can create task"
        )
    logger.info(new_task)
    task = await AsyncORM.create_task(new_task, project_id)
    return task


@app.post("/upload_file/{chat_id}")
async def upload_file(chat_id: int, file: UploadFile = File(), curr_user: User = Depends(security.get_current_user)):
    if curr_user is None:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated"
        )
    unique_suffix = uuid.uuid4().hex
    original_filename = Path(file.filename)
    filename = f"{original_filename.stem}_{unique_suffix}{original_filename.suffix}"
    file_location = UPLOAD_DIR / filename
    async with aiofiles.open(file_location, "wb") as buffer:
        while True:
            chunk = await file.read(1024)
            if not chunk:
                break
            await buffer.write(chunk)
    file_type, _ = mimetypes.guess_type(file.filename)
    if file_type and file_type.startswith("image/"):
        file_type = "image"
    else:
        file_type = "file"
    timestamp, msg_id = await AsyncORM.create_message(None, str(file_location), curr_user.id, chat_id,
                                                      type=file_type)
    user = schemas.UserSearchResult.from_orm(curr_user).dict()
    chat_db = await AsyncORM.get_single_chat(chat_id)
    chat = schemas.ChatInSocket.from_orm(chat_db).dict()
    await sio.emit("new_message", {"user": user, "chat": chat, "filename": file.filename, "message_id": msg_id,
                                   "type": file_type,
                                   "timestamp": timestamp.utcnow().isoformat(),
                                   "url": str(file_location)},
                   room=f"chat_{chat_id}")
    return 201


@app.delete("/projects/{project_id}/task/{task_id}")
async def remove_task(project_id: int, task_id: int, curr_user: User = Depends(security.get_current_user),
                      db: AsyncSession = Depends(get_db)):
    if curr_user is None:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated"
        )
    query = select(Project).options(selectinload(Project.owner).load_only(User.id)
                                    , selectinload(Project.tasks).load_only(Task.id)
                                    ).where(Project.id == project_id)
    prj = (await db.execute(query)).scalars().first()
    if prj.owner.id != curr_user.id:
        raise HTTPException(
            status_code=404,
            detail="Only owner can remove projects"
        )
    if task_id not in [i.id for i in prj.tasks]:
        raise HTTPException(
            status_code=400,
            detail="Project id and task id dont match"
        )
    await AsyncORM.remove_task(task_id)
    return 201


@app.post("/comment/{task_id}")
async def create_comment(task_id: int, comment: schemas.CommentsCreate, curr_user: User = Depends(
                         security.get_current_user)):
    if curr_user is None:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated"
        )
    await AsyncORM.create_comment(comment.content, curr_user.id, task_id)
    return 201


@app.put("/projects/{project_id}/task/{task_id}", response_model=schemas.TaskOut)
async def update_task(project_id: int, task_id: int, task: schemas.TaskUpdate, curr_user: User = Depends(
    security.get_current_user), db: AsyncSession = Depends(get_db)):
    if curr_user is None:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated"
        )
    query = select(Project).options(selectinload(Project.owner).load_only(User.id)
                                    , selectinload(Project.tasks).load_only(Task.id)
                                    ).where(Project.id == project_id)
    prj = (await db.execute(query)).scalars().first()
    if prj.owner.id != curr_user.id:
        raise HTTPException(
            status_code=404,
            detail="Only owner can update projects"
        )
    updated_task = await AsyncORM.update_task(task_id, task)
    return updated_task


@sio.on("connect")
async def connection(sid, environ, auth: dict):
    if not auth:
        await sio.disconnect(sid)
        return False
    token = auth.get("token")
    if not token:
        await sio.disconnect(sid)
        return False
    try:
        user = await security.get_current_user(token)
    except HTTPException:
        await sio.disconnect(sid)
        return False
    await AsyncORM.update_online(user.id, True)
    await sio.save_session(sid, {"user": user.id})
    await sio.emit("connect", {"data": "User connected"})


@sio.on("new_message")
async def message_handler(sid, data: dict):
    session = await sio.get_session(sid)
    user_id = session.get("user")
    message = data.get("message")
    chat_id = data.get("chat_id")
    if message and chat_id:
        timestamp, msg_id = await AsyncORM.create_message(message, None, user_id, chat_id, type="text")
        user_db = await AsyncORM.get_user_by_id(user_id)
        user = schemas.UserSearchResult.from_orm(user_db).dict()
        chat_db = await AsyncORM.get_single_chat(chat_id)
        chat = schemas.ChatInSocket.from_orm(chat_db).dict()
        await sio.emit("new_message", {"user": user, "chat": chat, "message": message, "message_id": msg_id,
                                       "type": "text",
                                       "timestamp": timestamp.utcnow().isoformat()},
                       room=f"chat_{chat_id}")


@sio.on("begin_chat")
async def begin_chat(sid, data: dict):
    chat_id = data.get("chat_id")
    if chat_id:
        await sio.enter_room(sid, f"chat_{chat_id}")


@sio.on("leave_chat")
async def leave_chat(sid, data: dict):
    chat_id = data.get("chat_id")
    if chat_id:
        await sio.leave_room(sid, f"chat_{chat_id}")


@sio.on("set_reaction")
async def reaction(sid, data: dict):
    session = await sio.get_session(sid)
    user_id = session.get("user")
    chat_id = data.get("chat_id")
    reaction_id = data.get("reaction_id")
    msg_id = data.get("message_id")
    if reaction_id and msg_id and chat_id:
        await AsyncORM.create_reaction(reaction_id, msg_id, user_id)
        user_db = await AsyncORM.get_user_by_id(user_id)
        user = schemas.UserSearchResult.from_orm(user_db).dict()
        chat_db = await AsyncORM.get_single_chat(chat_id)
        chat = schemas.ChatInSocket.from_orm(chat_db).dict()
        await sio.emit("set_reaction", {"user": user, "chat": chat, "message_id": msg_id, "reaction": reaction_id})


@sio.on("disconnect")
async def disconnect(sid):
    session = await sio.get_session(sid)
    user_id = session.get("user")
    if user_id:
        await AsyncORM.update_online(user_id, False)


if __name__ == "__main__":
    uvicorn.run(socket_app, host="0.0.0.0", port=8000, log_level="debug")
