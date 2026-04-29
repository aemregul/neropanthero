"""
Celery Configuration - Production-Ready Background Task Processing.

Enterprise-grade job queue with:
- Redis as message broker
- Result backend for task tracking
- Retry policies
- Rate limiting
- Priority queues
- Scheduled tasks (beat)
"""
from celery import Celery
from kombu import Queue, Exchange
import os

# Redis URL from environment
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Celery app instance
celery_app = Celery(
    "nero_panthero",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "app.tasks.video_tasks",
        "app.tasks.image_tasks",
        "app.tasks.cleanup_tasks",
        "app.tasks.notification_tasks",
    ]
)

# ============== CELERY CONFIGURATION ==============

celery_app.conf.update(
    # Task serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    
    # Timezone
    timezone="Europe/Istanbul",
    enable_utc=True,
    
    # Task execution
    task_acks_late=True,  # Acknowledge after task completes (safer)
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # Fair task distribution
    
    # Task result storage
    result_expires=86400,  # Results expire after 24 hours
    result_extended=True,  # Store additional task metadata
    
    # Task limits
    task_time_limit=3600,  # Hard limit: 1 hour max
    task_soft_time_limit=3000,  # Soft limit: 50 minutes
    
    # Rate limiting (per worker)
    worker_concurrency=4,
    
    # Retry configuration
    task_default_retry_delay=60,  # Wait 1 minute before retry
    task_max_retries=3,
    
    # Memory management
    worker_max_tasks_per_child=100,  # Restart worker after 100 tasks
    
    # Task tracking
    task_track_started=True,
    task_send_sent_event=True,
)

# ============== PRIORITY QUEUES ==============

# Define exchanges
default_exchange = Exchange("default", type="direct")
priority_exchange = Exchange("priority", type="direct")
video_exchange = Exchange("video", type="direct")

# Define queues with priorities
celery_app.conf.task_queues = (
    # High priority - notifications, quick tasks
    Queue("high", priority_exchange, routing_key="high", queue_arguments={"x-max-priority": 10}),
    
    # Default - standard tasks
    Queue("default", default_exchange, routing_key="default"),
    
    # Video processing - long running, dedicated workers
    Queue("video", video_exchange, routing_key="video"),
    
    # Low priority - cleanup, analytics
    Queue("low", default_exchange, routing_key="low"),
)

# Default queue
celery_app.conf.task_default_queue = "default"
celery_app.conf.task_default_exchange = "default"
celery_app.conf.task_default_routing_key = "default"

# Route tasks to specific queues
celery_app.conf.task_routes = {
    # Video tasks go to video queue
    "app.tasks.video_tasks.*": {"queue": "video"},
    
    # Cleanup tasks are low priority
    "app.tasks.cleanup_tasks.*": {"queue": "low"},
    
    # Notifications are high priority
    "app.tasks.notification_tasks.*": {"queue": "high"},
    
    # Everything else goes to default
    "*": {"queue": "default"},
}

# ============== SCHEDULED TASKS (CELERY BEAT) ==============

celery_app.conf.beat_schedule = {
    # Clean up expired trash items every hour
    "cleanup-expired-trash": {
        "task": "app.tasks.cleanup_tasks.cleanup_expired_trash",
        "schedule": 3600.0,  # Every hour
    },
    
    # Clean up old task results every 6 hours
    "cleanup-old-results": {
        "task": "app.tasks.cleanup_tasks.cleanup_old_results",
        "schedule": 21600.0,  # Every 6 hours
    },
    
    # Update Pinecone indexes every day at 3 AM
    "reindex-pinecone": {
        "task": "app.tasks.cleanup_tasks.reindex_pinecone",
        "schedule": {
            "hour": 3,
            "minute": 0,
        },
    },
}

# ============== TASK BASE CLASS ==============

from celery import Task
from typing import Optional


class BaseTask(Task):
    """Base task with retry and error handling."""
    
    autoretry_for = (Exception,)
    retry_backoff = True
    retry_backoff_max = 600  # Max 10 minutes between retries
    retry_jitter = True
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called when task fails after all retries."""
        print(f"❌ Task {self.name}[{task_id}] failed: {exc}")
        # TODO: Send notification to admin
    
    def on_success(self, retval, task_id, args, kwargs):
        """Called when task succeeds."""
        print(f"✅ Task {self.name}[{task_id}] completed successfully")
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Called when task is retried."""
        print(f"🔄 Task {self.name}[{task_id}] retrying: {exc}")


# Set as default base
celery_app.Task = BaseTask
