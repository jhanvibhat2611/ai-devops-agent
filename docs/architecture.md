# Architecture

User
│
▼
FastAPI
│
▼
LangGraph Workflow
│
├── Retrieve Context (Elasticsearch)
├── Analyze Requirement (Ollama)
├── Human Approval
├── Create Branch
└── Create Merge Request

GitLab APIs

- Branch API
- Merge Request API

AI

- Ollama
- Llama 3

Database

- Elasticsearch