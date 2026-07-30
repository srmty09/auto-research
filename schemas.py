from pydantic import BaseModel
from typing import Optional


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    username: str

    class Config:
        from_attributes = True


class RunRequest(BaseModel):
    goal: str
    max_steps: int = 15
    model: str = ""


class FollowUpRequest(BaseModel):
    session_id: str
    message: str
    max_steps: int = 10
    model: str = ""


class SessionSummary(BaseModel):
    session_id: str
    goal: str
    success: bool
    steps: int
    time: float
    timestamp: str

    class Config:
        from_attributes = True


class SessionDetail(BaseModel):
    session_id: str
    goal: str
    success: bool
    steps: int
    time: float
    timestamp: str
    final_answer: str
    log: list

    class Config:
        from_attributes = True


class RunResponse(BaseModel):
    session_id: str
    success: bool
    final_answer: str
    steps: int
    time: float
    log: list


class FollowUpResponse(BaseModel):
    success: bool
    final_answer: str
    steps: int
    log: list
