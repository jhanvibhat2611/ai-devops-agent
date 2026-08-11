# Next Steps

## Immediate

- Implement automated AI Code Review triggering from GitLab Push events.
- Implement automated AI Code Suggestions triggering from GitLab Push events.
- Connect GitLab webhook events to the AI analysis pipeline.
- Automatically post AI Code Review results as comments on relevant GitLab Merge Requests.
- Automatically post AI Code Suggestions as comments on relevant GitLab Merge Requests.
- Complete the automated Push → Diff → AI Analysis → GitLab Comment workflow.
- Complete and validate the Search frontend and Elasticsearch integration.
- Improve frontend error handling, loading states, and user feedback.
- Improve backend error handling and API response validation.
- Replace development-only `print()` statements with structured logging where appropriate.

## Upcoming

- Implement developer approval/rejection workflow specifically for AI-generated code suggestions.
- Define how accepted AI-generated code should be stored and applied.
- Determine whether accepted code changes should be written locally or pushed to a remote GitLab branch.
- Prevent accepted AI-generated changes from being incorrectly re-identified as new issues in subsequent AI reviews.
- Improve duplicate Merge Request detection and context retrieval.
- Standardize API response structures across the backend.
- Add automated tests for:
  - GitLab API functions.
  - AI Code Review.
  - AI Code Suggestions.
  - Webhook processing.
  - LangGraph workflow.
  - Chatbot endpoints.
- Add better validation for Merge Request IDs and GitLab API failures.
- Complete end-to-end testing of the integrated system.
- Prepare deployment configuration and documentation.

## Deployment & CI/CD

- Set up Jenkins for the project as requested by the supervisor.
- Configure Jenkins to build/test the application.
- Integrate GitLab repository events with Jenkins.
- Define the CI/CD pipeline stages.
- Test the Jenkins pipeline with the project.
- Document the deployment and CI/CD workflow.

## Future

- Improve semantic search over historical Merge Requests.
- Improve Elasticsearch retrieval and ranking of similar Merge Requests.
- Add GitLab Pipeline integration.
- Automate CI/CD-based AI code review.
- Introduce configurable AI review severity/quality thresholds.
- Explore automated Merge Request approval based on configurable AI review thresholds.
- Improve the AI DevOps Agent's natural-language intent detection.
- Expand chatbot capabilities to support more GitLab operations.