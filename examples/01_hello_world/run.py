from agentforge import Forge

forge = Forge.from_yaml("agents.yaml")
result = forge.run("What are the top 3 programming languages in 2026?")
print(result.output)
