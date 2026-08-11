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


## 10 August

### Worked on

- Continued development of the AI DevOps Agent backend and GitLab integration.
- Debugged and verified the GitLab webhook endpoint:
  - Implemented the `/webhook/gitlab` FastAPI POST endpoint.
  - Added webhook payload parsing for:
    - Event type.
    - Project name.
    - Branch.
    - Commit SHA.
    - User name.
    - Commit information.
  - Added logging of webhook payload information to the backend terminal.
- Tested the webhook locally using `Invoke-RestMethod`.
- Tested the webhook through ngrok and verified that GitLab could reach the local FastAPI application.
- Debugged an issue where the webhook was returning `200 OK` through ngrok but the expected logging was not appearing in the backend terminal.
- Investigated the issue by:
  - Checking the registered FastAPI routes.
  - Verifying that `/webhook/gitlab` existed.
  - Verifying that the endpoint accepted `POST`.
  - Verifying that the imported `main.py` was the expected file.
  - Inspecting the loaded `gitlab_webhook` function.
  - Checking which process was listening on port `8000`.
  - Terminating the old process and restarting Uvicorn.
- Confirmed that the updated webhook code was finally being executed.
- Successfully tested the webhook and received detailed output in the backend terminal.
- Continued GitLab API integration using reusable helper functions:
  - `make_gitlab_request(endpoint)` for GET requests.
  - `make_gitlab_post_request(endpoint, payload)` for POST requests.
- Implemented GitLab commit-diff retrieval using:
  - `repository/commits/{commit_sha}/diff`
- Implemented diff extraction into readable text containing file names and Git diff content.
- Connected GitLab Merge Request changes to the AI Code Review workflow.
- Tested AI Code Review using real GitLab Merge Request diffs.
- Verified that the AI Code Review could analyze a Git diff and return:
  - Summary.
  - Bugs/issues.
  - Code quality observations.
  - Readability observations.
  - Performance observations.
  - Security observations.
  - Best-practice suggestions.
  - Severity.
- Added and tested the AI Code Suggestions functionality.
- Refined the `suggest_code()` prompt so that suggestions include:
  - File.
  - Previous Code.
  - Suggested Code.
  - Reason for the improvement.
- Added rules to prevent the model from inventing previous code when the diff represents a new file.
- Added rules requiring the model to analyze only code present in the Git diff.
- Added rules to avoid unnecessary or repetitive suggestions.
- Added the `/suggest/{mr_iid}` FastAPI endpoint.
- Tested AI Code Suggestions against GitLab Merge Requests.
- Verified that the suggestion endpoint could retrieve an MR diff, send it to the LLM, and return structured improvement suggestions.
- Added support for AI Code Review and AI Code Suggestions through the backend.
- Connected the AI Code Review and AI Code Suggestions functionality to the existing Flet frontend.
- Debugged a Flet frontend issue caused by an `ft` import/scoping problem.
- Verified that the AI Review page could retrieve and display AI-generated code reviews.
- Verified that the Suggestions page could retrieve and display AI-generated code suggestions.
- Tested posting an AI-generated review comment to a GitLab Merge Request.
- Implemented and tested `post_ai_review()` to create an AI Code Review comment on a GitLab MR.
- Verified that the AI-generated review appeared successfully inside GitLab.
- Continued work on integrating all AI DevOps functionality into the main chatbot interface.

### Learned

- How GitLab webhooks send HTTP requests to an application when repository events occur.
- How to parse GitLab webhook payloads in FastAPI.
- How ngrok can expose a local development server to external services such as GitLab.
- How to debug webhook issues by checking:
  - HTTP status codes.
  - Uvicorn processes.
  - Registered FastAPI routes.
  - Imported Python modules.
  - Active processes on a port.
- How to retrieve GitLab commit diffs through the GitLab REST API.
- How Git diffs can be converted into text suitable for LLM analysis.
- How to design reusable GitLab API helper functions instead of repeating request logic.
- How AI Code Review and AI Code Suggestions can use the same GitLab diff retrieval pipeline while performing different types of analysis.
- How prompt structure affects the reliability and usefulness of LLM-generated code suggestions.
- Why an AI code suggestion system should distinguish between:
  - Previous code.
  - Current code.
  - Suggested improved code.
  - Reason for the change.
- How to validate AI output and reduce hallucinated or unsupported suggestions.
- How FastAPI endpoints can expose AI functionality to the frontend.
- How Flet can consume FastAPI endpoints through a separate API layer.
- How to debug frontend/backend integration issues.
- How AI-generated results can be posted back into GitLab as Merge Request comments.

---

## 11 August

### Worked on

- Continued development and integration of the AI DevOps Agent.
- Completed the AI Code Review and AI Code Suggestions integration with the main chatbot.
- Added routing logic to the `/chat` endpoint so that the chatbot can distinguish between:
  - AI Code Review requests.
  - AI Code Suggestion requests.
  - Normal AI DevOps workflow requests.
- Implemented review request detection for messages such as:
  - `Review MR 9`
  - `Review merge request 9`
- Implemented suggestion request detection for messages such as:
  - `Give me suggestions for MR 9`
  - `Suggest improvements for MR 9`
- Added Merge Request ID extraction from chatbot messages.
- Connected chatbot review requests directly to the existing `review_code()` function.
- Connected chatbot suggestion requests directly to the existing `suggest_code()` function.
- Ensured that the existing LangGraph workflow remains the fallback for normal development requests.
- Verified the three chatbot paths:
  1. Review an existing Merge Request.
  2. Generate improvement suggestions for an existing Merge Request.
  3. Create a new development workflow through the LangGraph agent.
- Updated the Flet chatbot `agent.py` to handle the new backend response types:
  - `type = "review"`
  - `type = "suggestion"`
- Added separate chatbot output handling for:
  - AI Code Review.
  - AI Code Suggestions.
  - Existing LangGraph workflow responses.
- Tested `Review MR 9` directly from the chatbot UI.
- Confirmed that the chatbot successfully displayed the AI Code Review generated from the GitLab MR diff.
- Tested `Give me suggestions for MR 9` directly from the chatbot UI.
- Confirmed that the chatbot successfully displayed AI-generated code suggestions.
- Tested a normal development request:
  - `Create a login system using JWT`
- Confirmed that normal development requests still go through the existing LangGraph workflow.
- Verified the LangGraph workflow still:
  - Validates the request.
  - Retrieves relevant context from Elasticsearch.
  - Analyzes the requirement using Ollama.
  - Generates a branch name.
  - Generates a commit message.
  - Generates an MR title.
  - Pauses for human approval.
  - Provides Approve and Reject options in the chatbot.
- Confirmed that the chatbot now acts as a unified interface for the major AI DevOps capabilities.
- Tested the complete chatbot flow from Flet frontend → FastAPI → AI functionality.
- Committed the completed chatbot integration changes to Git.
- Continued reviewing the project architecture and identifying remaining work before deployment.
- Identified Jenkins deployment as a major remaining project requirement based on the supervisor's instructions.
- Identified webhook automation, testing, error handling, documentation, and deployment as remaining areas for project completion and polish.

### Learned

- How to route multiple AI capabilities through a single chatbot API endpoint.
- How a backend router can determine the user's intent before passing the request to the appropriate workflow.
- How to preserve an existing LangGraph workflow while adding additional capabilities around it.
- How frontend code can interpret different response types returned by a FastAPI backend.
- How to integrate independent AI tools into a unified conversational interface.
- How LangGraph's human-in-the-loop workflow can continue to work independently from chatbot-based code review and suggestion functionality.
- How `thread_id` and LangGraph checkpointing are used to preserve an interrupted workflow between the initial request and the approval decision.
- How FastAPI, Flet, LangGraph, Elasticsearch, Ollama, and GitLab interact as separate layers of the application.
- How to test individual backend endpoints before connecting them to the frontend.
- How to progressively integrate and test a complex system instead of changing the entire application at once.

### Current Project Status

#### Completed

- GitLab API integration.
- GitLab branch retrieval and creation.
- GitLab Merge Request retrieval and creation.
- GitLab Merge Request diff retrieval.
- Reusable GitLab GET and POST helper functions.
- Elasticsearch integration for Merge Request context retrieval.
- Ollama integration for local LLM inference.
- AI Code Review.
- AI Code Suggestions.
- Structured AI suggestions containing previous and suggested code.
- AI-generated review comments posted to GitLab Merge Requests.
- FastAPI backend endpoints for review and suggestions.
- GitLab webhook endpoint.
- Local webhook testing.
- ngrok webhook testing.
- LangGraph-based DevOps workflow.
- Request validation.
- Elasticsearch context retrieval.
- Requirement analysis.
- Human-in-the-loop approval.
- Automated GitLab branch creation.
- Automated GitLab Merge Request creation.
- Flet frontend.
- Flet authentication and navigation.
- AI Review frontend.
- AI Suggestions frontend.
- Main AI DevOps chatbot.
- Integration of Review and Suggestions into the chatbot.
- Integration of the existing LangGraph workflow into the chatbot.
- Testing of the three major chatbot paths.

#### Currently Working

- Consolidating and updating project documentation.
- Improving AI Code Suggestion prompt quality and consistency.
- Preparing the project for deployment.
- Preparing Jenkins-based deployment/CI/CD as requested by the supervisor.

#### Pending

- Jenkins deployment.
- Proper CI/CD pipeline configuration.
- Making the GitLab webhook trigger useful automated processing rather than only receiving/logging payloads.
- Improving automated webhook → diff → AI analysis → GitLab comment flow.
- Adding meaningful automated tests.
- Improving backend error handling and API response validation.
- Improving logging and reducing development-only `print()` statements.
- Final project cleanup and code organization.
- `.env.example` and deployment configuration documentation.
- Complete README and technical documentation.
- Final end-to-end testing.
- Final demonstration preparation.