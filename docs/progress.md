# Project Progress

## Version 1 — Core Backend and Frontend Completed

### Completed Features

#### Backend

- FastAPI backend
- GitLab API integration
- Reusable GitLab GET request helper
- Reusable GitLab POST request helper
- GitLab branch retrieval
- GitLab branch creation
- GitLab Merge Request retrieval
- GitLab Merge Request creation
- GitLab Merge Request diff retrieval
- GitLab commit diff retrieval
- GitLab webhook endpoint
- Local GitLab webhook testing
- ngrok webhook testing
- Elasticsearch indexing
- Elasticsearch Merge Request retrieval
- Retrieval-Augmented Generation (RAG)
- LangGraph workflow
- Request validation
- Context retrieval from Elasticsearch
- AI requirement analysis
- Human-in-the-loop approval
- Automated branch creation after approval
- Automated Merge Request creation after approval

#### AI Features

- Ollama local LLM integration
- Qwen2.5-Coder integration for AI Code Suggestions
- AI-powered Code Review
- AI-powered Code Suggestions
- Structured AI Code Suggestions containing:
  - Previous Code
  - Current Code
  - Suggested Code
  - Reason
- Review endpoint:
  - `/review/{mr_iid}`
- Suggestion endpoint:
  - `/suggest/{mr_iid}`
- AI-generated review comment posting to GitLab Merge Requests

#### Frontend

- Flet frontend
- Login and registration interface
- Application dashboard and navigation
- Branch management interface
- Merge Request management interface
- AI Code Review interface
- AI Code Suggestions interface
- Dedicated frontend API layer
- Frontend-to-FastAPI API integration

#### AI DevOps Chatbot

- Natural-language AI DevOps Agent interface
- Chatbot connected to FastAPI `/chat` endpoint
- Chatbot routing for AI Code Review requests
- Chatbot routing for AI Code Suggestion requests
- Chatbot integration with the existing LangGraph workflow
- Chatbot support for human approval/rejection of development workflows
- Review requests such as:
  - `Review MR 9`
- Suggestion requests such as:
  - `Give me suggestions for MR 9`
- Normal development requests continue to use the LangGraph workflow

---

## Current Architecture

```text
                         Flet Frontend
                              |
             +----------------+----------------+
             |                |                |
             v                v                v
         GitLab Views     AI Review       AI Suggestions
             |                |                |
             +----------------+----------------+
                              |
                         AI Chatbot
                              |
                         POST /chat
                              |
                     Backend Request Router
                              |
              +---------------+---------------+
              |               |               |
              v               v               v
           Review          Suggestion       Create
              |               |               |
              v               v               v
        GitLab MR Diff   GitLab MR Diff   LangGraph
              |               |               |
              v               v               v
        review_code()    suggest_code()   Validation
                                              |
                                         Elasticsearch
                                              |
                                           Ollama
                                              |
                                      Human Approval
                                         /       \
                                      Reject     Approve
                                                   |
                                             Create Branch
                                                   |
                                             Create MR