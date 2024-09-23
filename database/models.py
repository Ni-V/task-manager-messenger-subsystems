import datetime
import enum
from typing import Annotated, Optional
from sqlalchemy import String, ForeignKey, DateTime, JSON, func, text

from database.database_init import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship

intpk = Annotated[int, mapped_column(autoincrement=True, primary_key=True)]


class User(Base):
    __tablename__ = "users"
    id: Mapped[intpk]
    photo: Mapped[str] = mapped_column(nullable=True)
    first_name: Mapped[str] = mapped_column(nullable=True)
    second_name: Mapped[str] = mapped_column(nullable=True)
    email = mapped_column(String, unique=True)
    hashed_password: Mapped[str]
    confirmation_code = mapped_column(String, nullable=True)
    is_active: Mapped[bool]
    is_online: Mapped[bool]
    chats: Mapped[list["Chat"]] = relationship(back_populates="members", secondary="chat_members")
    messages: Mapped[list["Message"]] = relationship(back_populates="sender")
    my_projects: Mapped[list["Project"]] = relationship(back_populates="owner")
    projects: Mapped[list["Project"]] = relationship(back_populates="members", secondary="project_members")
    reactions: Mapped[list["Reaction"]] = relationship(back_populates="sender")
    tasks: Mapped[list["Task"]] = relationship(back_populates="assigned", secondary="task_assigned")
    comments: Mapped[list["Comment"]] = relationship(back_populates="sender")


class TaskAssigned(Base):
    __tablename__ = "task_assigned"
    task_id = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)
    user_id = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[intpk]
    name: Mapped[str]
    color: Mapped[str]
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    owner: Mapped["User"] = relationship(back_populates="my_projects")
    members: Mapped[list["User"]] = relationship(back_populates="projects", secondary="project_members")
    tasks: Mapped[list["Task"]] = relationship(back_populates="project")


class TaskStatus(enum.Enum):
    todo = "todo"
    inprogress = "inprogress"
    completed = "completed"


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[intpk]
    assigned: Mapped[list["User"]] = relationship(back_populates="tasks", secondary="task_assigned")
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    project: Mapped["Project"] = relationship(back_populates="tasks")
    time_end: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    time_start: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    description: Mapped[str]
    name: Mapped[str]
    comments: Mapped[list["Comment"]] = relationship(back_populates="task")
    status: Mapped[TaskStatus]


class ProjectMembers(Base):
    __tablename__ = "project_members"
    project_id = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    user_id = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)


class MessageType(enum.Enum):
    file = "file"
    image = "image"
    text = "text"


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[intpk]
    timestamp: Mapped[datetime.datetime] = mapped_column(default=text("TIMEZONE('utc', now())"))
    type: Mapped[MessageType]
    content: Mapped[str] = mapped_column(nullable=True)
    file_path: Mapped[str] = mapped_column(nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    sender: Mapped["User"] = relationship(back_populates="messages")
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"))
    chat: Mapped["Chat"] = relationship(back_populates="messages")
    reactions: Mapped[list["Reaction"]] = relationship(back_populates="message")
    read_id: Mapped[list[int]] = mapped_column(JSON, default=[])


class ChatType(enum.Enum):
    direct = "direct"
    group = "group"


class Chat(Base):
    __tablename__ = "chats"
    id: Mapped[intpk]
    name: Mapped[Optional[str]] = mapped_column(nullable=True)
    members: Mapped[list["User"]] = relationship(back_populates="chats", secondary="chat_members")
    messages: Mapped[list["Message"]] = relationship(back_populates="chat")
    photo: Mapped[Optional[str]] = mapped_column(nullable=True)
    type: Mapped[ChatType]


class ChatMember(Base):
    __tablename__ = "chat_members"
    chat_id = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"), primary_key=True)
    user_id = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)


class Comment(Base):
    __tablename__ = "comments"
    id: Mapped[intpk]
    content: Mapped[str]
    timestamp: Mapped[datetime.datetime] = mapped_column(default=text("TIMEZONE('utc', now())"))
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    sender: Mapped["User"] = relationship(back_populates="comments")
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    task: Mapped["Task"] = relationship(back_populates="comments")
    #parent_comment_id: Mapped[int] = mapped_column(ForeignKey("comments.id", ondelete="CASCADE"), nullable=True)
    #replies: Mapped[list["Comment"]] = relationship("Comment", back_populates="parent_comment")
    #parent_comment: Mapped["Comment"] = relationship("Comment", back_populates="replies", remote_side="Comment.id")


class Reaction(Base):
    __tablename__ = "reactions"
    id: Mapped[intpk]
    content: Mapped[int]
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id"), onupdate="CASCADE")
    message: Mapped["Message"] = relationship(back_populates="reactions")
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    sender: Mapped["User"] = relationship(back_populates="reactions")

