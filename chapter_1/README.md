# Chapter 1 — From API Calls to Autonomous Decision-Making

Hands-on exercises for Chapter 1 of *Ultimate Agentic AI Systems*. You will get a free Gemini API key, set it as an environment variable, and run two `curl` calls that demonstrate exactly what a system prompt does to a model's output.

---

## Step 1 — Create a Gemini API key

1. Open [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) in your browser.
2. Sign in with your Google account. If you use a Google Workspace account your administrator may need to enable AI Studio access.
3. Accept the Terms of Service for Generative AI if prompted.
4. Click **Get API key** (or **Create API key**). A project named `agentic-ai-book` is fine for experimentation.
5. Copy the key immediately and store it in a password manager — treat it like a password, never commit it to git.

> **Free tier note:** As of early 2026, Google AI Studio provides a free tier for Gemini models that does not require a credit card for prototyping, though daily request and token limits apply. Content sent on the free tier may be used to improve Google's products, so do not point a free-tier key at production or sensitive data.

---

## Step 2 — Set the environment variable

Open the terminal you will use for the next steps.

**macOS / Linux**
```bash
export GEMINI_API_KEY="paste-your-key-here"
```

**Windows PowerShell**
```powershell
$env:GEMINI_API_KEY = "paste-your-key-here"
```

The variable lasts for the current shell session. To make it permanent, add the `export` line to your `~/.bashrc` or `~/.zshrc`, or set it as a system environment variable on Windows.

---

## Step 3 — Run the bare prompt

`bare_prompt.sh` sends a single user message with no system instruction. The model picks its own tone, length, and format.

```bash
bash bare_prompt.sh
```

You should receive a JSON response containing a `candidates` array. Inside it, a `content.parts[0].text` field holds the model's answer. A `usageMetadata` block at the bottom reports input tokens, output tokens, and total tokens charged for the call.

Run it twice and notice that the wording of the answer may change between runs — the model is probabilistic even on simple factual questions.

---

## Step 4 — Run the system-prompted call

`system_prompt.sh` sends the identical user message, but adds a `system_instruction` field that pins the model's role and output format.

```bash
bash system_prompt.sh
```

Compare the two outputs side by side and observe three things:

1. **Format discipline** — the second response is shorter and follows the prescribed structure consistently across reruns.
2. **Controlled tone** — the system instruction steers the model away from markdown and bullet points.
3. **Larger input token count** — the `usageMetadata.promptTokenCount` is higher because the system instruction itself counts as input on every call. This is the seed of the cost-control conversation in Chapter 13.

These two calls illustrate the core claim of the prompts section: the system prompt is the *policy layer* of an agent, not mere decoration.

---

## Troubleshooting

| Response code | Likely cause | First thing to check |
|---|---|---|
| `400` | Malformed JSON in the request body | Check quoting in the `-d` argument, especially on Windows |
| `403` | Key present but Generative Language API is disabled or key is restricted | Open the key in Google Cloud Console and verify API restrictions |
| `429` | Free-tier rate limit hit | Wait a minute, reduce request frequency, or enable billing |
| `404` on model path | Model name has moved | Check the latest stable names at [ai.google.dev/gemini-api/docs](https://ai.google.dev/gemini-api/docs) |

---

## What comes next

Chapter 2 wraps this same Gemini round-trip in Python, adds `python-dotenv` so the key lives in a `.env` file rather than a shell export, and sets up a reproducible Docker Compose environment. Every chapter from there forward builds on that foundation.
