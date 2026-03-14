from pydantic import BaseModel


class PtyCreate(BaseModel):
    session_id: int
    rows: int = 24
    cols: int = 80


class PtyData(BaseModel):
    session_id: int
    data: str


class PtyResize(BaseModel):
    session_id: int
    rows: int = 24
    cols: int = 80


class PtyClose(BaseModel):
    session_id: int
    reason: str = "unknown"
