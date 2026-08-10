# Project Progress

## Version 1 (Core Backend Completed)

### Completed Features

- FastAPI backend
- GitLab API integration
- Elasticsearch indexing
- Retrieval-Augmented Generation (RAG)
- LangGraph workflow
- Human approval
- Branch creation
- Merge Request creation
- Merge Request diff retrieval
- AI-powered code review using Ollama
- AI-powered code suggestions using Qwen2.5-Coder
- Review endpoint (`/review/{mr_iid}`)
- Suggestion endpoint (`/suggest/{mr_iid}`)
- Flet frontend
- Login and registration interface
- Application dashboard and navigation
- Branch management interface
- Merge Request management interface
- AI Code Review interface
- AI Code Suggestions interface
- Frontend-to-FastAPI API integration

### Current Workflow

User Request
→ Elasticsearch
→ Ollama / LangGraph
→ Human Approval
→ Branch
→ Merge Request
→ Fetch Merge Request Diff
→ AI Code Review
→ AI Code Suggestions

### Current Status

- Core backend workflow is functional.
- Merge Requests can be created through the application.
- Merge Request diffs are fetched using the GitLab API.
- AI generates code reviews based on Merge Request diffs.
- AI generates code improvement suggestions based on Merge Request diffs.
- Flet frontend is connected to the FastAPI backend.
- Users can interact with GitLab branches and Merge Requests through the frontend.
- AI Code Review and AI Code Suggestions are accessible through the frontend.

## Current Development

### Pending Features

- Search interface and Elasticsearch search integration in the frontend.
- AI chatbot for natural-language interaction with the application.
- Push event workflow.
- AI Code Review for Push events.
- Automatic posting of AI reviews to GitLab.
- Automatic posting of AI suggestions to GitLab.
- Developer approval/rejection workflow for AI suggestions.
- Applying and storing accepted AI-generated code.
- Preventing accepted suggestions from appearing in the final AI review.
- Improved duplicate Merge Request detection.