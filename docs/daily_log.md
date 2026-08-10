## 26 July

### Worked on

- GitHub repository setup and project organization.
- Elasticsearch bulk indexing improvements using Python generators (`yield`).
- GitLab Merge Request diff retrieval.
- Initial AI Code Review implementation using Ollama.

### Learned

- Git repository setup and version control workflow.
- Python generators (`yield`) and their use in efficient data processing.
- Elasticsearch `bulk()` helper for indexing.
- Fetching GitLab Merge Request diffs using the GitLab API.

---

## 28 July

### Worked on

- Implemented AI Code Suggestions using Qwen2.5-Coder.
- Added the `suggest_code()` function for merge request analysis.
- Created the `/suggest/{mr_iid}` FastAPI endpoint.
- Tested AI code suggestions using a GitLab Merge Request.
- Updated project documentation.

### Learned

- Prompt engineering for AI-generated code suggestions.
- Separating AI Code Review and AI Code Suggestions into independent modules.
- Testing AI workflows using GitLab Merge Requests.

## 26 July

### Worked on

- GitHub repository setup and project organization.
- Elasticsearch bulk indexing improvements using Python generators (`yield`).
- GitLab Merge Request diff retrieval.
- Initial AI Code Review implementation using Ollama.

### Learned

- Git repository setup and version control workflow.
- Python generators (`yield`) and their use in efficient data processing.
- Elasticsearch `bulk()` helper for indexing.
- Fetching GitLab Merge Request diffs using the GitLab API.

---

## 28 July

### Worked on

- Implemented AI Code Suggestions using Qwen2.5-Coder.
- Added the `suggest_code()` function for merge request analysis.
- Created the `/suggest/{mr_iid}` FastAPI endpoint.
- Tested AI Code Suggestions using GitLab Merge Requests.
- Updated project documentation.
- Added environment-based AI model configuration using `.env`.
- Tested AI Code Review and AI Code Suggestions with Ollama.

### Learned

- Prompt engineering for AI-generated code suggestions.
- Separating AI Code Review and AI Code Suggestions into independent modules.
- Testing AI workflows using GitLab Merge Requests.
- Using environment variables to configure AI models.
- Debugging Ollama model configuration and API integration.

---

## 31 July

### Worked on

- Structured the Flet frontend into separate views and modules.
- Implemented the frontend authentication flow with login and registration.
- Added the main application dashboard and navigation.
- Connected the Flet frontend to the FastAPI backend through a dedicated API layer.
- Implemented the Branches view:
  - View GitLab branches.
  - Create new GitLab branches.
- Implemented the Merge Requests view:
  - View merge requests.
  - Create merge requests.
  - View individual merge requests.
- Implemented the AI Code Review frontend.
- Connected AI Code Review to the existing FastAPI and GitLab workflow.
- Implemented the AI Code Suggestions frontend.
- Tested AI Code Review and AI Code Suggestions with real GitLab Merge Requests.
- Debugged frontend/backend integration issues.
- Added handling for Elasticsearch being unavailable during Merge Request retrieval.
- Tested the complete flow between Flet, FastAPI, GitLab, Elasticsearch, and Ollama.

### Learned

- Structuring a Flet application using separate views.
- Separating frontend API communication from UI logic.
- Connecting a frontend application to FastAPI endpoints.
- Handling frontend state and navigation in Flet.
- Debugging API and service-integration errors.
- Understanding how GitLab, FastAPI, Elasticsearch, LangGraph, and Ollama fit together as separate layers of the application.
- Designing graceful behavior when a supporting service such as Elasticsearch is unavailable.
