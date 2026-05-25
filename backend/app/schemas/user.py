from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    username: str = Field(min_length=2, max_length=64, examples=["teacher_zhang"])
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    role: str = Field(default="teacher", pattern="^(admin|teacher|journalist|student|researcher|editor|developer)$")


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    quota_remaining: int

    model_config = {"from_attributes": True}
