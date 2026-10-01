from fastapi import APIRouter
from typing import Dict, Any
from pydantic import BaseModel

router = APIRouter(prefix="/api/agent", tags=["Agent"])


class ChatMessageRequest(BaseModel):
    message: str
    conversation_id: str = "conv_default"


from ..agent.agent import agent

@router.post("/chat")
async def chat_with_agent(req: ChatMessageRequest) -> Dict[str, Any]:
    """Agentic AI interaction endpoint (Phase 4)."""
    return await agent.chat(req.message, req.conversation_id)
