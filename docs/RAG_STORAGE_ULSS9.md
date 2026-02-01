# How ULSS 9 Information Is Stored for RAG

This note explains how content gets into the RAG system and how queries use it.

---

## 1. Flow in short

```
Content (website pages or uploaded files)
    → Uploaded to a store (e.g. general_info, hours, locations, services)
    → Indexed by Gemini File Search (chunked + embedded)
    → User asks a question
    → Store selection: Gemini chooses which store(s) apply
    → RAG: Gemini retrieves relevant chunks from those stores and generates an answer
```

So: **you put ULSS 9 information into stores; the chatbot uses those stores to answer.**

---

## 2. Stores (categories)

- **Four initial stores** (Allegato A): `general_info`, `hours`, `locations`, `services`.
- **Extra stores** can be added via `POST /api/admin/stores` (e.g. `docs`).

Each store is a **Gemini File Search Store**. Documents in a store are chunked and embedded by Gemini; at query time, only the stores selected for the question are searched.

---

## 3. How to put information into a store

Two ways:

### A) Upload files (admin API)

- **Endpoint:** `POST /api/admin/stores/{domain}/upload`
- **Body:** multipart file (PDF, .md, .txt, .docx)
- **Effect:** File is sent to Gemini, chunked and indexed in the store `domain`. Metadata (title, `source_type`, `document_id`) is set so the chat can return “suggested documents”.

Use this for:
- Attached documents (modulistica, bandi, normative) → typically store `docs`.
- Sample or curated “informazioni generali” (e.g. markdown pages) → store `general_info`.

### B) Website ingestion (future)

- Crawl or export pages from aulss9.veneto.it.
- For each page: assign a store, convert to text/markdown, then upload via the same mechanism (e.g. script that calls `StoreManager.upload_document` with `source_type="website"` and `url`).

For now, **storing ULSS 9 info for RAG = uploading files to the right store** (e.g. sample .md files into `general_info`).

---

## 4. Sample: “informazioni generali” only

A minimal setup is:

1. **Create the store** (if not already there):  
   `POST /api/admin/stores/ulss9/create-all`  
   → creates `general_info`, `hours`, `locations`, `services`.

2. **Put sample content into `general_info`:**
   - Either upload each file via `POST /api/admin/stores/general_info/upload`.
   - Or run the provided script once:  
     `uv run python scripts/ingest_sample_general_info.py`  
     which uploads everything in `data/ulss9_sample/general_info/` (e.g. .md files) to the `general_info` store.

3. **Ask in the chat** (e.g. “Chi è l’ULSS 9?”, “Qual è il numero dell’URP?”, “Come prenoto una visita?”).  
   Store selection will choose `general_info`; RAG will use the uploaded documents to answer.

---

## 5. Sample “informazioni generali” – files and script

- **Sample files:** `data/ulss9_sample/general_info/`  
  - `chi_siamo_ulss9.md` – Chi siamo, sede (Via Valverde 42), telefono 045 8075511  
  - `numeri_utili_contatti.md` – URP, prenotazioni, referti, 118  
  - `prenotazioni_visite_esami.md` – Come prenotare visite/esami con o senza impegnativa  
  - `modulistica_cosa_fare_per.md` – Modulistica e “Cosa fare per...”

- **Ingest script (one-shot):**  
  From the backend root:
  ```bash
  uv run python scripts/ingest_sample_general_info.py
  ```
  This creates the `general_info` store if missing and uploads all `.md`/`.txt` files from `data/ulss9_sample/general_info/` into it.

- **Alternative:** upload each file via  
  `POST /api/admin/stores/general_info/upload` (multipart file).

So for a **sample just for information**: run the script above (or upload the sample files to `general_info`), then test with questions that fall under “informazioni generali”.
