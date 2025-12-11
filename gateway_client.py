import os
from dotenv import load_dotenv
load_dotenv()
import requests
from datetime import datetime


MEMMACHINE_PORT  = os.getenv("MEMORY_SERVER_URL")
BACKEND_API_KEY = os.getenv("BACKEND_API_KEY")

PROMPT = """You are a helpful AI assistant. Use the provided context and profile information to answer the user's question accurately and helpfully.

<CURRENT_DATE>
{current_date}
</CURRENT_DATE>

Instructions:
- Use the PROFILE and CONTEXT data provided to answer the user's question
- Be conversational and helpful in your responses
- If you don't have enough information to answer completely, say so and suggest what additional information might be helpful
- If the context contains relevant information, use it to provide a comprehensive answer
- If no relevant context is available, let the user know and offer to help in other ways
- Be concise but thorough in your responses
- Use markdown formatting when appropriate to make your response clear and readable

Data Guidelines:
- Don't invent information that isn't in the provided context
- If information is missing or unclear, acknowledge this
- Prioritize the most recent and relevant information when available
- If there are conflicting pieces of information, mention this and explain the differences

Response Format:
- Directly answer the user's question, without showing your thought process
- Provide supporting details from the context when available
- Use bullet points or numbered lists when appropriate
- End with any relevant follow-up questions or suggestions"""

def ingest_and_rewrite(user_id: str, query: str) -> str:
    """Pass a raw user message through the memory server and get context-aware response."""
    print("entered ingest_and_rewrite")
    headers = {
        "user-id": user_id,
        "group-id": user_id,  
        "session-id": user_id,
        "agent-id": "agent",
    }
    
    # Add API key if configured
    if BACKEND_API_KEY:
        headers["x-api-key"] = BACKEND_API_KEY
    
    requests.post(
        f"{MEMMACHINE_PORT}/v1/memories",
        json={"producer": user_id, "produced_for": "agent", "episode_content": query},
        headers=headers,
        timeout=5,
    )
    
    resp = requests.post(
        f"{MEMMACHINE_PORT}/v1/memories/search",
        headers=headers,
        json={"query": query},
        timeout=1000,
    )
    resp.raise_for_status()

    return PROMPT + "\n\n" + resp.text + "\n\n" + "User Query: " + query


def get_memories(user_id: str) -> dict:
    """Fetch all memories for a given user_id"""
    headers = {
        "user-id": user_id,
        "group-id": user_id,  
        "session-id": user_id,
        "agent-id": "agent",
    }
    
    # Add API key if configured
    if BACKEND_API_KEY:
        headers["x-api-key"] = BACKEND_API_KEY
    
    try:
        resp = requests.get(
            f"{MEMMACHINE_PORT}/v1/memories",
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching memories: {e}")
        return {}


def ingest_memories(user_id: str, memories_text: str) -> bool:
    """Ingest imported memories into MemMachine system.
    
    Args:
        user_id: The user identifier
        memories_text: Text containing memories/conversations to ingest
        
    Returns:
        True if successful, False otherwise
    """
    headers = {
        "user-id": user_id,
        "group-id": user_id,  
        "session-id": user_id,
        "agent-id": "agent",
    }
    
    # Add API key if configured
    if BACKEND_API_KEY:
        headers["x-api-key"] = BACKEND_API_KEY
    
    try:
        # Ingest the memories as an episode
        resp = requests.post(
            f"{MEMMACHINE_PORT}/v1/memories",
            json={
                "producer": user_id,
                "produced_for": "agent",
                "episode_content": memories_text
            },
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error ingesting memories: {e}")
        return False


def delete_profile(user_id: str) -> bool:
    """Delete the session for the given user_id"""
    headers = {
        "user-id": user_id,
        "group-id": user_id,  
        "session-id": user_id,
        "agent-id": "agent",
    }
    
    # Add API key if configured
    if BACKEND_API_KEY:
        headers["x-api-key"] = BACKEND_API_KEY
    
    requests.delete(f"{MEMMACHINE_PORT}/v1/memories", headers=headers, json={})
    return True