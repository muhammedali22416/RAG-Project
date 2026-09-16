from app.database import supabase
from app.services.embedder import generate_embedding

def retrieve_relevant_chunks(question: str, match_count: int = 5):
    query_embedding = generate_embedding(question)

    result = supabase.rpc("match_document_chunks", {
        "query_embedding": query_embedding,
        "match_count": match_count
    }).execute()

    return result.data