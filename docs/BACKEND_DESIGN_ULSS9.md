# Backend Design – ULSS 9 RAG Chatbot

This document describes how to adapt `univr-chatbot-backend` so that it implements the professor’s flow: **user sends a free-form prompt → system chooses the relevant knowledge area(s) → RAG over those areas → generative answer + links to the site**. The frontend is assumed to keep the same flow (send message, show answer + suggested links).

---

## 1. Current vs Target Behaviour

| Aspect | Current (sample) | Target (ULSS 9) |
|--------|------------------|------------------|
| **Store selection** | Frontend sends `domain` (user picks) | Backend selects store(s) from the user message via Gemini |
| **Stores** | One store per “domain” (e.g. scholarships, tuition) | One store per **category**: general_info, hours, locations, services, docs (and optionally news) |
| **Content** | Sample UniVR docs (PDF/MD) | **Website content** (ULSS 9 pages) **+ attached documents** (uploaded PDF/MD/DOCX) in the same stores |
| **Response** | `response` + `sources` (chunk snippets) | `response` + **links** (title + URL) + `stores_used` |
| **Agent** | Single File Search store per request | Multiple File Search stores per request when needed |

---

## 2. Store Registry (Categories)

Stores are the RAG “areas” required by **Allegato A**. The system **starts with exactly four stores** (the four areas from the research program); **others can be added via API** (POST /api/admin/stores). All are backed by **Gemini File Search Stores**.

### 2.1 Initial stores (Allegato A – quattro aree)

```python
# app/config.py – ULSS9_STORES (fixed)

ULSS9_STORES = [
    { "id": "general_info", "description": "Informazioni generali sull'Azienda ULSS 9 Scaligera: ..." },
    { "id": "hours",         "description": "Informazioni relative agli orari: ambulatori, punti prelievo, ..." },
    { "id": "locations",    "description": "Informazioni relative alle sedi: indirizzi, ospedali, distretti, ..." },
    { "id": "services",     "description": "Informazioni relative ai servizi offerti presso le sedi: esami di laboratorio, visite specialistiche, ..." },
]
```

- **id** is used as the **domain** when creating/listing Gemini File Search Stores (e.g. display name: `ulss9-general_info`).
- **description** is sent to Gemini when asking “which store(s) is this question about?”.

### 2.2 Extra stores (added via API)

- **POST /api/admin/stores** with `domain` and `description` creates a new store and saves the description (e.g. in `data/store_descriptions.json`) so store selection can include it.
- Store selection uses **ULSS9_STORES + extra stores** (existing stores that are not in the four initial ids, with their saved or display description).

### 2.2 Naming convention

- Keep a single prefix for ULSS 9 so you can distinguish from any legacy UniVR stores: e.g. `STORE_PREFIX = "ulss9"`.
- Store display name in Gemini: `{STORE_PREFIX}-{id}` → `ulss9-general_info`, `ulss9-hours`, etc.

---

## 3. API Contract (Chat)

The frontend continues to send one message and receive one answer; only the semantics and response shape change slightly.

### 3.1 Request

- **Required**: `message` (string).
- **Optional**: `domain` (string). If present, **skip store selection** and use that single store (backward compatibility / testing).
- **Optional**: `conversation_id` (string) for future use (e.g. history).

So: same `ChatRequest` as now, with `domain` optional and meaning “force this store”.

### 3.2 Response

Extend the current `ChatResponse` so the frontend can show **links** and **which categories** were used:

```json
{
  "response": "Testo generativo sintetico...",
  "sources": [
    { "title": "Orari punto prelievi Legnago", "url": "https://www.aulss9.veneto.it/...", "snippet": "..." }
  ],
  "links": [
    { "title": "Punto prelievi Ospedale Mater Salutis", "url": "https://www.aulss9.veneto.it/...", "source_type": "website" },
    { "title": "Modulo richiesta documentazione sanitaria", "document_id": "abc123", "source_type": "attachment" }
  ],
  "stores_used": ["hours", "locations", "docs"],
  "domain": null
}
```

- **response**: Answer text (Italian, synthetic, as per professor’s requirement).
- **sources**: Optional; grounding chunks with title/url/snippet for transparency.
- **links**: 1–3 suggested links to show as “Pagine consigliate” (from RAG context / grounding). Each item can be:
  - **Web**: `title` + `url` (aulss9.veneto.it) — open in browser.
  - **Attached doc**: `title` + `document_id` (and optionally `url` for download/view if you expose one) — e.g. “Documento: Modulo richiesta X”.
- **stores_used**: List of store ids that were queried (so the frontend can show badges like “Orari”, “Sedi”).
- **domain**: Echo of request `domain` if provided; otherwise `null`.

You can keep **sources** as today and add **links** + **stores_used**; if you prefer a single list, you can merge “sources” and “links” into one list with a `url` or `document_id` field.

---

## 4. Chat Flow (Backend)

Single entry point: `POST /api/chat`.

1. **Store selection (when `domain` not provided)**  
   - Build a list of store id + description from the store registry.  
   - Call Gemini (one shot) with a **structured-output** prompt, e.g.:  
     - “Given the user question and the list of stores below, return a JSON object with key `stores` (array of store ids) and optional `reason`.”  
   - Validate the returned ids against the registry; ignore unknown ids.  
   - If the model returns no stores, fallback to e.g. `["general_info"]`.

2. **Resolve Gemini File Search Stores**  
   - For each selected store id, get the corresponding File Search Store from `StoreManager` (by domain = id).  
   - If a store does not exist yet, either skip it or create it (your choice; for demo, skip is fine).  
   - Collect the list of `store.name` (Gemini API names).

3. **Build agent tools**  
   - **Multi-store**: pass **all** selected store names in one File Search tool:  
     - `file_search_store_names=[name1, name2, ...]`  
   - So one RAG call over multiple stores.

4. **Generate answer**  
   - Use the same Gemini chat + File Search as today: system instruction for ULSS 9, user message, tools with the selected stores.  
   - Get the generated text and grounding metadata (chunks).

5. **Build links and sources**  
   - From grounding metadata (and/or chunk custom_metadata): extract `url`, `title`, and `source_type` (“website” | “attachment”) per chunk. For **attached docs**, metadata may have `document_id` or `file_name` instead of `url`.  
   - Deduplicate by URL or document_id, then build:  
     - **links**: up to 3–5 with title + url (website) or title + document_id (attached doc); frontend can show “Pagine consigliate” / “Documenti consigliati” accordingly.  
     - **sources**: same or extended with snippet.  
   - If Gemini does not expose URL/document_id in metadata, add a post-step: ask Gemini to list suggested links in a structured block (e.g. JSON or markdown) and parse it; then merge with grounding chunks.

6. **Return**  
   - `response`, `sources`, `links`, `stores_used`, `domain`.

---

## 5. Agent Changes

- **UniVRAgent** (or a dedicated ULSS9 agent) must support:  
  - **Multiple stores** in one request: `_build_tools(domain=None, store_ids=[...])` and pass `file_search_store_names=[...]`.  
- **System instruction**: Replace UniVR text with ULSS 9: answer in Italian, only from context, suggest 1–3 links with title and URL, do not invent; if info is missing, say so and suggest URP/contacts.  
- **Store selection**: New small module or function: input = user message + store list (id + description); output = list of store ids (call Gemini structured).

No change to the **frontend flow**: it still does one `POST /api/chat` with `message` and optionally `domain`; it just uses the new fields `links` and `stores_used` when present.

---

## 6. Content for RAG: Website + Attached Documents

Content must be available in Gemini File Search Stores. Each store (general_info, hours, locations, services, docs) is fed from **two sources**, both implemented and queryable together:

1. **Website-derived content** — pages from ULSS 9 (ingestion pipeline).  
2. **Attached documents** — PDFs, MD, TXT, DOCX uploaded via the admin API and assigned to a store.

RAG queries run over **all** documents in the selected store(s), regardless of source (website vs attached). The response distinguishes web links from attached-doc references so the frontend can show “Pagine consigliate” vs “Documenti consigliati”.

### 6.1 Content sources (both implemented)

| Source | How it gets into a store | Typical stores |
|--------|---------------------------|----------------|
| **Website** | Ingestion pipeline: fetch ULSS 9 pages → parse → assign store → upload with metadata. | general_info, hours, locations, services, docs |
| **Attached docs** | Admin upload: user selects file + **target store** (or default `docs`) → `StoreManager.upload_document` with metadata. | Prefer `docs`; optionally general_info, services, etc. |

- **Primary (website)**: Pages from `https://www.aulss9.veneto.it/` (crawler or manual export).  
- **Attached docs**: Uploaded via `POST /api/admin/stores/{domain}/upload`; caller specifies which store (domain) the document belongs to (e.g. `docs` for modulistica/bandi, or `general_info` for procedural guides).

### 6.2 Document shape for RAG and links

- Each **page** (or logical section) and each **attached file** becomes one or more indexed documents in the chosen store.  
- **Custom metadata** (set at ingestion or upload) must include:  
  - `title`: page or document title  
  - `store` (or `domain`): e.g. `hours`, `locations`, `docs`  
  - **Website docs**: `url` (canonical aulss9.veneto.it), `source_type`: `"website"`  
  - **Attached docs**: `source_type`: `"attachment"`, `document_id` (or `file_name`) for building “document” links; optional `url` if you expose a download/view endpoint later.  

Chunking is handled by Gemini File Search; metadata is attached so **grounding_metadata** exposes url/title or document_id/title for **links** in the chat response.

### 6.3 Website ingestion pipeline (offline or admin-triggered)

- **Input**: List of URLs (or a sitemap) + rules to map URL/section → store id.  
- **Steps**:  
  1. Fetch HTML (or use pre-saved HTML).  
  2. Parse: title, main content, tables (e.g. orari, recapiti).  
  3. Assign store (e.g. “Ospedali” + address → locations; “Prenotazione punti prelievo” → hours + services).  
  4. Output one file per page (e.g. `.md`) with frontmatter or first line: `# Title\n\nURL: ...\n\n` then body.  
  5. Upload each file to the corresponding store via `StoreManager.upload_document`, with custom_metadata: `url`, `title`, `store`, `source_type`: `"website"`.  

Add an **admin endpoint** (e.g. `POST /api/admin/ingest`) to trigger this pipeline, or run a script once to populate stores.

### 6.4 Attached documents (admin upload)

- **Upload**: Existing `POST /api/admin/stores/{domain}/upload` — require the caller to pass the **target store** (domain), e.g. `docs`, `general_info`, `services`.  
- **Metadata on upload**: When calling `StoreManager.upload_document`, set custom_metadata:  
  - `title` (from extraction or filename),  
  - `store` / `domain`,  
  - `source_type`: `"attachment"`,  
  - `document_id`: stable id (e.g. Gemini document name or a UUID) so the chat response can reference it.  
- **List/delete**: Keep existing `GET /api/admin/stores/{domain}/documents` and `DELETE /api/admin/stores/{domain}/documents/{doc_name}` so admins can manage attached docs per store.  
- **Optional**: Admin UI or API to list “all attached documents” across stores (filter by metadata `source_type == "attachment"`).

When the user asks something that matches content from an attached doc, store selection may include `docs` (or the store where that doc was uploaded); RAG will retrieve from it; the response’s **links** can include an entry with `title` + `document_id` (and no `url`, or an optional download URL if you add one).

### 6.5 Store creation

- On first run (or via admin), ensure all stores in the registry exist: for each `id` in `ULSS9_STORES`, call `StoreManager.create_store(domain=id, description=...)`.  
- Populate stores with: (1) website ingestion run, and (2) any attached documents uploaded via admin. Each store can contain both website-derived and attached documents.

---

## 7. Other Endpoints

- **GET /api/domains** (or **GET /api/stores**): Return the list of **ULSS 9** stores (id, display_name, document_count) from the store registry + StoreManager. So the frontend can show “Categorie” or use for debugging; the professor’s flow does not require the user to pick a category.  
- **GET /api/welcome**: Update message and suggestions to ULSS 9 examples, e.g.:  
  - “Quali sono gli orari del punto prelievi di Legnago?”  
  - “Dove si trova l’Ospedale Magalini di Villafranca?”  
  - “Come posso cambiare il medico di base?”  
  - “Come prenotare una visita specialistica?”  
- **Admin — stores**: Keep existing create store, list stores, delete store. Optionally add “create all ULSS9 stores” and “trigger ingest” for website ingestion.  
- **Admin — attached documents**: Keep and use for **attached docs** implementation:  
  - **POST /api/admin/stores/{domain}/upload**: Upload a file (PDF, MD, TXT, DOCX); backend assigns it to store `domain` and sets metadata (`title`, `store`, `source_type`: `"attachment"`, `document_id`).  
  - **GET /api/admin/stores/{domain}/documents**: List documents in a store (website-derived + attached).  
  - **DELETE /api/admin/stores/{domain}/documents/{doc_name}**: Remove a document (e.g. an attached PDF) from a store.  
  - Optional: **GET /api/admin/documents/attachments**: List all attached documents across stores (filter by `source_type == "attachment"`).

---

## 8. Summary

| Component | Change |
|----------|--------|
| **Config** | Add `ULSS9_STORES` (id + description); optional `STORE_PREFIX = "ulss9"`. |
| **Content** | **Two sources**: (1) **Website** — ingestion pipeline from aulss9.veneto.it; (2) **Attached docs** — admin upload to a chosen store, with metadata `source_type`, `document_id`, `title`. |
| **Store selection** | New step: Gemini structured call → list of store ids. |
| **Agent** | Multi-store File Search; ULSS 9 system instruction; build tools from selected store ids. |
| **Chat response** | Add `links` (title + url for web, title + document_id for attachments) and `stores_used`; keep `response` and `sources`. |
| **Ingestion** | **Website**: fetch ULSS 9 pages → parse → assign store → upload with metadata (url, title, store, source_type). **Attached docs**: admin upload to store with metadata (title, store, source_type, document_id). |
| **Admin** | Ensure ULSS9 stores exist; website ingest trigger; **attached-doc upload/list/delete** per store (existing endpoints used and extended with metadata). |

With this, the backend implements the professor’s requirement: **user prompt → system chooses areas (stores) → RAG over website + attached documents → generative answer + links (site pages and/or suggested documents)**, while reusing your existing frontend flow and Gemini File Search.
