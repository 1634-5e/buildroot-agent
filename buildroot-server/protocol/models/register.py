from pydantic import BaseModel


class RegisterRequest(BaseModel):
    device_id: str
    version: str = "unknown"


class RegisterResult(BaseModel):
    success: bool
    message: str = ""
