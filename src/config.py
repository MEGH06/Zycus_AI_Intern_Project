import os
from pydantic import BaseModel, field_validator

SUPPORTED_PROVIDERS = {"local", "groq", "openai"}


class AppConfig(BaseModel):
    data_dir: str = "data"
    kb_dir: str = "knowledge-base"
    llm_provider: str = "local"
    llm_model: str = "llama3-8b-8192"
    llm_temperature: float = 0.0
    openai_api_key: str | None = None
    groq_api_key: str | None = None

    @field_validator("llm_temperature")
    @classmethod
    def temperature_must_be_zero(cls, v: float) -> float:
        if v != 0.0:
            raise ValueError(
                f"llm_temperature must be 0.0 for deterministic output; got {v}. "
                "Override only for manual demo runs."
            )
        return v

    @field_validator("llm_provider")
    @classmethod
    def provider_must_be_known(cls, v: str) -> str:
        if v not in SUPPORTED_PROVIDERS:
            raise ValueError(
                f"llm_provider '{v}' is not supported. "
                f"Choose one of: {sorted(SUPPORTED_PROVIDERS)}"
            )
        return v

    @property
    def active_api_key(self) -> str | None:
        if self.llm_provider == "groq":
            return self.groq_api_key
        if self.llm_provider == "openai":
            return self.openai_api_key
        return None


def load_config() -> AppConfig:
    raw_temp = os.getenv("LLM_TEMPERATURE", "0")
    try:
        temp = float(raw_temp)
    except ValueError:
        temp = 0.0

    return AppConfig(
        data_dir=os.getenv("DATA_DIR", "data"),
        kb_dir=os.getenv("KB_DIR", "knowledge-base"),
        llm_provider=os.getenv("LLM_PROVIDER", "local"),
        llm_model=os.getenv("LLM_MODEL", "llama3-8b-8192"),
        llm_temperature=temp,
        openai_api_key=os.getenv("OPENAI_API_KEY") or None,
        groq_api_key=os.getenv("GROQ_API_KEY") or None,
    )
