from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    answer: str
    provider: str
    suggested_actions: list[str]


class IncidentAnalysis(BaseModel):
    summary: str
    root_cause_hypotheses: list[str]
    recommended_actions: list[str]
    provider: str
