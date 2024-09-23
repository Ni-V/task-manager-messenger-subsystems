from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select, delete
from fastapi_mail import FastMail, MessageSchema
from sqlalchemy.orm import joinedload, selectinload

from database import schemas
from database.database_init import engine, Base
from database.models import User, Chat, Project, Task, TaskStatus, Message, Reaction, MessageType, Comment
from database.database_init import session_factory
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AsyncORM:

    @staticmethod
    async def create_table():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    @staticmethod
    async def get_user_by_email(email: str):
        async with (session_factory() as session):
            # query = (select(User)
            #         .options(
            #    selectinload(User.projects)
            #    .selectinload(Project.tasks),
            #    selectinload(User.projects)
            #    .selectinload(Project.owner),
            #    selectinload(User.chats),
            #    selectinload(User.projects).selectinload(Project.tasks).selectinload(Task.assigned),
            #    selectinload(User.projects).selectinload(Project.tasks).selectinload(Task.comments)
            # )
            #         .where(User.email == email))
            query = select(User).where(User.email == email)
            res = await session.execute(query)
        return res.unique().scalars().first()

    @staticmethod
    async def get_user_by_id(id: int):
        async with (session_factory() as session):
            query = select(User).where(User.id == id)
            res = await session.execute(query)
        return res.unique().scalars().first()

    @staticmethod
    async def get_users_projects(id: int):
        async with session_factory() as session:
            query = select(User).options(selectinload(User.projects).selectinload(
                Project.tasks),
                selectinload(User.projects).selectinload(Project.owner), selectinload(User.projects).selectinload(
                    Project.tasks).selectinload(Task.assigned), selectinload(User.projects).selectinload(
                    Project.tasks).selectinload(Task.comments), selectinload(User.projects).selectinload(
                    Project.members), selectinload(User.projects).selectinload(
                    Project.tasks).selectinload(Task.comments).selectinload(Comment.sender)
            ).where(User.id == id)
            user_db = await session.execute(query)
            user = user_db.scalars().first()
            return user

    @staticmethod
    async def create_user(user: schemas.UserCreate, confirmation_code: str):
        async with session_factory() as session:
            user_db = User(email=user.email, hashed_password=pwd_context.hash(user.password), is_active=False,
                           confirmation_code=confirmation_code,
                           is_online=False
                           )
            session.add(user_db)
            await session.commit()
            await session.refresh(user_db)
            user_db.first_name = "User"
            user_db.second_name = f"{user_db.id}"
            await session.commit()

    @staticmethod
    async def confirm_user(email: str):
        async with session_factory() as session:
            query = select(User).where(User.email == email)
            res = await session.execute(query)
            user = res.scalars().first()
            user.confirmation_code = None
            user.is_active = True
            await session.commit()

    @staticmethod
    async def update_online(id: int, value: bool):
        async with session_factory() as session:
            query = select(User).where(User.id == id)
            res = await session.execute(query)
            user = res.scalars().first()
            user.is_online = value
            await session.commit()
            await session.refresh(user)
            return user

    @staticmethod
    async def get_all_chats(id: int):
        async with session_factory() as session:
            query = select(User).options(
                selectinload(User.chats),
                selectinload(User.chats).selectinload(Chat.members),
                selectinload(User.chats).selectinload(Chat.messages),
                selectinload(User.chats).selectinload(Chat.messages).selectinload(Message.reactions),
                selectinload(User.chats).selectinload(Chat.messages).selectinload(Message.reactions).selectinload(
                    Reaction.sender)
            ).where(User.id == id)
            user = await session.execute(query)
            return user.scalars().first()

    @staticmethod
    async def create_chat(name, members, photo, type):
        async with session_factory() as session:
            users = []
            for id in members:
                user = await AsyncORM.get_user_by_id(id)
                if not user:
                    raise HTTPException(
                        status_code=400,
                        detail="Incorrect user info"
                    )
                users.append(user)
            chat = Chat(name=name, members=users, photo=photo, messages=[], type=type)
            session.add(chat)
            await session.commit()
            await session.refresh(chat)
            query = select(Chat).options(selectinload(Chat.members),
                                         selectinload(Chat.messages),
                                         selectinload(Chat.messages).selectinload(Message.reactions)).where(Chat.id == chat.id)
            return (await session.execute(query)).scalars().first()

    @staticmethod
    async def create_project(project: schemas.ProjectCreate, owner_id: int):
        async with session_factory() as session:
            query = select(User).where(User.id == owner_id).options(selectinload(User.my_projects)).options(
                selectinload(User.projects))
            result = await session.execute(query)
            user = result.scalars().first()
            project_db = Project(name=project.name, color=project.color)
            user.my_projects.append(project_db)
            user.projects.append(project_db)
            await session.commit()
            await session.refresh(user)
            project_id = user.projects[-1].id
            project_out = await session.execute(select(Project)
                                                .options(selectinload(Project.owner),
                                                         selectinload(Project.tasks))
                                                .where(Project.id == project_id))
            return project_out.scalars().first()

    @staticmethod
    async def create_task(task: schemas.TaskCreate, project_id: int):
        async with session_factory() as session:
            assigned = []
            for user_id in task.assigned:
                search_user = select(User).options(selectinload(User.projects).load_only(Project.id)).where(User.id ==
                                                                                                            user_id)
                res = await session.execute(search_user)
                result = res.scalars().first()
                if result is None:
                    raise HTTPException(status_code=404, detail="User not found")
                if project_id not in [i.id for i in result.projects]:
                    raise HTTPException(status_code=404, detail="User not member of the project")
                assigned.append(result)
            new_task = Task(name=task.name, description=task.description, assigned=assigned,
                            project_id=project_id, status=TaskStatus.todo, time_end=task.time_end,
                            time_start=task.time_start)
            session.add(new_task)
            await session.commit()
            query = select(Task).options(selectinload(Task.assigned), selectinload(Task.comments))
            task_db = (await session.execute(query)).scalars().first()
            return task_db

    @staticmethod
    async def add_user_to_prj(project_id: int, email: str):
        async with session_factory() as session:
            query = select(User).where(User.email == email)
            user_db = await session.execute(query)
            user = user_db.scalars().first()
            if not user:
                raise HTTPException(
                    status_code=404,
                    detail="User not found"
                )
            query = select(Project).options(selectinload(Project.members).load_only(User.id)).where(Project.id ==
                                                                                                    project_id)
            project_db = await session.execute(query)
            project = project_db.scalars().first()
            if not project:
                raise HTTPException(
                    status_code=404,
                    detail="Project not found"
                )
            if user.id in [i.id for i in project.members]:
                raise HTTPException(
                    status_code=404,
                    detail="User already in project"
                )
            project.members.append(user)
            session.add(project)
            await session.commit()

    @staticmethod
    async def remove_task(task_id: int):
        async with session_factory() as session:
            query = select(Task).where(Task.id == task_id)
            task_db = await session.execute(query)
            task = task_db.scalars().first()
            if task is None:
                raise HTTPException(
                    status_code=404,
                    detail="Task not found"
                )
            await session.delete(task)
            await session.commit()

    @staticmethod
    async def update_task(task_id: int, task_in: schemas.TaskUpdate):
        async with session_factory() as session:
            query = select(Task).options(selectinload(Task.assigned), selectinload(Task.comments)
                                         ).where(Task.id == task_id)
            task_db = await session.execute(query)
            task = task_db.scalars().first()
            if task_in.assigned:
                users = []
                for i in task_in.assigned:
                    query = select(User).where(User.id == i)
                    user = (await session.execute(query)).scalars().first()
                    if user is None:
                        raise HTTPException(
                            status_code=404,
                            detail="Assigned user not found"
                        )
                    users.append(user)
                task.assigned = users
            if task_in.description:
                task.description = task_in.description
            if task_in.name:
                task.name = task_in.name
            if task_in.time_start:
                task.time_start = task_in.time_start
            if task_in.time_end:
                task.time_end = task_in.time_end
            if task_in.status:
                task.status = TaskStatus[task_in.status]
            session.add(task)
            await session.commit()
            await session.refresh(task)
            return task

    @staticmethod
    async def create_message(content: Optional[str], file_path: Optional[str], sender_id: int, chat_id: int,
                             type: str) -> tuple[datetime, int]:
        async with session_factory() as session:
            new_message = Message(content=content, file_path=file_path, user_id=sender_id, chat_id=chat_id,
                                  type=MessageType[type])
            session.add(new_message)
            await session.commit()
            await session.refresh(new_message)
            return new_message.timestamp, new_message.id

    @staticmethod
    async def get_single_chat(chat_id: int):
        async with session_factory() as session:
            query = select(Chat).where(Chat.id == chat_id)
            res = await session.execute(query)
            chat = res.scalars().first()
            return chat

    @staticmethod
    async def create_reaction(reaction: int, message_id, user_id):
        async with session_factory() as session:
            new_reaction = Reaction(content=reaction, message_id=message_id, user_id=user_id)
            session.add(new_reaction)
            await session.commit()

    @staticmethod
    async def create_comment(content: str, user_id: int, task_id: int):
        async with session_factory() as session:
            new_comment = Comment(content=content, sender_id=user_id, task_id=task_id)
            session.add(new_comment)
            await session.commit()

