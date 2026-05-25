import os
from mem0 import Memory

# Mem0's Gemini provider reads GOOGLE_API_KEY, not GEMINI_API_KEY.
# Mirror it so the rest of the book's env stays consistent.
os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

config = {
    "llm": {
        "provider": "gemini",
        "config": {
            "model": "gemini-2.5-flash",
            "temperature": 0.1,
            "max_tokens": 2000,
        },
    },
    "embedder": {
        "provider": "huggingface",
        "config": {
            "model": "sentence-transformers/all-MiniLM-L6-v2",
        },
    },
    "vector_store": {
        "provider": "chroma",
        "config": {
            "collection_name": "agent_memory",
            "path": "./chroma_db",
        },
    },
}

m = Memory.from_config(config)

messages = [
    {"role": "user", "content": "Hi, I'm Alice. I avoid peanuts."},
    {"role": "assistant", "content": "Noted. I'll keep that in mind."}
]
m.add(messages, user_id="alice")

results = m.search("what do you know about Alice?",
                   filters={"user_id": "alice"})
for r in results["results"]:
    print(r["memory"])
