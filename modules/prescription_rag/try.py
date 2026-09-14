from langchain_google_genai import ChatGoogleGenerativeAI
import json

llm = ChatGoogleGenerativeAI(
    model="gemini-3.6-flash",
    temperature=0,
)


response = llm.invoke(
    "Explain in one sentence what a drug-drug interaction is."
)
response_json=response.json()
print(response.content[0]["text"])