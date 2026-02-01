"""
API tests for ULSS 9 Chatbot backend.

Chat and admin endpoints that call Gemini are mocked so tests run without an API key.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


# ----- Health & public -----


def test_health(client: TestClient) -> None:
    """GET /health returns 200 and app name."""
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy"
    assert "ulss9" in data.get("app", "").lower()


def test_welcome(client: TestClient) -> None:
    """GET /api/welcome returns message and suggestions."""
    r = client.get("/api/welcome")
    assert r.status_code == 200
    data = r.json()
    assert "message" in data
    assert "suggestions" in data
    assert isinstance(data["suggestions"], list)
    assert "available_domains" in data


def test_domains(client: TestClient) -> None:
    """GET /api/domains returns list of stores (four initial + any extra)."""
    r = client.get("/api/domains")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    # Four initial stores from config
    ids = [s["domain"] for s in data]
    assert "general_info" in ids
    assert "hours" in ids
    assert "locations" in ids
    assert "services" in ids
    for s in data:
        assert "domain" in s
        assert "display_name" in s
        assert "document_count" in s


# ----- Chat (mocked) -----


def test_chat_with_domain_mocked(client: TestClient) -> None:
    """POST /api/chat with domain returns response from mocked agent."""
    mock_result = {
        "response": "Risposta di test per general_info.",
        "sources": [{"title": "Fonte", "snippet": "..."}],
        "links": [{"title": "Pagina", "url": "https://example.it"}],
        "stores_used": ["general_info"],
    }
    with patch("app.api.chat.agent.chat", new_callable=AsyncMock, return_value=mock_result):
        r = client.post(
            "/api/chat",
            json={"message": "Qual è il numero dell'URP?", "domain": "general_info"},
        )
    assert r.status_code == 200
    data = r.json()
    assert data["response"] == mock_result["response"]
    assert data["sources"] == mock_result["sources"]
    assert data["links"] == mock_result["links"]
    assert data["stores_used"] == mock_result["stores_used"]
    assert data["domain"] == "general_info"


def test_chat_without_domain_mocked(client: TestClient) -> None:
    """POST /api/chat without domain uses store selection then RAG (mocked)."""
    mock_result = {
        "response": "Risposta generata da RAG.",
        "sources": [],
        "links": [],
        "stores_used": ["general_info"],
    }
    with (
        patch("app.api.chat.select_stores_for_query", new_callable=AsyncMock, return_value=["general_info"]),
        patch("app.api.chat.agent.chat", new_callable=AsyncMock, return_value=mock_result),
    ):
        r = client.post("/api/chat", json={"message": "Chi è l'ULSS 9?"})
    assert r.status_code == 200
    data = r.json()
    assert data["response"] == mock_result["response"]
    assert data["stores_used"] == ["general_info"]
    assert data["domain"] is None


def test_chat_requires_message(client: TestClient) -> None:
    """POST /api/chat without message returns 422."""
    r = client.post("/api/chat", json={})
    assert r.status_code == 422


def test_chat_accepts_conversation_id(client: TestClient) -> None:
    """POST /api/chat accepts optional conversation_id."""
    mock_result = {
        "response": "OK",
        "sources": [],
        "links": [],
        "stores_used": [],
    }
    with patch("app.api.chat.agent.chat", new_callable=AsyncMock, return_value=mock_result):
        r = client.post(
            "/api/chat",
            json={
                "message": "Test",
                "domain": "general_info",
                "conversation_id": "conv-123",
            },
        )
    assert r.status_code == 200


# ----- Admin: stores -----


def test_admin_list_stores(client: TestClient) -> None:
    """GET /api/admin/stores returns list (may be empty without API key)."""
    r = client.get("/api/admin/stores")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_admin_create_store_mocked(client: TestClient) -> None:
    """POST /api/admin/stores creates a store (mocked)."""
    fake_store = type("Store", (), {"name": "stores/fake-123", "display_name": "ulss9-docs"})()
    with patch(
        "app.api.admin.StoreManager",
    ) as MockSM:
        mock_instance = MockSM.return_value
        mock_instance.create_store = AsyncMock(return_value=fake_store)
        r = client.post(
            "/api/admin/stores",
            json={"domain": "docs", "description": "Documenti ufficiali"},
        )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["domain"] == "docs"


def test_admin_create_all_ulss9_mocked(client: TestClient) -> None:
    """POST /api/admin/stores/ulss9/create-all creates four stores (mocked)."""
    fake_store = type("Store", (), {"name": "stores/fake", "display_name": "ulss9-x"})()
    with patch("app.api.admin.StoreManager") as MockSM:
        mock_instance = MockSM.return_value
        mock_instance.create_store = AsyncMock(return_value=fake_store)
        r = client.post("/api/admin/stores/ulss9/create-all")
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert "stores" in data
    assert len(data["stores"]) == 4


def test_admin_delete_store_not_found_mocked(client: TestClient) -> None:
    """DELETE /api/admin/stores/{domain} returns 404 when store does not exist."""
    with patch("app.api.admin.StoreManager") as MockSM:
        mock_instance = MockSM.return_value
        mock_instance.delete_store = AsyncMock(return_value=False)
        r = client.delete("/api/admin/stores/nonexistent")
    assert r.status_code == 404


def test_admin_delete_all_stores_mocked(client: TestClient) -> None:
    """POST /api/admin/stores/delete-all deletes all stores (mocked)."""
    with patch("app.api.admin.StoreManager") as MockSM:
        mock_instance = MockSM.return_value
        mock_instance.list_stores = AsyncMock(
            return_value=[
                type("StoreInfo", (), {"domain": "general_info", "display_name": "ulss9-general_info", "document_count": 0})(),
            ]
        )
        mock_instance.delete_store = AsyncMock(return_value=True)
        r = client.post("/api/admin/stores/delete-all")
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert "deleted" in data


# ----- Admin: documents -----


def test_admin_upload_rejects_bad_file_type(client: TestClient) -> None:
    """POST /api/admin/stores/{domain}/upload returns 400 for unsupported file type."""
    r = client.post(
        "/api/admin/stores/general_info/upload",
        files={"file": ("bad.csv", b"col1,col2\n1,2", "text/csv")},
    )
    assert r.status_code == 400
    assert "supported" in r.json().get("detail", "").lower()


def test_admin_list_documents_mocked(client: TestClient) -> None:
    """GET /api/admin/stores/{domain}/documents returns list (mocked)."""
    with patch("app.api.admin.StoreManager") as MockSM:
        mock_instance = MockSM.return_value
        mock_instance.list_documents = AsyncMock(return_value=[])
        r = client.get("/api/admin/stores/general_info/documents")
    assert r.status_code == 200
    assert r.json() == []


def test_admin_delete_document_not_found_mocked(client: TestClient) -> None:
    """DELETE /api/admin/stores/{domain}/documents/{doc} returns 404 when doc not found."""
    with patch("app.api.admin.StoreManager") as MockSM:
        mock_instance = MockSM.return_value
        mock_instance.delete_document = AsyncMock(return_value=False)
        r = client.delete("/api/admin/stores/general_info/documents/some-doc-name")
    assert r.status_code == 404


# ----- Agent status (no mock) -----


def test_agent_status(client: TestClient) -> None:
    """GET /api/agent/status returns api_key_set and client info."""
    r = client.get("/api/agent/status")
    assert r.status_code == 200
    data = r.json()
    assert "api_key_set" in data
    assert "client_initialized" in data
