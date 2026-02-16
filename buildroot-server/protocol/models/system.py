from pydantic import BaseModel


class Heartbeat(BaseModel):
    pass


class SystemStatus(BaseModel):
    cpu_usage: float = 0.0
    mem_used: int = 0
    mem_total: int = 0
    load_1min: float = 0.0
    request_id: str | None = None


class LogUpload(BaseModel):
    filepath: str = ""
    chunk: int | None = None
    total_chunks: int = 1
    line: str = ""
    lines: int = 0


class ScriptRecv(BaseModel):
    script_id: str
    content: str
    execute: bool = False


class ScriptResult(BaseModel):
    script_id: str
    exit_code: int = -1
    success: bool = False
    output: str = ""
