"""PLE Engineering Harness.

An autonomous agent for Physical-Engineering's Last Exam tasks.
Pairs a Google-sponsored foundation model with bash/read_file/write_file
tools, context management, and time-budgeted wrap-up to solve long-horizon
engineering problems across structural, civil, electrical, and mechanical
domains.

Design principles (from dev-set failure analysis):
  1. Read the full task and every referenced file before computing.
  2. Compute with code, never by hand — avoids unit and arithmetic errors.
  3. Open each deliverable after writing it to verify format and contents.
  4. Budget time: stop and summarize well before the 6-hour limit.
  5. Never hard-code task answers; generalize across all 29 dev tasks.
"""

import asyncio
import json
import os
import re

import openai
import taskbridge

MODEL = os.environ["MODEL_NAME"]
MAX_EFFORT_MODELS = ("claude", "glm", "gpt-oss", "deepseek-v4")
EFFORT = os.environ.get("REASONING_EFFORT") or (
    "max" if any(m in MODEL.lower() for m in MAX_EFFORT_MODELS) else "high"
)
WRAP_UP_SEC = 300  # seconds before the limit at which wrap-up begins
WRAP_UP = {
    "role": "user",
    "content": "Time is almost up. Stop calling tools and reply with your final summary of all deliverables.",
}
RESULT_CHARS = 20_000
RETRY_WAITS = (5, 15, 30, 60, 120)
CONTEXT_FULL = re.compile(
    r"context.?(length|window)|prompt is too long|maximum prompt length"
    r"|exceed[^.]{0,40}(token|context)",
    re.I,
)
CUT_KEEP = 1000
MAX_NUDGES = 3
MAX_OUTPUT_TOKENS = int(os.environ.get("MAX_OUTPUT_TOKENS", "32000"))
CACHE_MARK = "claude" in MODEL.lower()

client = openai.AsyncOpenAI(max_retries=5, timeout=1800)

SYSTEM = """You are an expert engineer solving a long-horizon physical-engineering task inside a Linux container with no internet access.

WORKFLOW:
1. Read the task instruction in full. Identify every file it references.
2. Read those files (drawings, PDFs, CSVs, specs, CAD exports) before computing.
3. Compute with code (Python scripts via bash), never by hand — avoids unit-conversion and arithmetic errors.
4. Write each deliverable exactly where and in the format the task asks.
5. Open each deliverable after writing it to verify its format and contents.
6. When done, reply without calling a tool: a short summary of each deliverable, its location, and key results.

TOOLS:
- bash: run a shell command (120 s limit). Inspect files, run Python solvers, convert units, generate CAD/IFC, check outputs.
- read_file: read a text file.
- write_file: create or overwrite a file; parent folders are created automatically.

ENGINEERING REMINDERS:
- Check unit conversions (SI vs imperial) explicitly before applying them.
- Read code tables and drawing callouts carefully before using them.
- If a calculation is complex, write a solver script and let it run.
- Do not stop early: produce every deliverable the task requires.
"""


def tool(name, description, **params):
  return {
      "type": "function",
      "function": {
          "name": name,
          "description": description,
          "parameters": {
              "type": "object",
              "properties": {k: {"type": v} for k, v in params.items()},
              "required": list(params),
          },
      },
  }


TOOLS = [
    tool(
        "bash",
        "Run a bash command (120 s limit) and return its exit code and output.",
        command="string",
    ),
    tool("read_file", "Read a text file.", path="string"),
    tool(
        "write_file",
        "Create or overwrite a file; parent folders are created automatically.",
        path="string",
        content="string",
    ),
]


def clip(text):
  if len(text) <= RESULT_CHARS:
    return text
  half = RESULT_CHARS // 2
  return (
      f"{text[:half]}\n[... {len(text) - RESULT_CHARS} characters cut ...]\n"
      f"{text[-half:]}"
  )


def marked(messages):
  if not CACHE_MARK:
    return messages
  out = list(messages)
  for i in {0, len(out) - 1}:
    m = out[i]
    content = m.get("content")
    if isinstance(content, str) and content:
      out[i] = {
          **m,
          "content": [
              {
                  "type": "text",
                  "text": content,
                  "cache_control": {"type": "ephemeral"},
              }
          ],
      }
    else:
      out[i] = {**m, "cache_control": {"type": "ephemeral"}}
  return out


async def run_tool(session, call):
  if hasattr(call, "function"):
    name = call.function.name
    raw_args = call.function.arguments
  elif isinstance(call, dict):
    fn = call.get("function") or call
    name = fn.get("name") if isinstance(fn, dict) else getattr(fn, "name", "")
    raw_args = fn.get("arguments", "{}") if isinstance(fn, dict) else getattr(fn, "arguments", "{}")
  else:
    name = getattr(call, "name", "")
    raw_args = getattr(call, "arguments", "{}")

  try:
    args = json.loads(raw_args or "{}")
    if not isinstance(args, dict):
      raise TypeError("not a JSON object")
  except (TypeError, ValueError) as exc:
    return f"error: the arguments are not a JSON object ({exc}); send the call again"
  try:
    if name == "bash":
      result = await session.exec(args["command"])
      return clip(f"exit code {result['exit_code']}\n{result['output']}")
    if name == "read_file":
      return clip(
          (await session.read_file(args["path"])).decode("utf-8", "replace")
      )
    if name == "write_file":
      return (
          f"wrote {await session.write_file(args['path'], args['content'])}"
          f" bytes to {args['path']}"
      )
    return f"error: there is no tool named {name}"
  except (taskbridge.TaskError, KeyError, ValueError) as exc:
    return f"error: {type(exc).__name__}: {exc}"


async def recover(session, messages, exc, waits, until):
  status = getattr(exc, "status_code", None)
  if status == 400 and CONTEXT_FULL.search(str(exc)):
    return await shorten(session, messages)
  wait = next(waits, None)
  if wait is None or not (
      status is None or status in (408, 409, 429) or status >= 500
  ):
    return False
  left = session.time_left()
  if left is not None and left > until:
    wait = min(wait, left - until)
  await session.log(f"model call failed ({str(exc)[:200]}); again in {wait:.0f} s")
  await asyncio.sleep(wait)
  return True


async def shorten(session, messages):
  truncated_any = False
  for m in messages:
    content = getattr(m, "content", None) if not isinstance(m, dict) else m.get("content")
    if isinstance(content, str) and len(content) > CUT_KEEP * 2:
      half = CUT_KEEP
      new_content = (
          f"{content[:half]}\n[... {len(content) - 2 * half} characters cut ...]\n"
          f"{content[-half:]}"
      )
      if isinstance(m, dict):
        m["content"] = new_content
      else:
        m.content = new_content
      truncated_any = True
  return truncated_any


async def solve(session: taskbridge.Session) -> str:
  messages = [
      {"role": "system", "content": SYSTEM},
      {"role": "user", "content": session.instruction},
  ]
  left = session.time_left()
  wrap_up_at = None
  if left is not None:
    wrap_up_at = max(left - WRAP_UP_SEC, 0)

  while True:
    now = session.time_left()
    if wrap_up_at is not None and now is not None and now <= wrap_up_at:
      messages.append(dict(WRAP_UP))
      wrap_up_at = None

    try:
      kwargs = {
          "model": MODEL,
          "messages": marked(messages),
          "tools": TOOLS,
          "max_completion_tokens": MAX_OUTPUT_TOKENS,
      }
      if EFFORT:
        kwargs["extra_body"] = {"reasoning_effort": EFFORT}
      response = await client.chat.completions.create(**kwargs)
    except Exception as exc:
      waits = iter(RETRY_WAITS)
      if not await recover(session, messages, exc, waits, wrap_up_at or 0):
        raise
      continue

    choice = response.choices[0]
    msg = choice.message
    messages.append(msg)

    if not msg.tool_calls:
      final = msg.content or "(no final message)"
      session.final_message = final
      await session.log(f"agent final: {final[:500]}")
      return final

    tool_results = []
    for call in (msg.tool_calls or []):
      result = await run_tool(session, call)
      call_id = getattr(call, "id", None) or (call.get("id") if isinstance(call, dict) else "")
      tool_results.append(
          {
              "role": "tool",
              "tool_call_id": call_id,
              "content": result,
          }
      )
    messages.extend(tool_results)
