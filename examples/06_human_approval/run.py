from agentforge import Forge

forge = Forge.from_yaml("agents.yaml")
result = forge.run("Write a company-wide email announcing our new remote work policy")
print(result.output)
