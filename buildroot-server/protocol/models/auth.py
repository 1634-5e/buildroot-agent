from pydantic import BaseModel


class AuthRequest(BaseModel):
    device_id: str
    version: str = "unknown"


class AuthResult(BaseModel):
    success: bool
    message: str = ""
