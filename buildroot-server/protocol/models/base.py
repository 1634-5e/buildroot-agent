from pydantic import BaseModel, Field


class BaseMessage(BaseModel):
    request_id: str | None = Field(default=None)
    device_id: str | None = Field(default=None)

    class Config:
        extra = "allow"
