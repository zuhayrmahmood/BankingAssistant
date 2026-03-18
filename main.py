import dspy
from litellm import api_base

print("Welcome to the LLM-Based Teller AI Assistant!")
print("================================================")
print("Loading...")


lm = dspy.LM(model="ollama_chat/llama3.1:8b", api_base="http://localhost:11434", api_key='')
dspy.configure(lm=lm)









