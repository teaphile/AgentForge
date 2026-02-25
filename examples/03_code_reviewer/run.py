from agentforge import Forge

code_to_review = '''
def process_payment(user_id, amount):
    import sqlite3
    conn = sqlite3.connect("payments.db")
    cursor = conn.cursor()
    query = f"INSERT INTO payments (user_id, amount) VALUES ({user_id}, {amount})"
    cursor.execute(query)
    conn.commit()
    return True
'''

forge = Forge.from_yaml("agents.yaml")
result = forge.run(code_to_review)
print(result.output)
