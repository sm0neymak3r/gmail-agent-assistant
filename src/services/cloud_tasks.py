"""Cloud Tasks client for reliable batch job processing.

Replaces unreliable self-continuation HTTP calls with guaranteed delivery
via Google Cloud Tasks queue.
"""

import json
import logging
import os
import time
import uuid
from typing import Optional

from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2

logger = logging.getLogger(__name__)


class CloudTasksClient:
    """Wrapper for Google Cloud Tasks operations.

    Handles enqueuing batch worker tasks with proper authentication
    and retry configuration.
    """

    def __init__(
        self,
        queue_path: Optional[str] = None,
        service_url: Optional[str] = None,
        service_account_email: Optional[str] = None,
    ):
        """Initialize Cloud Tasks client.

        Args:
            queue_path: Full Cloud Tasks queue path. Defaults to CLOUD_TASKS_QUEUE env var.
            service_url: Cloud Run service URL. Defaults to constructed from K_SERVICE.
            service_account_email: Service account for OIDC auth. Defaults to SERVICE_ACCOUNT_EMAIL env var.
        """
        self.queue_path = queue_path or os.environ.get("CLOUD_TASKS_QUEUE", "")
        self.service_url = service_url or self._get_service_url()
        self.service_account_email = service_account_email or os.environ.get(
            "SERVICE_ACCOUNT_EMAIL", ""
        )
        self._client: Optional[tasks_v2.CloudTasksClient] = None

    @staticmethod
    def _get_service_url() -> str:
        """Construct Cloud Run service URL from environment.

        Cloud Run provides K_SERVICE with the service name. We construct
        the full URL using the standard Cloud Run URL pattern.

        Returns:
            Service URL or empty string if not on Cloud Run.
        """
        # Check for explicit SERVICE_URL first
        if os.environ.get("SERVICE_URL"):
            return os.environ.get("SERVICE_URL", "")

        # Construct from Cloud Run environment
        k_service = os.environ.get("K_SERVICE", "")
        if not k_service:
            return ""

        region = os.environ.get("REGION", "us-central1")
        project_id = os.environ.get("PROJECT_ID", "")

        # Cloud Run URL pattern: https://{service}-{hash}.{region}.run.app
        # We can get the hash from K_CONFIGURATION or use the newer pattern
        # Newer pattern (2024+): https://{service}-{project-number}.{region}.run.app
        # Even simpler: Cloud Run provides the URL as part of the request

        # For now, construct using a known pattern - the project number
        # is stable and we can pass it via env var if needed
        project_number = os.environ.get("PROJECT_NUMBER", "621335261494")
        return f"https://{k_service}-{project_number}.{region}.run.app"

    @property
    def client(self) -> tasks_v2.CloudTasksClient:
        """Lazy-initialize Cloud Tasks client."""
        if self._client is None:
            self._client = tasks_v2.CloudTasksClient()
        return self._client

    def enqueue_batch_worker(
        self,
        job_id: str,
        delay_seconds: int = 0,
    ) -> str:
        """Enqueue a batch worker task.

        Creates a Cloud Tasks task that will invoke the /batch-worker endpoint
        with OIDC authentication. Cloud Tasks handles retries automatically.

        Args:
            job_id: Batch job ID to process.
            delay_seconds: Optional delay before task execution.

        Returns:
            Task ID for tracking.

        Raises:
            ValueError: If queue_path or service_url not configured.
        """
        if not self.queue_path:
            raise ValueError("CLOUD_TASKS_QUEUE environment variable not set")
        if not self.service_url:
            raise ValueError("SERVICE_URL environment variable not set")

        task_id = str(uuid.uuid4())
        url = f"{self.service_url.rstrip('/')}/batch-worker"

        payload = {
            "job_id": job_id,
            "task_id": task_id,
        }

        # Build the task
        task: dict = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": url,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(payload).encode("utf-8"),
            }
        }

        # Add OIDC token for Cloud Run authentication
        if self.service_account_email:
            task["http_request"]["oidc_token"] = {
                "service_account_email": self.service_account_email,
                "audience": self.service_url,
            }

        # Add schedule time if delay specified
        if delay_seconds > 0:
            schedule_time = timestamp_pb2.Timestamp()
            schedule_time.FromSeconds(int(time.time()) + delay_seconds)
            task["schedule_time"] = schedule_time

        # Create the task
        response = self.client.create_task(
            request={
                "parent": self.queue_path,
                "task": task,
            }
        )

        logger.info(
            f"Enqueued batch worker task: job_id={job_id}, task_id={task_id}, "
            f"delay={delay_seconds}s, task_name={response.name}"
        )

        return task_id

    def get_queue_stats(self) -> dict:
        """Get basic queue statistics.

        Returns:
            Dictionary with queue state and task counts.
        """
        if not self.queue_path:
            return {"error": "Queue not configured"}

        try:
            queue = self.client.get_queue(name=self.queue_path)
            return {
                "name": queue.name,
                "state": queue.state.name,
                "rate_limits": {
                    "max_dispatches_per_second": queue.rate_limits.max_dispatches_per_second,
                    "max_concurrent_dispatches": queue.rate_limits.max_concurrent_dispatches,
                },
            }
        except Exception as e:
            logger.error(f"Failed to get queue stats: {e}")
            return {"error": str(e)}
