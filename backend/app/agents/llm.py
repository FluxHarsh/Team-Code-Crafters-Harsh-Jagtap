"""
Single place every agent node gets its reasoning-model client from.
Provider-agnostic on purpose: which LLM you're running is entirely an
environment concern, not a code concern.

Configure via three env vars (see .env.example):
  LLM_PROVIDER    "openai" | "gemini"
  LLM_API_KEY     the API key for whichever provider you picked
  LLM_MODEL_NAME  e.g. "gpt-4o" for OpenAI, "gemini-2.0-flash" for Gemini

Every node (Supervisor, Intake, Scope Critic, Planner, GitHub Watcher
summarization, Risk Watcher, Reprioritizer, Pitch Agent, Team Assistant)
calls get_chat_model() and never touches provider-specific code -- switch
providers by editing .env, not app code.

Kept separate from OPENAI_API_KEY / OPENAI_EMBEDDINGS_URL in
app/services/embeddings.py, which is a fixed OpenAI-only embeddings call
(Section 3.2 / Phase 11) and is unaffected by LLM_PROVIDER.
"""

from functools import lru_cache
from typing import Union

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from app.config import get_settings

ChatModel = Union[ChatOpenAI, ChatGoogleGenerativeAI]

SUPPORTED_PROVIDERS = {"openai", "gemini"}


@lru_cache(maxsize=4)
def get_chat_model(*, temperature: float = 0.3) -> ChatModel:
    settings = get_settings()
    provider = (settings.llm_provider or "").strip().lower()

    if not settings.llm_api_key:
        raise RuntimeError(
            "LLM_API_KEY is not set. Configure LLM_PROVIDER, LLM_API_KEY, "
            "and LLM_MODEL_NAME in your environment (see .env.example)."
        )

    if provider == "openai":
        return ChatOpenAI(
            model=settings.llm_model_name,
            api_key=settings.llm_api_key,
            temperature=temperature,
            max_tokens=1024,
            timeout=30,
        )

    if provider == "gemini":
        return ChatGoogleGenerativeAI(
            model=settings.llm_model_name,
            google_api_key=settings.llm_api_key,
            temperature=temperature,
            max_output_tokens=1024,
            timeout=30,
        )

    raise ValueError(
        f"Unsupported LLM_PROVIDER '{settings.llm_provider}'. "
        f"Must be one of: {sorted(SUPPORTED_PROVIDERS)}."
    )
