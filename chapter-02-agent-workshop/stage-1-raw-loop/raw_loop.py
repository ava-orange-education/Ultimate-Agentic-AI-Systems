import asyncio
import os
import sys

import httpx
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

MODEL_NAME = "gemini-2.5-flash"
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])


async def calculator(expression: str) -> str:
    """Evaluate a basic arithmetic expression like '21 * 7'."""
    allowed = set("0123456789+-*/(). ")
    if not all(c in allowed for c in expression):
        return "error: only numbers and + - * / ( ) are allowed"
    return str(eval(expression, {"__builtins__": {}}, {}))


async def get_weather(city: str) -> str:
    """Look up the current temperature in Celsius for a city."""
    async with httpx.AsyncClient(timeout=10) as http:
        geo = await http.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1},
        )
        hits = geo.json().get("results") or []
        if not hits:
            return f"unknown city: {city}"
        lat, lon = hits[0]["latitude"], hits[0]["longitude"]
        wx = await http.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon, "current": "temperature_2m"},
        )
        return f"{wx.json()['current']['temperature_2m']} C in {city}"


TOOLS = {"calculator": calculator, "get_weather": get_weather}

TOOL_SCHEMA = types.Tool(
    function_declarations=[
        {
            "name": "calculator",
            "description": "Evaluate a basic arithmetic expression.",
            "parameters": {
                "type": "object",
                "properties": {"expression": {"type": "string"}},
                "required": ["expression"],
            },
        },
        {
            "name": "get_weather",
            "description": "Get the current temperature in Celsius for a city.",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        },
    ]
)


async def run_agent(user_message: str, max_steps: int = 6) -> str:
    history = [{"role": "user", "parts": [{"text": user_message}]}]
    for _ in range(max_steps):
        resp = await client.aio.models.generate_content(
            model=MODEL_NAME,
            contents=history,
            config=types.GenerateContentConfig(tools=[TOOL_SCHEMA]),
        )
        part = resp.candidates[0].content.parts[0]
        if part.function_call:
            call = part.function_call
            tool_fn = TOOLS[call.name]
            result = await tool_fn(**dict(call.args))
            history.append({"role": "model", "parts": [part]})
            history.append(
                {
                    "role": "user",
                    "parts": [
                        {
                            "function_response": {
                                "name": call.name,
                                "response": {"result": result},
                            }
                        }
                    ],
                }
            )
            continue
        return part.text
    return "step limit reached without a final answer"


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "What is 21 * 19?"
    print(asyncio.run(run_agent(q)))
