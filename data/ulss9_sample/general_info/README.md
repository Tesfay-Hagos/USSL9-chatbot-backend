# Sample documents – Informazioni generali (ULSS 9)

These markdown files are **sample content** for the RAG store `general_info`.  
They mimic typical “informazioni generali” from the ULSS 9 website (chi siamo, numeri utili, prenotazioni, modulistica).

## Files

- `chi_siamo_ulss9.md` – Chi siamo, sede legale, contatti
- `numeri_utili_contatti.md` – Numeri utili, URP, prenotazioni, referti, 118
- `prenotazioni_visite_esami.md` – Come prenotare visite ed esami (con/senza impegnativa)
- `modulistica_cosa_fare_per.md` – Modulistica e “Cosa fare per...”

## How to use for RAG

1. Create the store (if needed):  
   `POST /api/admin/stores/ulss9/create-all`  
   or run the ingest script once.

2. Ingest these files into the `general_info` store:
   - **Option A:** From the backend root:  
     `uv run python scripts/ingest_sample_general_info.py`
   - **Option B:** Upload each file via the API:  
     `POST /api/admin/stores/general_info/upload` with each .md file.

3. Ask the chatbot questions such as:
   - “Chi è l’ULSS 9?”
   - “Qual è il numero dell’URP?”
   - “Come prenoto una visita?”
   - “Dove si trova la sede di Verona?”

The store selector will choose `general_info` and RAG will use these documents to answer.
