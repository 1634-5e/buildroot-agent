"""
WebSocket 认证模块
简单的 token 认证机制
"""

import secrets
import asyncio
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Token 存储（生产环境应使用 Redis 或数据库）
# Token 有效期 24 小时
VALID_TOKENS: dict[str, tuple[str, float]] = {}  # token -> (user_id, created_at)
TOKEN_EXPIRY = 24 * 60 * 60  # 24 hours


def generate_token(user_id: str = "anonymous") -> str:
    """生成认证 token"""
    token = secrets.token_urlsafe(32)
    try:
        current_time = asyncio.get_event_loop().time()
    except RuntimeError:
        import time
        current_time = time.time()
    VALID_TOKENS[token] = (user_id, current_time)
    logger.info(f"[AUTH] 生成 token: {token[:8]}... for user: {user_id}")
    return token


def validate_token(token: str) -> Optional[str]:
    """验证 token，返回 user_id 或 None"""
    if not token:
        return None
    
    # 清理过期 token
    try:
        current_time = asyncio.get_event_loop().time()
    except RuntimeError:
        import time
        current_time = time.time()
    
    expired = [t for t, (_, created) in VALID_TOKENS.items() 
               if current_time - created > TOKEN_EXPIRY]
    for t in expired:
        del VALID_TOKENS[t]
    
    if token in VALID_TOKENS:
        user_id, _ = VALID_TOKENS[token]
        return user_id
    return None


def revoke_token(token: str) -> bool:
    """撤销 token"""
    if token in VALID_TOKENS:
        del VALID_TOKENS[token]
        logger.info(f"[AUTH] 撤销 token: {token[:8]}...")
        return True
    return False