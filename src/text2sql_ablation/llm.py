"""Gemini client: uses GEMINI_API_KEY if set, otherwise Vertex AI via ADC."""
from __future__ import annotations

import os
import re

from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential

_SQL_BLOCK = re.compile(r"```[a-zA-Z]*\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def make_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        return genai.Client(api_key=api_key)
    return genai.Client(
        vertexai=True,
        project=os.environ["GCP_PROJECT_ID"],
        location=os.getenv("GCP_LOCATION", "us-central1"),
    )


def extract_sql(text: str) -> str:
    m = _SQL_BLOCK.search(text or "")
    return (m.group(1) if m else text or "").strip().rstrip(";")


@retry(stop=stop_after_attempt(6), wait=wait_exponential(min=2, max=60))
def generate_text(client: genai.Client, model: str, prompt: str, temperature: float = 0.0) -> str:
    resp = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=temperature),
    )
    return (resp.text or "").strip()


def generate_sql(client: genai.Client, model: str, prompt: str, temperature: float = 0.0) -> str:
    return extract_sql(generate_text(client, model, prompt, temperature))
