
import os
with open('erp_client.py', 'r', encoding='utf-8') as f:
    data = f.read()

# Replace literal backslash-quote with quote
data = data.replace('\\\"', '\"')

with open('erp_client.py', 'w', encoding='utf-8') as f:
    f.write(data)
print("Cleaned erp_client.py")
