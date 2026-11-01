# API Design (REST)

Base path: `/api`. JSON over HTTPS. Auth via the session cookie set by `/api/auth/login`, except where noted. Response/request bodies validated by Pydantic. Endpoint list is **[PROVISIONAL]** and will firm up with the OpenAPI schema.

## Auth
| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/auth/register` | public | Create a user account. |
| POST | `/api/auth/login` | public | Check credentials and set the session cookie. |
| POST | `/api/auth/logout` | user | Clear the session cookie. |
| GET | `/api/auth/me` | user | Current user profile. |

## Lessons & Content
| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/lessons` | user | List lessons. |
| GET | `/api/lessons/{lessonId}` | user | Lesson detail. |
| GET | `/api/lessons/{lessonId}/content` | user | Content items (all modes) for a lesson. |
| GET | `/api/videos/{videoId}` | user | Video metadata + checkpoints (not the media bytes). |

## Interactive Question Answering
| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/checkpoints/{checkpointId}/questions` | user | Questions for a video checkpoint. |
| POST | `/api/questions/{questionId}/answer` | user | Submit an answer; returns correctness + gate decision; records a ProgressEvent. |

## BFS Computation / Stepping
| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/graphs` | user | List available graph scenarios. |
| GET | `/api/graphs/{scenarioId}` | user | Scenario detail (nodes/edges). |
| POST | `/api/graphs/{scenarioId}/bfs` | user | Compute BFS from a given `startNode`; returns ordered steps for animation. |

Example `POST /api/graphs/{scenarioId}/bfs` request/response:
```json
// request
{ "startNode": "A" }

// response
{
  "scenarioId": 1,
  "startNode": "A",
  "order": ["A", "B", "C", "D"],
  "steps": [
    {
      "index": 0,
      "action": "visit",
      "node": "A",
      "queueBefore": [],
      "queueAfter": ["B", "C"],
      "visited": ["A"],
      "discovered": ["B", "C"],
      "frontierEdges": [["A","B"], ["A","C"]]
    }
    // ...one entry per BFS step
  ]
}
```

## Scoring
| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/me/score` | user | Current user's total + breakdown. |
| GET | `/api/me/progress` | user | Progress events / completion state. |

(Scores are mutated as a side effect of answer/assessment submissions, not by a direct client "add points" call.)

## Leaderboard
| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/leaderboard` | user | Top-N ranked users + the current user's rank. |

## Assessment
| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/lessons/{lessonId}/assessment` | user | Fetch the assessment (questions). |
| POST | `/api/assessments/{assessmentId}/submit` | user | Submit answers; server grades, decides branch, persists AssessmentResult, returns outcome + scaffold payload if branched. |
| GET | `/api/assessments/{assessmentId}/result` | user | Latest result for the current user. |

Example `POST /api/assessments/{assessmentId}/submit` response:
```json
{
  "assessmentId": 7,
  "score": 0.55,
  "passed": false,
  "branchTaken": "scaffold",
  "scaffold": {
    "reason": "below_threshold",
    "contentItemIds": [12, 15],
    "guidedQuestions": [31, 32]
  }
}
```

## Conventions **[PROVISIONAL]**
- Standard HTTP status codes; error bodies `{ "detail": "..." }`.
- Pagination for list endpoints (`?limit=&offset=`) where needed (leaderboard, lessons).
- OpenAPI/Swagger auto-published at `/api/docs` (FastAPI) and used as the frontend contract.
