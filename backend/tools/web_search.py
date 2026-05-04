import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

def ask_with_web_search(query: str) -> str:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    response = client.responses.create(
        model="gpt-4.1-mini",
        tools=[{"type": "web_search"}],
        input=f"Answer briefly for a voice assistant. User asked: {query}",
    )

    return response.output_text