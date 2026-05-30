from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.core.orchestrator import StreamHandle, StreamOutcome


class MockChatOrchestratorStream:
    async def create_chat_completion_stream(self, request_id: str, request) -> StreamHandle:
        async def events():
            # Emit chunk
            yield (
                'data: {"id":"chatcmpl_chunk","object":"chat.completion.chunk","created":1672531199,'
                '"model":"nesty-combined-1.0","provider":"groq","choices":[{"index":0,'
                '"delta":{"content":"Hi"},"finish_reason":null}]}\n\n'
            )
            # Emit metadata
            yield (
                'data: {"id":"chatcmpl_chunk","object":"chat.completion.metadata","created":1672531199,'
                '"model":"nesty-combined-1.0","provider":"groq","guard":{"input_redacted":false,'
                '"output_redacted":false,"redaction_count":0,"categories":[]},"tools":{"used":[],"search":'
                '{"enabled":false,"query":null,"results_count":0,"failed":false},"executions":[]},'
                '"sources":[],"usage":{"prompt_tokens":1,"completion_tokens":1,"total_tokens":2},'
                '"orchestration":{"enabled":false,"requested":"auto","used":false},'
                '"semantic_recall":{"enabled":false,"requested":"auto","used":false},'
                '"model_alias":"nesty-combined-1.0"}\n\n'
            )
            # Emit DONE
            yield 'data: [DONE]\n\n'

        return StreamHandle(
            events=events(),
            outcome=StreamOutcome(
                provider="groq",
                status="success",
                assistant_content="Hi",
            )
        )


def test_streaming_chat_completion_contract(monkeypatch, tmp_path) -> None:
    db_file = tmp_path / "stream_contract.db"
    settings = Settings(
        app_env="development",
        diagnostics_enabled=True,
        require_api_key=False,
        rate_limit_enabled=False,
        nesty_db_path=str(db_file),
    )
    monkeypatch.setattr("app.deps.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.chat.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.chat.get_orchestrator", lambda: MockChatOrchestratorStream())

    app = create_app(settings)
    client = TestClient(app)

    payload = {
        "model": "nesty-combined-1.0",
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": True,
        "store": False,
    }

    with client.stream("POST", "/v1/chat/completions", json=payload) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        
        lines = list(response.iter_lines())
        # Filter empty lines
        data_lines = [line.strip() for line in lines if line.strip()]
        
        assert len(data_lines) == 3
        assert data_lines[0].startswith("data: ")
        assert data_lines[1].startswith("data: ")
        assert data_lines[2] == "data: [DONE]"

        import json
        chunk_event = json.loads(data_lines[0][6:])
        assert chunk_event["object"] == "chat.completion.chunk"
        assert chunk_event["choices"][0]["delta"]["content"] == "Hi"

        metadata_event = json.loads(data_lines[1][6:])
        assert metadata_event["object"] == "chat.completion.metadata"
        assert metadata_event["model_alias"] == "nesty-combined-1.0"
        assert "guard" in metadata_event
        assert "tools" in metadata_event
        assert "sources" in metadata_event
