from agentforge import Forge

forge = Forge.from_yaml("agents.yaml")
result = forge.run("The rise of AI agents in software development")
print(result.output)
print(f"\nTotal cost: ${result.cost.total_cost:.4f}")
print(f"Duration: {result.duration:.1f}s")
