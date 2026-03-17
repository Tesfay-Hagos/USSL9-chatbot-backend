# How to Add Information to All Question Domains

The chatbot answers from document stores (RAG). Each domain is one store. Add content to each domain so the chatbot can answer well.

## The Five Domains

| Domain ID | Description |
|-----------|-------------|
| general_info | Informazioni generali: numeri utili, modulistica, cosa fare per... |
| hours | Orari: punti prelievo, ambulatori, guardie mediche, farmacie |
| locations | Sedi: indirizzi ospedali, distretti, CSP, mappe |
| services | Servizi: esami, visite specialistiche, screening |
| docs | Documenti, normative, bandi (add via Admin as extra store) |

## Method 1: Admin Board (Recommended)

1. Log in to the Admin board (USSL9-chatbot-adminboard).
2. Create the four ULSS 9 stores if needed (button "Crea le 4 categorie ULSS 9").
3. For each domain, upload PDF, Markdown (.md), .txt, or .docx files.
4. The backend ingests them into Gemini; the chatbot uses them for RAG.

What to upload per domain:

- **general_info**: Numeri utili, modulistica, "cosa fare per...", chi siamo. Copy or export from aulss9.veneto.it.
- **hours**: Orari punti prelievo, ambulatori, guardie mediche, farmacie.
- **locations**: Elenco sedi con indirizzi (ospedali, distretti, CSP).
- **services**: Descrizione servizi (esami, visite, screening).

## Method 2: Sample Data + Ingest Script

- Sample Markdown files are in `data/ulss9_sample/general_info/` and `data/sample_docs/`.
- Run: `uv run python scripts/ingest_sample_general_info.py` (requires GEMINI_API_KEY and store general_info).
- Replace sample .md with real content from aulss9.veneto.it, then re-run or upload via Admin.

## Method 3: Copy from aulss9.veneto.it

1. Open pages for Numeri utili, Prenotazioni, Orari, Sedi, Servizi, Modulistica, Cosa fare per...
2. Copy text into .md/.txt or save as PDF.
3. Upload those files to the matching domain in the Admin board.

## Checklist

- [ ] general_info: numeri utili, modulistica, cosa fare per...
- [ ] hours: orari punti prelievo, ambulatori, guardie mediche, farmacie
- [ ] locations: indirizzi sedi (ospedali, distretti, CSP)
- [ ] services: servizi (esami, visite, screening)
- [ ] docs (optional): add store via Admin, upload normative/bandi
- [ ] GEMINI_API_KEY set on backend
- [ ] Stores created via Admin, then documents uploaded

After uploading, the chatbot uses this content automatically. No code change needed.
