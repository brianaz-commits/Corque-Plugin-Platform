# How to Write Tools for Corque Plugin Platform

This guide explains how to author **tools** for the Corque Plugin Platform. Tools are callable capabilities that the Corque agent (and skills) use to perform actions—e.g. search the web, get weather, manage todos, or load a skill. Writing them in a consistent, well-documented way ensures the agent can discover, select, and invoke them correctly.

---

## 1. Overview: Tools and Skills

- **Tools** ("the Hand"): Python functions decorated with `@tool` that the agent invokes. Each tool has a name, parameters, and a docstring that describes *what it does* and *when to use it*.
- **Skills** ("the Brain"): Markdown personas that define workflow and **Tool Usage Protocol**—e.g. "Use `basicWebSearch` when the user asks for real-time info." Skills refer to tools by name and by the behavior described in the tool's docstring.

So: **your tool's docstring is the contract** for both the agent and for skill authors. Write it so that a reader can decide when to call the tool and how to pass arguments.

Reference implementations:

- **Tool template**: `sample/sampletool.py`
- **Skill template (tool-binding section)**: `sample/sampleskill.md` — see "Tool Usage Protocol" / "Tool Binding Protocol" for how skills reference tools.

---

## 2. Three Non-Negotiable Rules

These are the core requirements (as in `sample/sampletool.py`):

| Rule | Why |
|------|-----|
| **1. Docstring must be clear and complete** | The agent (and skills) use it to decide *when* and *how* to call the tool. No docstring → wrong or missed usage. |
| **2. Parameters must have type hints** | The framework and the agent need to know types (e.g. `str`, `int`, `Optional[str]`) to construct valid calls. |
| **3. Do not raise exceptions to the caller** | On failure, **return an error string** (e.g. `"Error: ..."`). If you raise, the agent's call can crash instead of getting a parseable failure message. |

---

## 3. Tool Structure and Content

### 3.1 Decorator and signature

- Use **LangChain**'s decorator: `from langchain_core.tools import tool`.
- Apply `@tool` **only** to functions that should be exposed to the agent. Helper functions (e.g. time conversion, DB init) stay as normal functions without `@tool`.
- Prefer explicit **return type** (e.g. `-> str`, `-> list`) for clarity.

Example (from `sample/sampletool.py`):

```python
from langchain_core.tools import tool

@tool
def sampleTool(query: str, limit: int = 5) -> str:
```

### 3.2 Docstring format

The docstring should include, in order:

1. **One or two sentences**: what the tool does and when the agent should use it (e.g. "Use this tool when the user asks for …").
2. **Args**: for each parameter, give type, meaning, and whether it's required or optional (and default).
3. **Returns**: type and meaning of the return value; mention that on failure an error message string may be returned if applicable.
4. **Optional**: input format rules (e.g. "Date in YYYY-MM-DD"), constraints, or "Do NOT …" to avoid misuse.

Example (adapted from `sample/sampletool.py`):

```python
"""
Search for relevant academic papers.
Use this tool when the user asks for scientific research or literature.

Args:
    query (str): The search topic or question.
    limit (int): The max number of results to return. Default is 5.

Returns:
    str: A formatted string containing the results or an error message.
"""
```

Skills (e.g. in `sampleskill.md`) then reference the tool by name and describe triggers and parameter constraints in "Tool Usage Protocol" / "Tool Binding Protocol", aligned with this docstring.

### 3.3 Recommended code layout

Keep a clear, consistent structure so that tools are easy to maintain and behave predictably:

1. **Parameter validation (optional but recommended)**  
   Check required args and return a clear error string if invalid (e.g. empty `query`).

2. **Core logic inside try/except**  
   Do the real work (API call, DB access, computation) in a `try` block.

3. **Return success or error string**  
   On success: return a string or a serializable structure (e.g. JSON string or list) that the agent can interpret.  
   On failure: `return "Error: ..."` (or `return f"Error: {str(e)}. ..."`) instead of re-raising.

Example flow (from `sample/sampletool.py`):

```python
if not query:
    return "Error: query parameter cannot be empty."

try:
    result = your_api_call(query)  # or computation, DB, etc.
    return json.dumps(result, ensure_ascii=False)
except Exception as e:
    return f"Error executing tool: {str(e)}. Please try again with different parameters."
```

---

## 4. Implementation Details

### 4.1 Configuration

- Use the project's config for secrets and paths (e.g. API keys, database path). Example: `from config.settings import settings` and `settings.tavilyApiKey`, `settings.dataBasePath`.
- Do not hardcode secrets in the tool file.

### 4.2 Time and timezones

- For time-sensitive tools (e.g. todos, scheduling), use the shared **`timeTools`** helpers so behavior is consistent across the platform:
  - `getUTCNow()`, `convertISOToUTCEpoch`, `convertUTCEpochToISO`, `convertUTCToLocal`
- Document in the docstring if inputs/outputs are in UTC or local time and in what format (e.g. ISO 8601).

### 4.3 Multiple tools in one file

- You may define several `@tool` functions in a single module (e.g. `addTodo`, `getTodoListinDaysFromNow`, `deleteTodo`, `changeTodoStatus` in `todoListTools.py`).
- You may also define **helper functions** in the same file **without** `@tool`; the agent only sees and calls the decorated functions. Use helpers to avoid duplication and to keep tool logic readable.

### 4.4 Return value shape

- Prefer **strings** or **serializable structures** (e.g. list of dicts, or `json.dumps(...)`) so the agent can reliably parse and summarize the result.
- If you return a complex object, document the shape in the docstring (e.g. "list of dicts with keys: id, title, status, dueAtLocal").

---

## 5. Examples from the codebase

- **Minimal tool**: `tools/weatherTools.py` — single `@tool`, docstring with Args/Returns, try/except returning error string.
- **Config-backed tool**: `tools/webSearch.py`, `tools/newsTools.py` — use `settings` for API key; same docstring and error-return discipline.
- **Multiple tools + helpers**: `tools/todoListTools.py` — several `@tool` functions plus helpers like `getCurrentUTCEpoch`, `getDueDateUTCEpoch` (no `@tool`), and use of `timeTools` for conversions.
- **Platform tool**: `tools/loadskillTools.py` — `load_skill(skill_name)` returns skill content or a "not found" message; docstring explains when the agent should call it.

---

## 6. Checklist before submitting a new tool

- [ ] `from langchain_core.tools import tool` and `@tool` applied only to functions that should be callable by the agent.
- [ ] Docstring: short "what + when to use", plus **Args** and **Returns** (and optional constraints).
- [ ] All parameters and return type have **type hints**.
- [ ] No **raised exceptions** to the caller; failures return an **error string** (e.g. `"Error: ..."`).
- [ ] Configuration (API keys, paths) read from **config.settings**; no hardcoded secrets.
- [ ] Time handling uses **timeTools** where relevant; docstring states format and timezone (e.g. UTC / ISO 8601).
- [ ] File lives under **`tools/`** and follows project naming (e.g. `*Tools.py`).
- [ ] Optional: add a "Tool Binding Protocol" or "When to use" note in a related skill (see `sample/sampleskill.md`) so the agent and skill authors know when to call this tool.

---

## 7. Quick reference: minimal template

```python
from langchain_core.tools import tool

@tool
def myTool(query: str, limit: int = 5) -> str:
    """
    [One sentence: what it does.]
    Use this tool when [when the agent should call it].

    Args:
        query (str): [Description.]
        limit (int): [Description.] Default is 5.

    Returns:
        str: [Description; mention error message on failure.]
    """
    if not query:
        return "Error: query parameter cannot be empty."
    try:
        result = ...  # your logic
        return result  # or json.dumps(result)
    except Exception as e:
        return f"Error: {str(e)}. Please try again."
```

For a full reference, see **`sample/sampletool.py`** and **`sample/sampleskill.md`** (Tool Usage / Tool Binding sections).
