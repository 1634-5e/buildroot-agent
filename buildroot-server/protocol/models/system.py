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




class PingResult(BaseModel):
    ip: str = ""
    status: int = 0
    avg_time: float = 0.0
    min_time: float = 0.0
    max_time: float = 0.0
    packet_loss: float = 0.0
    packets_sent: int = 0
    packets_received: int = 0
    timestamp: int = 0


class PingStatus(BaseModel):
    timestamp: int = 0
    results: list[PingResult] = []