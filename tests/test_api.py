"""
API tests for ULSS 9 Chatbot backend.

Covers: health, auth, chat, admin, session tokens, password reset, Pydantic validation,
corrections CRUD, chat log viewer, store health, and store registry seeding.
"""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

# ----- Health & public -----


def test_health(client: TestClient) -> None:
    """GET /health returns 200 and app name."""
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy"
    assert "ulss9" in data.get("app", "").lower()


def test_readiness(client: TestClient) -> None:
    """GET /ready returns readiness status."""
    r = client.get("/ready")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("ready", "degraded")
    assert "gemini_configured" in data


def test_welcome(client: TestClient) -> None:
    """GET /api/welcome returns message and suggestions."""
    r = client.get("/api/v1/welcome")
    assert r.status_code == 200
    data = r.json()
    assert "message" in data
    assert "suggestions" in data
    assert isinstance(data["suggestions"], list)
    assert "available_domains" in data


def test_domains(client: TestClient) -> None:
    """GET /api/domains returns list of stores (seeded from DB)."""
    with patch("app.api.chat.StoreManager") as MockSM:
        mock_instance = MockSM.return_value
        mock_instance.list_stores = AsyncMock(return_value=[])
        r = client.get("/api/v1/domains")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    # Four initial stores should be seeded in DB
    ids = [s["domain"] for s in data]
    assert "general_info" in ids
    assert "hours" in ids
    assert "locations" in ids
    assert "services" in ids
    for s in data:
        assert "domain" in s
        assert "display_name" in s
        assert "document_count" in s


# ----- Removed endpoints return 404/405 -----


def test_agent_status_removed(client: TestClient) -> None:
    """GET /api/agent/status should no longer exist (removed in Phase 0)."""
    r = client.get("/api/agent/status")
    assert r.status_code in (404, 405)


def test_agent_test_removed(client: TestClient) -> None:
    """GET /api/agent/test should no longer exist (removed in Phase 0)."""
    r = client.get("/api/agent/test")
    assert r.status_code in (404, 405)


def test_suggestions_removed(client: TestClient) -> None:
    """GET /api/suggestions/{domain} should no longer exist (removed in Phase 0)."""
    r = client.get("/api/suggestions/general_info")
    assert r.status_code in (404, 405)


# ----- Session Token -----


def test_session_token_issue(client: TestClient) -> None:
    """POST /api/v1/session-token returns a valid token."""
    r = client.post("/api/v1/session-token")
    assert r.status_code == 200
    data = r.json()
    assert "session_token" in data
    assert "expires_in" in data
    assert data["expires_in"] > 0
    token = data["session_token"]
    parts = token.split(":")
    assert len(parts) == 3


def test_session_token_validation(client: TestClient) -> None:
    """Session token validation rejects tampered tokens."""
    from app.api.session import create_session_token, validate_session_token

    token, _ = create_session_token()
    assert validate_session_token(token) is True
    assert validate_session_token("0:abc:fake_sig") is False
    assert validate_session_token("") is False
    assert validate_session_token("only_one_part") is False


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
            "/api/v1/chat",
            json={"message": "Qual è il numero dell'URP?", "domain": "general_info"},
            headers={"x-session-token": _get_session_token(client)},
        )
    assert r.status_code == 200
    data = r.json()
    assert data["response"] == mock_result["response"]
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
        r = client.post(
            "/api/v1/chat",
            json={"message": "Chi è l'ULSS 9?"},
            headers={"x-session-token": _get_session_token(client)},
        )
    assert r.status_code == 200
    data = r.json()
    assert data["response"] == mock_result["response"]


def test_chat_requires_message(client: TestClient) -> None:
    """POST /api/chat without message returns 422."""
    r = client.post(
        "/api/v1/chat",
        json={},
        headers={"x-session-token": _get_session_token(client)},
    )
    assert r.status_code == 422


def test_chat_requires_session_token(client: TestClient) -> None:
    """POST /api/chat without session token returns 401."""
    r = client.post("/api/v1/chat", json={"message": "test"})
    assert r.status_code == 401


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
            "/api/v1/chat",
            json={
                "message": "Test",
                "domain": "general_info",
                "conversation_id": "conv-123",
            },
            headers={"x-session-token": _get_session_token(client)},
        )
    assert r.status_code == 200


# ----- Pydantic Validation -----


def test_chat_message_too_long(client: TestClient) -> None:
    """POST /api/chat with message > 2000 chars returns 422."""
    r = client.post(
        "/api/v1/chat",
        json={"message": "x" * 2001},
        headers={"x-session-token": _get_session_token(client)},
    )
    assert r.status_code == 422


def test_chat_invalid_domain_pattern(client: TestClient) -> None:
    """POST /api/chat with invalid domain pattern returns 422."""
    r = client.post(
        "/api/v1/chat",
        json={"message": "test", "domain": "INVALID DOMAIN!"},
        headers={"x-session-token": _get_session_token(client)},
    )
    assert r.status_code == 422


def test_admin_create_store_invalid_domain(client: TestClient) -> None:
    """POST /api/admin/stores with invalid domain pattern returns 422."""
    r = client.post(
        "/api/v1/admin/stores",
        json={"domain": "BAD DOMAIN!!", "description": "test"},
    )
    assert r.status_code == 422


# ----- Admin: stores -----


def test_admin_list_stores(client: TestClient) -> None:
    """GET /api/admin/stores returns list."""
    r = client.get("/api/v1/admin/stores")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_admin_create_store_mocked(client: TestClient) -> None:
    """POST /api/admin/stores creates a store (mocked)."""
    fake_store = type("Store", (), {"name": "stores/fake-123", "display_name": "ulss9-docs"})()
    with patch("app.api.admin.StoreManager") as MockSM:
        mock_instance = MockSM.return_value
        mock_instance.create_store = AsyncMock(return_value=fake_store)
        r = client.post(
            "/api/v1/admin/stores",
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
        r = client.post("/api/v1/admin/stores/ulss9/create-all")
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
        r = client.delete("/api/v1/admin/stores/nonexistent")
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
        r = client.post("/api/v1/admin/stores/delete-all")
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True


# ----- Admin: store health -----


def test_store_health_endpoint(client: TestClient) -> None:
    """GET /api/admin/stores/{domain}/health returns status."""
    with patch("app.api.admin.StoreManager") as MockSM:
        mock_instance = MockSM.return_value
        mock_instance.get_store.return_value = None
        mock_instance.list_documents = AsyncMock(return_value=[])
        r = client.get("/api/v1/admin/stores/general_info/health")
    assert r.status_code == 200
    data = r.json()
    assert data["domain"] == "general_info"
    assert "in_database" in data
    assert "status" in data


# ----- Admin: documents -----


def test_admin_upload_rejects_bad_file_type(client: TestClient) -> None:
    """POST /api/admin/stores/{domain}/upload returns 400 for unsupported file type."""
    r = client.post(
        "/api/v1/admin/stores/general_info/upload",
        files={"file": ("bad.csv", b"col1,col2\n1,2", "text/csv")},
    )
    assert r.status_code == 400
    assert "supported" in r.json().get("detail", "").lower()


def test_admin_list_documents_mocked(client: TestClient) -> None:
    """GET /api/admin/stores/{domain}/documents returns list (mocked)."""
    with patch("app.api.admin.StoreManager") as MockSM:
        mock_instance = MockSM.return_value
        mock_instance.list_documents = AsyncMock(return_value=[])
        r = client.get("/api/v1/admin/stores/general_info/documents")
    assert r.status_code == 200
    assert r.json() == []


def test_admin_delete_document_not_found_mocked(client: TestClient) -> None:
    """DELETE /api/admin/stores/{domain}/documents/{doc} returns 404."""
    with patch("app.api.admin.StoreManager") as MockSM:
        mock_instance = MockSM.return_value
        mock_instance.delete_document = AsyncMock(return_value=False)
        r = client.delete("/api/v1/admin/stores/general_info/documents/some-doc-name")
    assert r.status_code == 404


# ----- Corrections CRUD -----


def test_create_correction(client: TestClient) -> None:
    """POST /api/v1/admin/corrections creates a correction with injection."""
    with patch("app.services.corrections.inject_correction", new_callable=AsyncMock, return_value="correction_abc123.md"):
        r = client.post(
            "/api/v1/admin/corrections",
            json={
                "query_pattern": "test correction pattern",
                "corrected_response": "This is the corrected response.",
                "domain": "general_info",
            },
        )
    assert r.status_code == 200
    data = r.json()
    assert "id" in data
    assert data["query_pattern"] == "test correction pattern"
    assert data["corrected_response"] == "This is the corrected response."
    assert data["domain"] == "general_info"
    assert data["is_active"] is True
    assert data["created_by"] == "test@test.com"
    assert data["injection_status"] == "injected"


def test_create_correction_injection_failed(client: TestClient) -> None:
    """Correction created with failed injection (no Gemini)."""
    with patch("app.services.corrections.inject_correction", new_callable=AsyncMock, return_value=None):
        r = client.post(
            "/api/v1/admin/corrections",
            json={
                "query_pattern": "failed injection test",
                "corrected_response": "Response text.",
                "domain": "hours",
            },
        )
    assert r.status_code == 200
    data = r.json()
    assert data["injection_status"] == "failed"
    assert data["gemini_doc_name"] is None


def test_list_corrections(client: TestClient) -> None:
    """GET /api/v1/admin/corrections lists all corrections."""
    r = client.get("/api/v1/admin/corrections")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1  # At least the ones created above


def test_update_correction(client: TestClient) -> None:
    """PUT /api/v1/admin/corrections/{id} updates a correction."""
    with patch("app.services.corrections.inject_correction", new_callable=AsyncMock, return_value="doc.md"):
        create_r = client.post(
            "/api/v1/admin/corrections",
            json={"query_pattern": "update test", "corrected_response": "original", "domain": "general_info"},
        )
    correction_id = create_r.json()["id"]

    with patch("app.services.corrections.remove_injection", new_callable=AsyncMock, return_value=True):
        r = client.put(
            f"/api/v1/admin/corrections/{correction_id}",
            json={"corrected_response": "updated response", "is_active": False},
        )
    assert r.status_code == 200
    data = r.json()
    assert data["corrected_response"] == "updated response"
    assert data["is_active"] is False


def test_delete_correction(client: TestClient) -> None:
    """DELETE /api/v1/admin/corrections/{id} deletes and cleans up injection."""
    with patch("app.services.corrections.inject_correction", new_callable=AsyncMock, return_value="doc.md"):
        create_r = client.post(
            "/api/v1/admin/corrections",
            json={"query_pattern": "delete test", "corrected_response": "to delete", "domain": "general_info"},
        )
    correction_id = create_r.json()["id"]

    with patch("app.services.corrections.remove_injection", new_callable=AsyncMock, return_value=True):
        r = client.delete(f"/api/v1/admin/corrections/{correction_id}")
    assert r.status_code == 200
    assert r.json()["success"] is True


def test_delete_correction_not_found(client: TestClient) -> None:
    """DELETE /api/v1/admin/corrections/{id} returns 404 for unknown id."""
    r = client.delete("/api/v1/admin/corrections/nonexistent-id")
    assert r.status_code == 404


def test_correction_requires_domain(client: TestClient) -> None:
    """POST /api/v1/admin/corrections without domain returns 422."""
    r = client.post(
        "/api/v1/admin/corrections",
        json={"query_pattern": "test pattern", "corrected_response": "ok"},
    )
    assert r.status_code == 422


# ----- Chat Log Viewer -----


def test_chat_logs_empty(client: TestClient) -> None:
    """GET /api/v1/admin/chat-logs returns paginated response."""
    r = client.get("/api/v1/admin/chat-logs")
    assert r.status_code == 200
    data = r.json()
    assert "logs" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert isinstance(data["logs"], list)


def test_purge_chat_logs(client: TestClient) -> None:
    """POST /api/v1/admin/chat-logs/purge returns success."""
    r = client.post("/api/v1/admin/chat-logs/purge")
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert "deleted" in data


# ----- Password Reset -----


def test_password_reset_request(client: TestClient) -> None:
    """POST /api/v1/auth/password-reset/request returns 200 regardless of email."""
    with patch("app.api.password_reset.send_otp_email", new_callable=AsyncMock, return_value=True):
        r = client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": "admin@aulss9.veneto.it"},
        )
    assert r.status_code == 200


def test_password_reset_request_unknown_email(client: TestClient) -> None:
    """POST /api/v1/auth/password-reset/request with unknown email still returns 200."""
    r = client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "unknown@example.com"},
    )
    assert r.status_code == 200


def test_password_reset_confirm_invalid_otp(client: TestClient) -> None:
    """POST /api/v1/auth/password-reset/confirm with wrong OTP returns 400."""
    r = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"email": "admin@aulss9.veneto.it", "otp": "000000", "new_password": "newpassword123"},
    )
    assert r.status_code == 400


def test_password_reset_confirm_invalid_otp_format(client: TestClient) -> None:
    """POST /api/v1/auth/password-reset/confirm with non-numeric OTP returns 422."""
    r = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"email": "admin@aulss9.veneto.it", "otp": "abcdef", "new_password": "newpassword123"},
    )
    assert r.status_code == 422


def test_password_reset_confirm_short_password(client: TestClient) -> None:
    """POST /api/v1/auth/password-reset/confirm with short password returns 422."""
    r = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"email": "admin@aulss9.veneto.it", "otp": "123456", "new_password": "short"},
    )
    assert r.status_code == 422


# ----- Security Headers -----


def test_security_headers(client: TestClient) -> None:
    """Health endpoint returns required security headers."""
    r = client.get("/health")
    assert r.headers.get("x-frame-options") == "DENY"
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert "strict-transport-security" in r.headers
    assert r.headers.get("x-permitted-cross-domain-policies") == "none"


def test_correlation_id(client: TestClient) -> None:
    """Responses include a correlation ID."""
    r = client.get("/health")
    assert "x-correlation-id" in r.headers
    assert len(r.headers["x-correlation-id"]) > 0


# ----- GDPR (Phase 5) -----


def test_gdpr_data_access(client: TestClient) -> None:
    """POST /api/v1/admin/gdpr/access returns data for hashed IP."""
    r = client.post(
        "/api/v1/admin/gdpr/access",
        json={"ip_address": "192.168.1.1"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "ip_hash" in data
    assert "record_count" in data
    assert "records" in data
    assert "exported_at" in data


def test_gdpr_data_erasure(client: TestClient) -> None:
    """POST /api/v1/admin/gdpr/erasure deletes data for hashed IP."""
    r = client.post(
        "/api/v1/admin/gdpr/erasure",
        json={"ip_address": "192.168.1.1"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "ip_hash" in data
    assert "records_deleted" in data
    assert "erased_at" in data


def test_gdpr_processing_register(client: TestClient) -> None:
    """GET /api/v1/admin/gdpr/processing-register returns activities."""
    r = client.get("/api/v1/admin/gdpr/processing-register")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 3
    for activity in data:
        assert "activity" in activity
        assert "purpose" in activity
        assert "legal_basis" in activity
        assert "data_categories" in activity
        assert "retention_period" in activity


# ----- Prometheus Metrics (Phase 5) -----


def test_metrics_endpoint(client: TestClient) -> None:
    """GET /metrics returns Prometheus text format."""
    r = client.get("/metrics")
    assert r.status_code == 200
    body = r.text
    assert "http_requests_total" in body
    assert "http_request_duration_seconds" in body


# ----- AI Act Transparency (Phase 5) -----


def test_ai_transparency(client: TestClient) -> None:
    """GET /api/v1/ai-transparency returns system card."""
    r = client.get("/api/v1/ai-transparency")
    assert r.status_code == 200
    data = r.json()
    assert data["system_name"] == "ULSS 9 Scaligera Healthcare Information Assistant"
    assert "limitations" in data
    assert isinstance(data["limitations"], list)
    assert len(data["limitations"]) > 0
    assert "human_oversight" in data
    assert "risk_category" in data


# ----- Request Size Limit (Phase 5) -----


def test_request_size_limit(client: TestClient) -> None:
    """POST with oversized body returns 413."""
    # Send a request with Content-Length header claiming huge payload
    r = client.post(
        "/api/v1/chat",
        json={"message": "test"},
        headers={
            "x-session-token": _get_session_token(client),
            "content-length": "999999999",
        },
    )
    assert r.status_code == 413


# ----- Helpers -----


def _get_session_token(client: TestClient) -> str:
    """Helper: get a valid session token for testing."""
    r = client.post("/api/v1/session-token")
    return r.json()["session_token"]

