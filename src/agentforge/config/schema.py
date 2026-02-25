"""Pydantic models for YAML config validation."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class MemoryConfig(BaseModel):
    enabled: bool = True
    backend: str = "sqlite"
    path: str = ".agentforge/memory.db"
    shared: bool = True

    @field_validator("backend")
    @classmethod
    def validate_backend(cls, v: str) -> str:
        allowed = ("sqlite", "chromadb", "memory")
        if v not in allowed:
            raise ValueError(f"memory.backend must be one of {allowed}, got '{v}'")
        return v


class ObserveConfig(BaseModel):
    trace: bool = True
    cost_tracking: bool = True
    log_level: str = "info"
    log_format: str = "pretty"

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = ("debug", "info", "warning", "error")
        if v not in allowed:
            raise ValueError(f"log_level must be one of {allowed}, got '{v}'")
        return v

    @field_validator("log_format")
    @classmethod
    def validate_log_format(cls, v: str) -> str:
        allowed = ("pretty", "json")
        if v not in allowed:
            raise ValueError(f"log_format must be one of {allowed}, got '{v}'")
        return v


class ControlConfig(BaseModel):
    dry_run: bool = False
    max_retries: int = 3
    timeout: int = 300
    confidence_threshold: float = 0.4


class TeamConfig(BaseModel):
    name: str
    description: str = ""
    llm: str = "openai/gpt-4o-mini"
    temperature: float = 0.7
    max_tokens: int = 4096
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    observe: ObserveConfig = Field(default_factory=ObserveConfig)
    control: ControlConfig = Field(default_factory=ControlConfig)

    @field_validator("llm")
    @classmethod
    def validate_llm(cls, v: str) -> str:
        if "/" not in v:
            raise ValueError(
                f"llm must be in 'provider/model' format (e.g., 'openai/gpt-4o-mini'), got '{v}'"
            )
        return v

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        if not 0.0 <= v <= 2.0:
            raise ValueError(f"temperature must be between 0.0 and 2.0, got {v}")
        return v


class AgentMemoryConfig(BaseModel):
    enabled: bool = True
    type: str = "short_term"
    recall_limit: int = 10

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        allowed = ("short_term", "long_term")
        if v not in allowed:
            raise ValueError(f"memory.type must be one of {allowed}, got '{v}'")
        return v


class AgentControlConfig(BaseModel):
    require_approval: bool = False
    max_iterations: int = 10
    allowed_actions: list[str] = Field(default_factory=list)
    blocked_actions: list[str] = Field(default_factory=list)


class AgentConfig(BaseModel):
    role: str
    goal: str
    backstory: str = ""
    llm: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    fallback: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    memory: AgentMemoryConfig = Field(default_factory=AgentMemoryConfig)
    control: AgentControlConfig = Field(default_factory=AgentControlConfig)
    instructions: str = ""

    @field_validator("llm")
    @classmethod
    def validate_llm(cls, v: str | None) -> str | None:
        if v is not None and "/" not in v:
            raise ValueError(f"agent llm must be in 'provider/model' format, got '{v}'")
        return v


class StepConfig(BaseModel):
    id: str
    agent: str
    task: str
    output_format: str = "text"
    timeout: Optional[int] = None
    retry_on_fail: Optional[int] = None
    approval_gate: bool = False
    dry_run: Optional[bool] = None
    condition: Optional[str] = None
    save_as: Optional[str] = None
    on_success: Optional[str] = None
    on_fail: Optional[str] = None
    next: Optional[str] = None


class ParallelStepConfig(BaseModel):
    parallel: list[StepConfig]


class WorkflowConfig(BaseModel):
    steps: list[StepConfig | ParallelStepConfig]


class InlineToolParam(BaseModel):
    type: str = "string"
    description: str = ""
    required: bool = False


class InlineToolConfig(BaseModel):
    description: str
    parameters: dict[str, InlineToolParam] = Field(default_factory=dict)
    handler: str  # "module_path:function_name"


class ForgeConfig(BaseModel):
    team: TeamConfig
    agents: dict[str, AgentConfig]
    workflow: WorkflowConfig
    tools: dict[str, InlineToolConfig] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_agent_references(self) -> "ForgeConfig":
        agent_names = set(self.agents.keys())

        for step_item in self.workflow.steps:
            if isinstance(step_item, ParallelStepConfig):
                for s in step_item.parallel:
                    if s.agent not in agent_names:
                        raise ValueError(
                            f"Parallel step '{s.id}' references agent '{s.agent}' "
                            f"which is not defined. Available: {sorted(agent_names)}"
                        )
            elif isinstance(step_item, StepConfig):
                if step_item.agent not in agent_names:
                    raise ValueError(
                        f"Step '{step_item.id}' references agent '{step_item.agent}' "
                        f"which is not defined. Available: {sorted(agent_names)}"
                    )
            elif isinstance(step_item, dict):
                # Fallback for raw dict input before Pydantic coercion
                agent = step_item.get("agent", "")
                if agent and agent not in agent_names:
                    raise ValueError(
                        f"Step references agent '{agent}' "
                        f"which is not defined. Available: {sorted(agent_names)}"
                    )
        return self
