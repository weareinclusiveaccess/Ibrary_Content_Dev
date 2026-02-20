from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from pydantic.dataclasses import dataclass
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal, Optional,List, Dict, Any
from dotenv import load_dotenv

class OpenAISettings(BaseSettings):
    api_key: str = Field(..., env="OPENAI_API_KEY")
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    
    
class openAIInferenceSettings(BaseSettings):
    temperature: float = Field(default=0.7, ge=0.0, le=1.0)
    model: str = Field(..., description="The model to use for the OpenAI API")
    max_tokens: int = Field(default=1000, ge=1, le=4096)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    frequency_penalty: float = Field(default=0.0, ge=0.0, le=2.0)
    presence_penalty: float = Field(default=0.0, ge=0.0, le=2.0)
    n: int = Field(default=1, ge=1, le=10)
    stop: list[str] = Field(default=[], description="List of strings to stop the generation")
    stream: bool = Field(default=False, description="Whether to stream the response")
    


