"""Team of agents that collaborate on a workflow."""

from __future__ import annotations

from agentforge.core.agent import Agent


class Team:

    def __init__(self, name: str, agents: dict[str, Agent], description: str = ""):
        self.name = name
        self.agents = agents  # name → Agent
        self.description = description

    def get_agent(self, name: str) -> Agent:
        if name not in self.agents:
            available = ", ".join(sorted(self.agents.keys()))
            raise KeyError(
                f"Agent '{name}' not found in team '{self.name}'. "
                f"Available agents: {available}"
            )
        return self.agents[name]

    def list_agents(self) -> list[str]:
        return list(self.agents.keys())

    @classmethod
    def from_config(cls, config: dict) -> "Team":
        team_config = config.get("team", {})
        agents_config = config.get("agents", {})

        agents = {}
        for agent_name, agent_conf in agents_config.items():
            agents[agent_name] = Agent.from_config(agent_name, agent_conf, team_config)

        return cls(
            name=team_config.get("name", "AgentForge Team"),
            agents=agents,
            description=team_config.get("description", ""),
        )
