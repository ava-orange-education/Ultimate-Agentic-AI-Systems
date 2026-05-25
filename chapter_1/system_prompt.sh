#!/usr/bin/env bash
# Chapter 1, Step 4 — same question steered by a system instruction
# The system_instruction field pins role and output format.
# Compare the output to bare_prompt.sh to feel what a system prompt actually does.

curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent" \
  -H "x-goog-api-key: $GEMINI_API_KEY" \
  -H "Content-Type: application/json" \
  -X POST \
  -d '{
    "system_instruction": {
      "parts": [ { "text": "You are a precise geography assistant. Answer in exactly one sentence, then on a new line list one notable historical fact about that capital. Never use bullet points or markdown." } ]
    },
    "contents": [
      { "parts": [ { "text": "What is the capital of India?" } ] }
    ]
  }'
