import os

import httpx
from dotenv import load_dotenv
from google.adk.agents import LlmAgent

load_dotenv()

MODEL_NAME = "gemini-2.5-flash"


def add(a: float, b: float) -> dict:
    """Add two numbers and return the sum."""
    return {"status": "ok", "result": a + b}


def multiply(a: float, b: float) -> dict:
    """Multiply two numbers and return the product."""
    return {"status": "ok", "result": a * b}


def subtract(a: float, b: float) -> dict:
    """Subtract b from a and return the difference."""
    return {"status": "ok", "result": a - b}


async def get_weather(city: str) -> dict:
    """Get the current temperature in Celsius for a named city."""
    async with httpx.AsyncClient(timeout=10) as http:
        geo = await http.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1},
        )
        hits = geo.json().get("results") or []
        if not hits:
            return {"status": "error", "message": f"unknown city: {city}"}
        lat, lon = hits[0]["latitude"], hits[0]["longitude"]
        wx = await http.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon, "current": "temperature_2m"},
        )
        temp = wx.json()["current"]["temperature_2m"]
        return {"status": "ok", "city": city, "temperature_c": temp}


root_agent = LlmAgent(
    name="workshop_agent",
    model=MODEL_NAME,
    description="Does arithmetic and weather lookups.",
    instruction=(
        "You are a helpful assistant. "
        "Use the calculator tools (add, subtract, multiply) for arithmetic, "
        "and get_weather for current temperature in a city. "
        "When you have the answer, respond in one short sentence."
    ),
    tools=[add, multiply, subtract, get_weather],
)
