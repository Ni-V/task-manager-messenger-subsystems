import datetime

from fastapi import UploadFile, File, Form
from pydantic import BaseModel, field_validator
from typing import List, Optional, Annotated


class UserBase(BaseModel):
    email: str
    first_name: str
    second_name: str
    photo: Optional[str]

    class Config:
        from_attributes = True


class UserSearchResult(UserBase):
    id: int

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    password: str
    email: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None


class ProjectCreate(BaseModel):
    name: str
    color: str


class ProjectOut(BaseModel):
    id: int
    name: str
    color: str
    owner: UserSearchResult
    tasks: Optional[List["TaskOut"]] = []
    members: List[UserSearchResult]

    class Config:
        from_attributes = True


class TaskCreate(BaseModel):
    assigned: List[int]
    time_start: datetime.datetime
    time_end: datetime.datetime
    description: str
    name: str


class TaskUpdate(BaseModel):
    assigned: Optional[List[int]] = None
    time_start: Optional[datetime.datetime] = None
    time_end: Optional[datetime.datetime] = None
    description: Optional[str] = None
    name: Optional[str] = None
    status: Optional[str] = None


class TaskWithoutProject(BaseModel):
    assigned: List[UserSearchResult]
    time_start: datetime.datetime
    time_end: datetime.datetime
    description: str
    name: str


class CommentsCreate(BaseModel):
    content: str
    task_id: int


class UserEmail(BaseModel):
    email: str


class CommentsOut(CommentsCreate):
    id: int
    sender: UserSearchResult
    timestamp: datetime.datetime

    class Config:
        from_attributes = True

    @field_validator('timestamp')
    @classmethod
    def set_timestamp_to_utc(cls, v):
        if v.tzinfo is None:
            return v.replace(tzinfo=datetime.timezone.utc)
        return v.astimezone(datetime.timezone.utc)


class TaskOut(TaskWithoutProject):
    assigned: List[UserSearchResult]
    id: int
    comments: list[CommentsOut]
    status: str

    class Config:
        from_attributes = True


class ChatBase(BaseModel):
    name: Optional[str]
    type: str


class ChatCreate(ChatBase):
    members: List[int]


class ChatOut(ChatBase):
    id: int
    members: List[UserSearchResult]
    messages: List["MessageOut"]
    photo: Optional[str]

    class Config:
        from_attributes = True


class ChatUpdate(BaseModel):
    photo: Optional[str]


class MessageOut(BaseModel):
    user_id: int
    id: int
    content: Optional[str]
    file_path: Optional[str]
    timestamp: datetime.datetime
    reactions: List["ReactionOut"]
    read_id: List[int]

    class Config:
        from_attributes = True

    @field_validator('timestamp')
    @classmethod
    def set_timestamp_to_utc(cls, v):
        if v.tzinfo is None:
            return v.replace(tzinfo=datetime.timezone.utc)
        return v.astimezone(datetime.timezone.utc)


class ChatInSocket(ChatBase):
    id: int
    photo: Optional[str]

    class Config:
        from_attributes = True


class ReactionOut(BaseModel):
    content: int
    sender: UserSearchResult

    class Config:
        from_attributes = True


class ChatWithMessages(ChatOut):
    pass


class UserProjects(BaseModel):
    projects: List[ProjectOut]

    class Config:
        from_attributes = True


class UserChats(BaseModel):
    chats: List[ChatOut]

    class Config:
        from_attributes = True
