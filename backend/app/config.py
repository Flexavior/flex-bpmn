from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

APP_NAME = os.getenv("APP_NAME", "FXV BPMN")
ENV = os.getenv("ENV", "development").strip().lower()

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "auto").strip().lower()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:9b")

OMNIROUTE_API_KEY = os.getenv("OMNIROUTE_API_KEY", "")
OMNIROUTE_BASE_URL = os.getenv("OMNIROUTE_BASE_URL", "https://api.omniroute.ai/v1")
OMNIROUTE_MODEL = os.getenv("OMNIROUTE_MODEL", "auto")
OMNIROUTE_PREFERRED_MODELS = [
    m.strip()
    for m in os.getenv("OMNIROUTE_PREFERRED_MODELS", "").split(",")
    if m.strip()
]

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "auto")
OPENROUTER_PREFERRED_MODELS = [
    m.strip()
    for m in os.getenv("OPENROUTER_PREFERRED_MODELS", "").split(",")
    if m.strip()
]

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_PREFERRED_MODELS = [
    m.strip()
    for m in os.getenv("OPENAI_PREFERRED_MODELS", "").split(",")
    if m.strip()
]

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_BASE_URL = os.getenv(
    "GEMINI_BASE_URL",
    "https://generativelanguage.googleapis.com/v1beta",
)
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "auto")
GEMINI_PREFERRED_MODELS = [
    m.strip()
    for m in os.getenv(
        "GEMINI_PREFERRED_MODELS",
        "gemini-2.0-flash,gemini-2.5-flash,gemini-flash-latest,gemini-1.5-flash",
    ).split(",")
    if m.strip()
]

OUTPUT_FOLDER = BASE_DIR / os.getenv("OUTPUT_FOLDER", "app/generated")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

CORS_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if o.strip()
]

CHAT_RATE_LIMIT = int(os.getenv("CHAT_RATE_LIMIT", "8"))
CHAT_RATE_WINDOW_S = float(os.getenv("CHAT_RATE_WINDOW_S", "60"))
PROMPT_MAX_CHARS = int(os.getenv("PROMPT_MAX_CHARS", "4000"))
TRUST_PROXY = os.getenv("TRUST_PROXY", "false").strip().lower() in ("1", "true", "yes")

CAMUNDA_BASE_URL = os.getenv("CAMUNDA_BASE_URL", "http://127.0.0.1:8080")
CAMUNDA_DEPLOY_ENABLED = os.getenv("CAMUNDA_DEPLOY_ENABLED", "false").strip().lower() in (
    "1",
    "true",
    "yes",
)
CAMUNDA_TOKEN = os.getenv("CAMUNDA_TOKEN", "")
EXAMPLES_DIR = Path(os.getenv("EXAMPLES_DIR", str(BASE_DIR.parent / "examples")))
CATALOG_PATH = Path(os.getenv("CATALOG_PATH", str(BASE_DIR.parent / "docs" / "prd_catalog.json")))
