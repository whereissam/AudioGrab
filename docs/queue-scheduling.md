# Queue, Batch Downloads & Scheduling

This document covers the download queue system, batch operations, and scheduled downloads.

## Priority Queue

The download queue processes jobs based on priority level, allowing important downloads to be processed first.

### Priority Levels

| Level | Name | Use Case |
|-------|------|----------|
| 1-3 | Low | Background downloads, non-urgent |
| 4-6 | Normal | Standard downloads (default: 5) |
| 7-8 | High | Important content |
| 9-10 | Urgent | Time-sensitive downloads |

### Queue Configuration

```env
QUEUE_ENABLED=true
MAX_CONCURRENT_QUEUE_JOBS=5    # Max parallel downloads
DEFAULT_PRIORITY=5              # Default priority for new jobs
```

### API Endpoints

#### Get Queue Status

```bash
GET /api/queue
```

Response:
```json
{
  "pending": 5,
  "processing": 2,
  "max_concurrent": 5,
  "processing_jobs": ["job-id-1", "job-id-2"],
  "jobs": [
    {
      "job_id": "abc123",
      "priority": 8,
      "queued_at": "2026-01-30T10:00:00"
    }
  ]
}
```

#### Update Job Priority

```bash
PATCH /api/download/{job_id}/priority?priority=10
```

Response:
```json
{
  "job_id": "abc123",
  "priority": 10,
  "status": "updated"
}
```

---

## Batch Downloads

Download multiple URLs in a single request with unified settings and progress tracking.

### Create Batch from URL List

```bash
POST /api/batch/download
Content-Type: application/json

{
  "urls": [
    "https://youtube.com/watch?v=abc",
    "https://youtube.com/watch?v=def",
    "https://youtube.com/watch?v=ghi"
  ],
  "name": "My Batch",
  "priority": 7,
  "format": "m4a",
  "quality": "high",
  "webhook_url": "https://my-webhook.com/batch"
}
```

Response:
```json
{
  "batch_id": "batch-uuid",
  "name": "My Batch",
  "total_jobs": 3,
  "job_ids": ["job-1", "job-2", "job-3"],
  "status": "pending",
  "created_at": "2026-01-30T10:00:00"
}
```

### Create Batch from File Upload

Upload a text file with one URL per line:

```bash
POST /api/batch/upload
Content-Type: multipart/form-data

file: urls.txt
name: "Uploaded Batch"
priority: 5
format: m4a
```

Example `urls.txt`:
```
# Comment lines are ignored
https://youtube.com/watch?v=abc
https://youtube.com/watch?v=def

# Empty lines are ignored
https://youtube.com/watch?v=ghi
```

### Get Batch Status

```bash
GET /api/batch/{batch_id}
```

Response:
```json
{
  "batch_id": "batch-uuid",
  "name": "My Batch",
  "total_jobs": 3,
  "completed_jobs": 2,
  "failed_jobs": 0,
  "status": "in_progress",
  "webhook_url": "https://my-webhook.com/batch",
  "created_at": "2026-01-30T10:00:00",
  "updated_at": "2026-01-30T10:05:00"
}
```

### Get Batch Jobs

```bash
GET /api/batch/{batch_id}/jobs
```

### Cancel Batch

Cancels all pending jobs in the batch:

```bash
DELETE /api/batch/{batch_id}
```

Response:
```json
{
  "batch_id": "batch-uuid",
  "cancelled_jobs": 5,
  "message": "Cancelled 5 pending jobs"
}
```

### List All Batches

```bash
GET /api/batch?status=in_progress&limit=50
```

---

## Scheduled Downloads

Schedule downloads to start at a specific time.

### Schedule a Download

```bash
POST /api/schedule/download
Content-Type: application/json

{
  "url": "https://youtube.com/watch?v=abc",
  "scheduled_at": "2026-02-01T03:00:00Z",
  "priority": 8,
  "format": "m4a",
  "quality": "high",
  "webhook_url": "https://my-webhook.com/scheduled"
}
```

Response:
```json
{
  "job_id": "job-uuid",
  "url": "https://youtube.com/watch?v=abc",
  "scheduled_at": "2026-02-01T03:00:00",
  "priority": 8,
  "status": "pending",
  "created_at": "2026-01-30T10:00:00"
}
```

### Configuration

```env
SCHEDULER_ENABLED=true
SCHEDULER_CHECK_INTERVAL=60    # Check every 60 seconds
```

### List Scheduled Jobs

```bash
GET /api/schedule
```

Response:
```json
{
  "scheduled_jobs": [
    {
      "job_id": "job-uuid",
      "url": "https://youtube.com/watch?v=abc",
      "scheduled_at": "2026-02-01T03:00:00",
      "priority": 8,
      "status": "pending",
      "created_at": "2026-01-30T10:00:00"
    }
  ],
  "total": 1
}
```

### Cancel Scheduled Job

```bash
DELETE /api/schedule/{job_id}
```

### Update Scheduled Job

Update the scheduled time or priority:

```bash
PATCH /api/schedule/{job_id}?scheduled_at=2026-02-02T10:00:00Z&priority=10
```

---

## How It Works

### Queue Processing Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        QUEUE PROCESSING FLOW                             │
└─────────────────────────────────────────────────────────────────────────┘

New Download Request
        │
        ▼
┌───────────────────┐
│ Create Job Record │ (SQLite, status=pending)
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Add to Priority   │ (heapq sorted by -priority, timestamp)
│      Queue        │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Queue Manager     │ (runs in background)
│ Processes Jobs    │ (respects max_concurrent limit)
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Download & Save   │
│ Update Status     │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Send Webhook      │ (if configured)
│ Notification      │
└───────────────────┘
```

### Scheduler Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         SCHEDULER FLOW                                   │
└─────────────────────────────────────────────────────────────────────────┘

Every SCHEDULER_CHECK_INTERVAL seconds:
        │
        ▼
┌───────────────────┐
│ Query jobs where  │
│ scheduled_at <=   │
│ now()             │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Clear scheduled_at│
│ field             │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Enqueue to        │
│ Priority Queue    │
└───────────────────┘
```

---

## Best Practices

### Batch Downloads

1. **Use webhooks** for large batches to get notified when complete
2. **Set appropriate priority** - don't use high priority for all jobs
3. **Monitor batch status** via the API instead of polling individual jobs

### Scheduling

1. **Use UTC times** to avoid timezone issues
2. **Schedule during off-peak hours** for better performance
3. **Set priority appropriately** - scheduled jobs compete with regular jobs

### Queue Management

1. **Adjust `MAX_CONCURRENT_QUEUE_JOBS`** based on your server capacity
2. **Use priority wisely** - overusing high priority defeats the purpose
3. **Monitor queue depth** to detect backlogs
