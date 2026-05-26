import os
import re
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def clean_voice_search_answer(text: str) -> str:
    source_names = (
        "Reuters",
        "AP News",
        "Associated Press",
        "BBC",
        "CNN",
        "The Guardian",
        "The Hindu",
        "Times of India",
        "NDTV",
        "Al Jazeera",
        "Bloomberg",
    )

    text = re.sub(r"[^]*", "", text)
    text = re.sub(r"【[^】]*】", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"https?://\S+|www\.\S+", "", text)
    text = re.sub(
        r"\b[\w.-]+\.(?:com|org|net|in|io|co|gov|edu)(?:/[^\s]*)?",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\b\S*/\S+\b", "", text)

    cleaned_lines = []
    for line in text.splitlines():
        line = re.sub(r"^\s*[-*•]\s*", "", line)
        for source in source_names:
            source_pattern = re.escape(source)
            line = re.sub(rf"\s*[-–—]\s*{source_pattern}\s*$", "", line, flags=re.IGNORECASE)
            line = re.sub(rf"\s*\({source_pattern}\)\s*", " ", line, flags=re.IGNORECASE)
            line = re.sub(rf"\s+from\s+{source_pattern}\s*\.?$", ".", line, flags=re.IGNORECASE)
        line = re.sub(r"\s+", " ", line).strip(" -")
        if line and not re.match(r"^(sources?|links?|references?)\s*:", line, re.IGNORECASE):
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


def ask_with_web_search(query: str) -> str:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    response = client.responses.create(
        model="gpt-4.1-mini",
        tools=[{"type": "web_search"}],
        max_output_tokens=350,
        input=(
            "Answer for spoken voice output.\n"
            "Rules:\n"
            "- Do not include URLs, domains, source names, citation markers, markdown links, brackets, or web paths.\n"
            "- If the user asks for news or search results, give each item as exactly one short sentence on its own line.\n"
            "- Keep the whole answer brief and natural to hear.\n\n"
            f"User asked: {query}"
        ),
    )

    return clean_voice_search_answer(response.output_text)
