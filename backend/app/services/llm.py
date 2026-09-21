import os
from typing import List, Optional, Dict
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=api_key) if api_key else None

def generate_answer(question: str, context_chunks: list, history: Optional[List[Dict[str, str]]] = None) -> str:
    if not client or not api_key:
        return "Groq API Key is missing. Please check your .env file."

    # 1. Context Formatting
    if context_chunks:
        context = "\n\n".join([
            f"[Source: Page {c.get('page_number', 1)}]\n{c.get('content', '')}"
            for c in context_chunks
        ])
    else:
        context = "No direct document context found."

    # 2. System Instructions
    system_prompt = f"""You are TechStore's AI support assistant.

Instructions:
1. Answer document-specific queries using the Context provided below.
2. If the user asks for follow-up adjustments (e.g., "translate to Roman Urdu", "explain simply", "summarize") or general chat ("hi", "thanks"), rely on the conversation history to respond naturally.
3. If the user asks a specific question about product or account data that is not available in context or history, politely state that you couldn't find that information. Do not invent facts.

Context:
{context}"""

    # 3. Message Assembly
    messages = [{"role": "system", "content": system_prompt}]

    if history:
        for msg in history:
            role = "assistant" if msg.get("role") == "assistant" else "user"
            messages.append({"role": role, "content": msg.get("content", "")})

    messages.append({"role": "user", "content": question})

    # 4. Fallback Model Execution
    # Standard active Groq models:
    available_models = ["openai/gpt-oss-20b", "openai/gpt-oss-120b"]
    
    last_error = None
    for model_name in available_models:
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.2
            )
            return response.choices[0].message.content
        except Exception as e:
            last_error = e
            print(f"[GROQ MODEL FAILED ({model_name})]: {e}")
            continue

    return f"Groq Error: All model endpoints failed. Details: {str(last_error)}"