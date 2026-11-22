import os
from dotenv import load_dotenv
from groq import Groq
 
load_dotenv()
client = Groq(api_key=os.environ["GROQ_API_KEY"])
reply = client.chat.completions.create(
    model=os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b"),
    messages=[{"role": "user", "content": "Reply with the single word: ready"}],
)
print(reply.choices[0].message.content)
