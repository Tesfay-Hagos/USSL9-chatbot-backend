"""
UniVR Chatbot - Configuration Module
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Gemini Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = os.getenv("MODEL", "gemini-2.5-flash")

# Store naming prefix - stores will be named: {STORE_PREFIX}-{domain}
STORE_PREFIX = os.getenv("STORE_PREFIX", "ulss9")

# ULSS 9 initial store registry (Allegato A – quattro aree obbligatorie).
# Altre categorie possono essere aggiunte via API (POST /api/admin/stores).
ULSS9_STORES = [
    {
        "id": "general_info",
        "description": "Informazioni generali sull'Azienda ULSS 9 Scaligera: chi siamo, come accedere ai servizi, numeri utili, modulistica, cosa fare per...",
    },
    {
        "id": "hours",
        "description": "Informazioni relative agli orari: ambulatori, punti prelievo, reparti, guardie mediche, farmacie, orari di visita.",
    },
    {
        "id": "locations",
        "description": "Informazioni relative alle sedi: indirizzi, come raggiungere ospedali, distretti, CSP, sedi vaccinali, mappe.",
    },
    {
        "id": "services",
        "description": "Informazioni relative ai servizi offerti presso le sedi: esami di laboratorio, visite specialistiche, screening, assistenza domiciliare, ambulatori.",
    },
]

# Language: if True, frontend can offer English; chatbot will respond in chosen language
ALLOW_ENGLISH = os.getenv("ALLOW_ENGLISH", "false").lower() == "true"

# Application Settings
APP_ENV = os.getenv("APP_ENV", "development")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Validation - warn if API key is missing
if not GEMINI_API_KEY:
    print("⚠️  WARNING: GEMINI_API_KEY not set!")
    print("   → Copy .env.example to .env and add your API key")
    print("   → Domains/documents will NOT be available")
    print()
