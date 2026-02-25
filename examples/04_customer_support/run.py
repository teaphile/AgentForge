from agentforge import Forge

ticket = """
I've been charged twice for my subscription this month. The charges appeared 
on my credit card on the 15th and 22nd. This is really frustrating as I've 
been a loyal customer for 3 years. Please fix this immediately and refund 
the duplicate charge. My account email is john@example.com.
"""

forge = Forge.from_yaml("agents.yaml")
result = forge.run(ticket)
print(result.output)
