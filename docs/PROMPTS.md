# Developer Memory OS
## LLM Prompt Specifications

Version: 1.0  
Status: Active  

---

## 1. Overview

Developer Memory OS uses structured LangChain LCEL chains combined with Google Gemma (via Hugging Face Inference API) to generate concise, actionable summaries of developer sessions and answer natural-language historical queries.

---

## 2. Session Summarization Chain

### LCEL Architecture
```python
chain = prompt | chat_model | JsonOutputParser(pydantic_object=SessionSummaryOutput)
```

### Output Pydantic Schema (`SessionSummaryOutput`)
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "SessionSummaryOutput",
  "type": "object",
  "properties": {
    "summary": {
      "type": "string",
      "description": "One-sentence summary of what was worked on."
    },
    "decisions": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Key decisions or actions taken during the session."
    },
    "pending_work": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Unfinished tasks or next steps remaining."
    }
  },
  "required": ["summary", "decisions", "pending_work"]
}
```

### System Prompt
```text
You are an expert developer activity analyzer. Follow the output format instructions precisely.

{format_instructions}
```

### Human Message Template
```text
Analyse the development session below and return a structured JSON summary.

Workspace : {workspace}
Duration  : {duration_seconds} seconds
Files     : {files}

Events (chronological):
{events}
```

### Input Variables
- `workspace`: Absolute path of the project workspace.
- `duration_seconds`: Total active session duration in seconds.
- `files`: JSON array / list of distinct files touched during the session.
- `events`: Formatted chronological string of raw events (e.g. `[2026-08-16 16:30:00] FileSaved — src/main.py`).

---

## 3. Search & Q&A Chain

### LCEL Architecture
```python
chain = prompt | chat_model | StrOutputParser()
```

### System Prompt
```text
You are a developer assistant with access to a developer's work history. Answer questions concisely and helpfully using only the sessions provided. Respond in plain text — no JSON, no markdown.
```

### Human Message Template
```text
Question: {query}

Work History:
{context}
```

### Input Variables
- `query`: The user's natural language question (e.g., `"What did I work on yesterday?"`, `"Which file did I edit last?"`).
- `context`: Formatted string representing retrieved sessions matching temporal keywords or search terms.

---

## 4. Local Deterministic Fallback Specification

When `HF_API_KEY` is not provided or network access is unavailable, the system produces deterministic summaries without LLM calls:

- **Summary**: Constructed from git commit messages if available (`Worked on development task. Commits: ...`) or modified files (`Completed development session. Touched: ...`).
- **Decisions**: List of committed messages or modified file actions.
- **Pending Work**: Extracted diagnostic warnings/errors (e.g., `Resolve diagnostic: [Warning] file.py: message`) or reminder to continue work on modified files.