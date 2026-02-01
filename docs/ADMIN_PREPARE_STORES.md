# Prepare ULSS 9 Stores (Gemini)

The chatbot uses **Gemini File Search Stores**. Only stores that exist in Gemini appear in the admin panel and in store selection. The **4 initial stores** (Allegato A) are not created automatically; you must create them once.

---

## 1. Clear all stores (optional)

To remove **every** store in Gemini that uses your `STORE_PREFIX` (e.g. `ulss9`):

- **From Admin Panel (frontend):**  
  Pannello Admin → Gestione categorie → **"Elimina tutte le categorie"** (with confirmation).

- **From API:**
  ```http
  POST /api/admin/stores/delete-all
  ```
  Response: `{ "success": true, "message": "...", "deleted": ["general_info", "docs", ...] }`

This deletes all stores returned by `GET /api/admin/stores` (i.e. all stores whose display name starts with `STORE_PREFIX`).

---

## 2. Create the 4 ULSS 9 stores

To create the four initial categories (**general_info**, **hours**, **locations**, **services**):

- **From Admin Panel (frontend):**  
  Pannello Admin → Gestione categorie → **"Crea le 4 categorie iniziali"**.

- **From API:**
  ```http
  POST /api/admin/stores/ulss9/create-all
  ```
  Response: `{ "success": true, "message": "ULSS 9 stores ensured", "stores": [ { "domain": "general_info", "store_name": "..." }, ... ] }`

This is **idempotent**: if a store already exists, it is not duplicated.

---

## 3. Recommended flow

1. **(Optional)** Clear all: Admin Panel → **Elimina tutte le categorie** (confirm).
2. Create the 4 stores: Admin Panel → **Crea le 4 categorie iniziali**.
3. Reload the page or refresh the list; you should see **general_info**, **hours**, **locations**, **services**.
4. Upload documents to each store (e.g. run `scripts/ingest_sample_general_info.py` for **general_info**, or use Admin → Carica file).

---

## 4. Environment

- **STORE_PREFIX** (e.g. in `.env`): must match what the backend uses (default `ulss9`).  
  Stores are named `{STORE_PREFIX}-{domain}` in Gemini (e.g. `ulss9-general_info`).
- **GEMINI_API_KEY**: required for listing, creating, and deleting stores.
