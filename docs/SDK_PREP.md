# NestyAI Client SDK Design Guidelines

This document outlines the blueprints and architectural patterns for future NestyAI client SDKs (Python, JavaScript/TypeScript, and Kotlin/Android).

---

## 1. Python SDK

A lightweight Python client wrapper designed for script integration, backend service calls, and testing.

### Proposed Interface

```python
class NestyClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8000", api_key: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def chat(self, model: str, messages: list[dict], **kwargs) -> ChatCompletionResponse:
        """
        Non-streaming chat completions.
        """
        ...

    def stream_chat(self, model: str, messages: list[dict], **kwargs) -> Iterator[ChatChunkEvent]:
        """
        Streaming completions yielding ChatChunkEvent chunks and returning metadata.
        """
        ...

    def list_models(self) -> list[dict]:
        """
        List active model configs.
        """
        ...

    def list_conversations(self, limit: int = 20, offset: int = 0) -> list[dict]:
        ...

    def get_conversation(self, conversation_id: str) -> dict:
        ...

    def export_conversation(self, conversation_id: str) -> dict:
        ...
```

---

## 2. JavaScript / TypeScript SDK

A universal promise-based JavaScript library designed to run on Node.js and modern browsers.

### Proposed Interface

```typescript
export class NestyClient {
  constructor(private baseUrl: string = "http://127.0.0.1:8000", private apiKey?: string) {}

  async chat(params: ChatParams): Promise<ChatCompletionResponse> {
    // Standard Fetch implementation
  }

  async *streamChat(params: ChatParams): AsyncIterableIterator<ChatEvent> {
    // ReadableStream fetch SSE events parser
  }

  async listModels(): Promise<ModelCard[]> {
    ...
  }

  // Conversation Helpers
  async listConversations(params?: ListConversationsParams): Promise<Conversation[]> { ... }
  async getConversation(id: string): Promise<ConversationDetail> { ... }
  async deleteConversation(id: string): Promise<boolean> { ... }
}
```

---

## 3. Kotlin / Android SDK

Guidelines for mobile apps communicating with the NestyAI gateway.

### Architectural Security Warnings
*   > [!CAUTION]
    > **Do NOT hardcode the API Key or Secrets inside a production APK.**
    > Decompiling Android APKs is trivial and exposes secrets to the public.
    >
    > **Secure Solution**: Public mobile apps should route traffic through a backend proxy session that appends authorization context safely, or rely on a user-authenticated login flow.

### SSE Streaming Considerations
*   Use standard **OkHttp** and **EventSource** interfaces to handle persistent server-sent events connection.
*   Run network connections outside the Main (UI) thread using Kotlin coroutines (`Dispatchers.IO`).
*   Handle connection drops, device sleep, and offline transitions gracefully with retry/exponential backoff.

### Draft SSE Implementation Pattern
```kotlin
fun connectStream(baseUrl: String, proxyToken: String) {
    val request = Request.Builder()
        .url("$baseUrl/v1/chat/completions")
        // Token refers to a secure proxy token, not the raw gateway master key!
        .addHeader("Authorization", "Bearer $proxyToken")
        .post(payloadBody)
        .build()

    // Establish event stream reader in an IO coroutine context
}
```
