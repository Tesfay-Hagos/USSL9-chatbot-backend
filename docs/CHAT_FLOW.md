# How the Chat Is Initiated and the Request Flow

This document describes how a chat is started and what happens on the backend step by step.

---

## 1. Who initiates the chat

The **client** (e.g. frontend or Postman) initiates the chat by calling the backend:

- **Endpoint:** `POST /api/chat`
- **Body (JSON):** `{ "message": "user text here" }`  
  Optional: `"domain": "general_info"` to force a single store; `"conversation_id": "..."` for future use.

There is **no** separate “start conversation” call. Each `POST /api/chat` is a **single request**: one user message in, one assistant reply out. The “chat” is just a sequence of such requests; the client can keep conversation history in the UI if needed.

---

## 2. Flow when the client sends a message

High-level:

```
Client                    Backend
   |                          |
   |  POST /api/chat           |
   |  { "message": "..." }     |
   |------------------------->|
   |                          |
   |                    [1] Validate request
   |                    [2] Store selection (if domain not set)
   |                    [3] Resolve stores → build RAG tools
   |                    [4] Agent: Gemini chat + File Search (RAG)
   |                    [5] Extract response, sources, links
   |                    [6] Return ChatResponse
   |                          |
   |  ChatResponse            |
   |  { response, sources,    |
   |    links, stores_used }   |
   |<-------------------------|
```

---

## 3. Step-by-step (backend)

### 3.1 Request received

- Route: `POST /api/chat`
- Body: `ChatRequest`: `message` (required), `domain` (optional), `conversation_id` (optional).

### 3.2 Branch: `domain` set or not

**A) Client sent `domain` (e.g. `"general_info"`)**

- **Store selection is skipped.**
- Backend calls: `agent.chat(message=request.message, domain=request.domain)`.
- The agent uses **only** that store for RAG (single-store File Search). If the store does not exist, the agent may respond without RAG (e.g. demo/generic).

**B) Client did not send `domain` (normal ULSS 9 flow)**

1. **Build store list**  
   - Four initial stores (from config) + any “extra” stores that exist in StoreManager and have a description (from registry or saved descriptions).
2. **Store selection**  
   - Call `select_stores_for_query(agent.client, request.message, extra_stores=...)`.  
   - This calls **Gemini** (one shot, structured output) with the user message and the list of store id + description.  
   - Gemini returns which store(s) are relevant (e.g. `["general_info"]` or `["hours", "locations"]`).
3. **Resolve stores**  
   - Map selected store ids to Gemini File Search Store names (via StoreManager). Stores that don’t exist are skipped.
4. **RAG + answer**  
   - Call `agent.chat(message=request.message, store_ids=selected_ids)`.  
   - The agent builds one File Search tool with **all** selected store names, sends the user message to Gemini chat with that tool.  
   - Gemini retrieves relevant chunks from those stores and generates an answer.
5. **Extract and return**  
   - From the Gemini response: text → `response`, grounding/sources → `sources`, and derived `links`, `stores_used`.  
   - Return `ChatResponse(response=..., sources=..., links=..., stores_used=..., domain=null)`.

### 3.3 Response to the client

- **Status:** 200 on success; 500 on unhandled exception.
- **Body:** `ChatResponse`:
  - `response` (str): assistant reply text
  - `sources` (list): grounding chunks (e.g. title, url, snippet)
  - `links` (list): suggested links (title, url or document_id, source_type)
  - `stores_used` (list): store ids that were queried (e.g. `["general_info"]`)
  - `domain` (str | null): echoed from request if provided

The client can then render the reply, show “Pagine consigliate” / “Documenti consigliati” from `links`, and optionally show category badges from `stores_used`.

---

## 4. Summary

| Step | Who / What |
|------|------------|
| **Initiation** | Client sends `POST /api/chat` with `message` (and optionally `domain`). |
| **Store selection** | Only if `domain` is not set: Gemini chooses store(s) from the user message. |
| **RAG** | Agent runs Gemini chat with File Search over the selected store(s). |
| **Response** | Backend returns one `ChatResponse` (response text + sources + links + stores_used). |

There is no separate “init” or “session” endpoint; each message is a single request/response. Multi-turn behaviour is achieved by the client sending further `POST /api/chat` requests (and optionally keeping history on the client side).
