# RAG Search
Languages: [English](rag-search.md) | [Русский](rag-search_ru.md)

## Overview

RAG (Retrieval-Augmented Generation) enables semantic search across all stored messages. Users ask natural language questions and receive answers sourced from the actual chat history.

## How It Works

1. **Query Embedding** -- The user's question is converted to a vector embedding
2. **Vector Search** -- pgvector HNSW index finds the most similar messages
3. **Context Expansion** -- Surrounding messages are fetched for context
4. **LLM Answer** -- The question and context are sent to the LLM for answer generation
5. **Source Attribution** -- Original messages are returned as sources

## Using the Search API

```bash
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What did we decide about the deployment schedule?",
    "chat_id": -1001234567890,
    "top_k": 5
  }'
```

Response:

```json
{
  "answer": "Based on the chat history, the team decided to deploy on Friday...",
  "sources": [
    {
      "message_id": 12345,
      "chat_id": -1001234567890,
      "text": "Let's deploy on Friday after the testing is done.",
      "sender_name": "Alice",
      "date": "2026-03-15T10:30:00Z",
      "similarity": 0.87
    }
  ]
}
```

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `RAG_TOP_K` | 5 | Number of messages to retrieve |
| `RAG_SCORE_THRESHOLD` | 0.3 | Minimum similarity score |

## Context Expansion

The context expander fetches messages surrounding the matched results to provide the LLM with better context. This is important because individual messages may lack the full picture.

## Search Scope

Search can be scoped to specific chats or performed across all monitored chats:

```bash
# Search specific chat
{"query": "...", "chat_id": -1001234567890}

# Search all chats
{"query": "..."}
```

## Summary Search

The RAG system also searches across stored summaries, enabling queries like "What happened last week?" to be answered from pre-generated summaries.

## Performance

The HNSW index in pgvector provides fast approximate nearest neighbor search. Index performance depends on:

- Vector dimension (auto-detected from embedding model)
- Number of indexed messages
- HNSW parameters (m, ef_construction, ef_search)

Reindexing is required when the embedding model changes. See [Reindex](reindex.md) for details.
