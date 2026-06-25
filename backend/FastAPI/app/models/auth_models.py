from pydantic import BaseModel


class RegisterRequest(BaseModel):  # Register class for json body
    username: str
    password: str


class LoginRequest(BaseModel):  # Login class for json body
    username: str
    password: str
