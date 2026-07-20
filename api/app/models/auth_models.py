from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):  # Register class for json body
    username: str
    password: str = Field(min_length=1)


class LoginRequest(BaseModel):  # Login class for json body
    username: str
    password: str
