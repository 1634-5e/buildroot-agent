from pydantic import BaseModel
from typing import List, Dict


class FileRequest(BaseModel):
    action: str = ""
    filepath: str = ""
    lines: int = 50
    offset: int = 0


class FileData(BaseModel):
    filepath: str = ""
    content: str = ""
    request_id: str = ""
    chunk_index: int = 0


class FileListRequest(BaseModel):
    request_id: str = ""
    path: str = ""


class FileListResponse(BaseModel):
    request_id: str = ""
    files: List[Dict[str, str]] = []


class FileUploadStart(BaseModel):
    filename: str = ""
    file_size: int = 0
    checksum: str = ""
    resume_transfer_id: str = ""


class FileUploadData(BaseModel):
    transfer_id: str = ""
    chunk_index: int = -1
    chunk_data: str = ""


class FileUploadAck(BaseModel):
    transfer_id: str = ""
    chunk_index: int = -1
    success: bool = False
    message: str = ""
    chunk_size: int = 0
    total_chunks: int = 0
    received_chunks: List[int] = []
    resume: bool = False


class FileUploadComplete(BaseModel):
    transfer_id: str = ""
    success: bool = False
    filepath: str = ""
    error: str = ""


class FileDownloadRequest(BaseModel):
    action: str = ""
    file_path: str = ""
    offset: int = 0
    chunk_size: int = 16384
    request_id: str = ""


class FileDownloadData(BaseModel):
    action: str = ""
    file_path: str = ""
    offset: int = 0
    data: str = ""
    size: int = 0
    is_final: bool = False
    total_size: int = 0
    request_id: str = ""


class DownloadPackage(BaseModel):
    request_id: str = ""
    chunk_index: int = 0
    total_chunks: int = 1
    content: str = ""
    filename: str = "unknown"
    size: int = 0
    is_first: bool = False
    is_last: bool = False
