"""WebSocket manager for real-time annotation updates."""

import asyncio
import json
import logging
from typing import Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    Manages WebSocket connections for real-time annotation updates.

    Connections are grouped by job_id, allowing broadcasts to all
    clients viewing a specific transcript.
    """

    def __init__(self):
        # job_id -> set of WebSocket connections
        self._connections: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, job_id: str) -> None:
        """
        Accept and register a WebSocket connection.

        Args:
            websocket: The WebSocket connection
            job_id: The job ID this connection is subscribed to
        """
        await websocket.accept()

        async with self._lock:
            if job_id not in self._connections:
                self._connections[job_id] = set()
            self._connections[job_id].add(websocket)

        logger.debug(f"WebSocket connected for job {job_id}")

    async def disconnect(self, websocket: WebSocket, job_id: str) -> None:
        """
        Unregister a WebSocket connection.

        Args:
            websocket: The WebSocket connection
            job_id: The job ID this connection was subscribed to
        """
        async with self._lock:
            if job_id in self._connections:
                self._connections[job_id].discard(websocket)
                if not self._connections[job_id]:
                    del self._connections[job_id]

        logger.debug(f"WebSocket disconnected for job {job_id}")

    async def broadcast_to_job(self, job_id: str, message: dict) -> int:
        """
        Broadcast a message to all connections for a specific job.

        Args:
            job_id: The job ID to broadcast to
            message: The message to send

        Returns:
            Number of connections the message was sent to
        """
        async with self._lock:
            connections = self._connections.get(job_id, set()).copy()

        if not connections:
            return 0

        message_str = json.dumps(message)
        sent_count = 0
        dead_connections = []

        for websocket in connections:
            try:
                await websocket.send_text(message_str)
                sent_count += 1
            except Exception as e:
                logger.debug(f"Failed to send to WebSocket: {e}")
                dead_connections.append(websocket)

        # Clean up dead connections
        if dead_connections:
            async with self._lock:
                for ws in dead_connections:
                    if job_id in self._connections:
                        self._connections[job_id].discard(ws)

        return sent_count

    async def broadcast_annotation_created(self, job_id: str, annotation: dict) -> int:
        """
        Broadcast an annotation creation event.

        Args:
            job_id: The job ID
            annotation: The annotation data

        Returns:
            Number of connections notified
        """
        return await self.broadcast_to_job(job_id, {
            "type": "annotation_created",
            "annotation": annotation,
        })

    async def broadcast_annotation_updated(self, job_id: str, annotation: dict) -> int:
        """
        Broadcast an annotation update event.

        Args:
            job_id: The job ID
            annotation: The updated annotation data

        Returns:
            Number of connections notified
        """
        return await self.broadcast_to_job(job_id, {
            "type": "annotation_updated",
            "annotation": annotation,
        })

    async def broadcast_annotation_deleted(
        self,
        job_id: str,
        annotation_id: str,
    ) -> int:
        """
        Broadcast an annotation deletion event.

        Args:
            job_id: The job ID
            annotation_id: The deleted annotation ID

        Returns:
            Number of connections notified
        """
        return await self.broadcast_to_job(job_id, {
            "type": "annotation_deleted",
            "annotation_id": annotation_id,
        })

    def get_connection_count(self, job_id: Optional[str] = None) -> int:
        """
        Get the number of active connections.

        Args:
            job_id: Optional job ID to filter by

        Returns:
            Number of connections
        """
        if job_id:
            return len(self._connections.get(job_id, set()))
        return sum(len(conns) for conns in self._connections.values())

    def get_connected_jobs(self) -> list[str]:
        """
        Get list of job IDs with active connections.

        Returns:
            List of job IDs
        """
        return list(self._connections.keys())


# Global instance
_websocket_manager: Optional[WebSocketManager] = None


def get_websocket_manager() -> WebSocketManager:
    """Get or create the global WebSocket manager instance."""
    global _websocket_manager
    if _websocket_manager is None:
        _websocket_manager = WebSocketManager()
    return _websocket_manager
