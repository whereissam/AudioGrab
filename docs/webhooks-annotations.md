# Webhooks & Collaborative Annotations

## Webhooks

Receive HTTP notifications when jobs complete or fail.

### Configuration

```env
DEFAULT_WEBHOOK_URL=https://your-webhook.com/hook
WEBHOOK_RETRY_ATTEMPTS=3
WEBHOOK_RETRY_DELAY=60
```

### Events

| Event | Description |
|-------|-------------|
| `job_completed` | Download/transcription completed successfully |
| `job_failed` | Job failed with error |
| `batch_completed` | All jobs in a batch finished |
| `test` | Test event from `/api/webhooks/test` |

### Payload Format

```json
{
  "event": "job_completed",
  "job_id": "abc123",
  "status": "completed",
  "job_type": "download",
  "content_info": {
    "title": "Content Title",
    "duration_seconds": 3600
  },
  "file_path": "/output/file.m4a",
  "file_size_mb": 42.5,
  "error": null,
  "batch_id": "batch-uuid",
  "timestamp": "2026-01-30T10:00:00Z"
}
```

### Per-Job Webhooks

Set webhook URL when creating a job:

```json
{
  "url": "https://youtube.com/watch?v=abc",
  "webhook_url": "https://my-webhook.com/job"
}
```

### Testing Webhooks

```bash
POST /api/webhooks/test
{
  "url": "https://your-webhook.com/hook"
}
```

---

## Collaborative Annotations

Add comments and notes to transcripts with real-time synchronization.

### Creating Annotations

```bash
POST /api/jobs/{job_id}/annotations
{
  "content": "Great point about X here",
  "user_id": "user123",
  "user_name": "John Doe",
  "segment_start": 120.5,
  "segment_end": 135.0
}
```

### Replying to Annotations

```bash
POST /api/annotations/{annotation_id}/reply
{
  "content": "I agree with this",
  "user_id": "user456",
  "user_name": "Jane Smith"
}
```

### Real-time Updates (WebSocket)

Connect to receive live annotation updates:

```javascript
const ws = new WebSocket('ws://localhost:8000/api/jobs/{job_id}/annotations/ws');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  switch (data.type) {
    case 'annotation_created':
      // New annotation added
      break;
    case 'annotation_updated':
      // Annotation content changed
      break;
    case 'annotation_deleted':
      // Annotation removed
      break;
  }
};

// Keep connection alive
setInterval(() => ws.send('ping'), 30000);
```

### WebSocket Message Types

| Type | Payload |
|------|---------|
| `connected` | `{ job_id, message }` |
| `annotation_created` | `{ annotation }` |
| `annotation_updated` | `{ annotation }` |
| `annotation_deleted` | `{ annotation_id }` |

### Annotation Response Format

```json
{
  "id": "annotation-uuid",
  "job_id": "job-uuid",
  "content": "Annotation text",
  "user_id": "user123",
  "user_name": "John Doe",
  "segment_start": 120.5,
  "segment_end": 135.0,
  "parent_id": null,
  "replies": [
    {
      "id": "reply-uuid",
      "content": "Reply text",
      "user_id": "user456",
      "user_name": "Jane Smith",
      "parent_id": "annotation-uuid",
      "replies": [],
      "created_at": "2026-01-30T10:05:00",
      "updated_at": "2026-01-30T10:05:00"
    }
  ],
  "created_at": "2026-01-30T10:00:00",
  "updated_at": "2026-01-30T10:00:00"
}
```
