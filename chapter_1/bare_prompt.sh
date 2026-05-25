#!/usr/bin/env bash
# Chapter 1, Step 3 — bare prompt, no system instruction
# Demonstrates a single-turn Gemini call with no steering.
# The model chooses its own tone, length, and format.

curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent" \
  -H "x-goog-api-key: $GEMINI_API_KEY" \
  -H "Content-Type: application/json" \
  -X POST \
  -d '{
    "contents": [
      { "parts": [ { "text": "What is the capital of India?" } ] }
    ]
  }'
