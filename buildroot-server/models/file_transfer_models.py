import time
from pydantic import BaseModel, Field, field_serializer
from typing import Set, List


class FileTransferSession(BaseModel):
    transfer_id: str
    device_id: str
    filename: str
    filepath: str
    file_size: int = Field(gt=0)
    direction: str = Field(pattern="^(upload|download)$")
    chunk_size: int = Field(gt=0)
    total_chunks: int = Field(ge=0)
    received_chunks: Set[int] = set()
    retry_count: dict = {}
    start_time: float = Field(default_factory=time.time)
    last_activity: float = Field(default_factory=time.time)
    checksum: str = ""

    def get_progress(self) -> float:
        if self.total_chunks == 0:
            return 0.0
        return len(self.received_chunks) / self.total_chunks

    def get_missing_chunks(self) -> List[int]:
        return [i for i in range(self.total_chunks) if i not in self.received_chunks]

    @field_serializer("received_chunks")
    def serialize_received_chunks(self, value: Set[int]) -> List[int]:
        return list(value)
