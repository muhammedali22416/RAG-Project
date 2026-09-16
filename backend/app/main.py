import os
import shutil
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.database import supabase
from app.services.pdf_extractor import extract_text_from_pdf
from app.services.chunker import chunk_text
from app.services.embedder import generate_embedding
from app.services.retriever import retrieve_relevant_chunks
from app.services.llm import generate_answer

app = FastAPI(title="TechStore AI Knowledge Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. Chat Message & Request Schemas
class MessageItem(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    question: str
    history: Optional[List[MessageItem]] = []


@app.get("/")
def root():
    return {"status": "TechStore AI backend running"}

@app.get("/test-db")
def test_db():
    result = supabase.table("documents").select("*").execute()
    return {"data": result.data}

@app.post("/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    os.makedirs("uploads", exist_ok=True)
    file_path = f"uploads/{file.filename}"
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    pages_data = extract_text_from_pdf(file_path)

    doc_result = supabase.table("documents").insert({
        "name": file.filename,
        "category": "Uncategorized",
        "file_path": file_path,
        "page_count": len(pages_data),
        "status": "processing"
    }).execute()

    document_id = doc_result.data[0]["id"]

    chunk_index = 0
    chunks_to_insert = []

    for page in pages_data:
        chunks = chunk_text(page["text"])
        for chunk in chunks:
            embedding = generate_embedding(chunk)
            chunks_to_insert.append({
                "document_id": document_id,
                "content": chunk,
                "page_number": page["page_number"],
                "chunk_index": chunk_index,
                "embedding": embedding
            })
            chunk_index += 1

    if chunks_to_insert:
        supabase.table("document_chunks").insert(chunks_to_insert).execute()

    supabase.table("documents").update({"status": "processed"}).eq("id", document_id).execute()

    return {"message": "Document processed successfully", "document_id": document_id}

@app.post("/chat")
async def chat(request: ChatRequest):
    if not request.question.strip():
        return {"error": "Question cannot be empty"}

    # Greetings / short chat check
    user_q = request.question.strip().lower()
    is_greeting = user_q in ["hi", "hello", "hey", "salam", "aoa", "thanks", "thank you"]

    # Retrieval only if not a basic greeting
    chunks = [] if is_greeting else (retrieve_relevant_chunks(request.question) or [])

    formatted_history = []
    if request.history:
        for msg in request.history:
            if hasattr(msg, "model_dump"):
                formatted_history.append(msg.model_dump())
            else:
                formatted_history.append(msg.dict())

    answer = generate_answer(
        question=request.question,
        context_chunks=chunks,
        history=formatted_history
    )

    sources = []
    if chunks:
        doc_ids = list(set(c["document_id"] for c in chunks if "document_id" in c))
        if doc_ids:
            docs = supabase.table("documents").select("id, name").in_("id", doc_ids).execute()
            doc_map = {d["id"]: d["name"] for d in docs.data}

            seen_sources = set()
            for c in chunks:
                doc_name = doc_map.get(c.get("document_id"), "unknown")
                page_num = c.get("page_number", 1)
                source_key = (doc_name, page_num)
                if source_key not in seen_sources:
                    seen_sources.add(source_key)
                    sources.append({"document": doc_name, "page": page_num})

    return {"answer": answer, "sources": sources}