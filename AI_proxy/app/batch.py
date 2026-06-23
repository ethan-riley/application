from __future__ import annotations

import json
import threading
import time
from typing import Any, TYPE_CHECKING
from uuid import uuid4

from fastapi import HTTPException, status

from app.schemas import (
    BatchCreateRequest,
    BatchObject,
    BatchRequestCounts,
    ChatCompletionRequest,
    FileObject,
)

if TYPE_CHECKING:
    from app.control_plane import ControlPlane


class BatchService:
    def __init__(self, control_plane: ControlPlane):
        self._cp = control_plane
        self._files: dict[str, tuple[FileObject, bytes]] = {}
        self._batches: dict[str, BatchObject] = {}
        self._lock = threading.Lock()

    # ── Files ────────────────────────────────────────────────────────────────

    def upload_file(self, filename: str, purpose: str, content: bytes) -> FileObject:
        file_id = f"file-{uuid4().hex}"
        obj = FileObject(
            id=file_id,
            bytes=len(content),
            created_at=int(time.time()),
            filename=filename,
            purpose=purpose,
        )
        with self._lock:
            self._files[file_id] = (obj, content)
        return obj

    def list_files(self, purpose: str | None = None) -> list[FileObject]:
        with self._lock:
            files = [obj for obj, _ in self._files.values()]
        if purpose:
            files = [f for f in files if f.purpose == purpose]
        return files

    def get_file(self, file_id: str) -> FileObject:
        with self._lock:
            entry = self._files.get(file_id)
        if not entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File {file_id} not found")
        return entry[0]

    def delete_file(self, file_id: str) -> dict[str, Any]:
        with self._lock:
            if file_id not in self._files:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File {file_id} not found")
            del self._files[file_id]
        return {"id": file_id, "object": "file", "deleted": True}

    def get_file_content(self, file_id: str) -> bytes:
        with self._lock:
            entry = self._files.get(file_id)
        if not entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File {file_id} not found")
        return entry[1]

    # ── Batches ───────────────────────────────────────────────────────────────

    def create_batch(self, request: BatchCreateRequest) -> BatchObject:
        self.get_file(request.input_file_id)
        batch_id = f"batch_{uuid4().hex}"
        now = int(time.time())
        batch = BatchObject(
            id=batch_id,
            endpoint=request.endpoint,
            input_file_id=request.input_file_id,
            completion_window=request.completion_window,
            status="validating",
            created_at=now,
            expires_at=now + 86400,
            metadata=request.metadata,
        )
        with self._lock:
            self._batches[batch_id] = batch
        thread = threading.Thread(target=self._process_batch, args=(batch_id,), daemon=True)
        thread.start()
        return batch

    def list_batches(self) -> list[BatchObject]:
        with self._lock:
            return list(self._batches.values())

    def get_batch(self, batch_id: str) -> BatchObject:
        with self._lock:
            batch = self._batches.get(batch_id)
        if not batch:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Batch {batch_id} not found")
        return batch

    def cancel_batch(self, batch_id: str) -> BatchObject:
        with self._lock:
            batch = self._batches.get(batch_id)
            if not batch:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Batch {batch_id} not found")
            if batch.status in {"completed", "failed", "cancelled", "expired"}:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Batch {batch_id} cannot be cancelled (status: {batch.status})",
                )
            now = int(time.time())
            batch = batch.model_copy(update={"status": "cancelling", "cancelling_at": now})
            self._batches[batch_id] = batch
        return batch

    # ── Processing ────────────────────────────────────────────────────────────

    def _process_batch(self, batch_id: str) -> None:
        now = int(time.time())
        with self._lock:
            batch = self._batches.get(batch_id)
            if not batch:
                return
            batch = batch.model_copy(update={"status": "in_progress", "in_progress_at": now})
            self._batches[batch_id] = batch
            content = self._files.get(batch.input_file_id, (None, b""))[1]

        try:
            lines = [line for line in content.decode("utf-8").splitlines() if line.strip()]
        except UnicodeDecodeError as exc:
            now = int(time.time())
            with self._lock:
                batch = self._batches.get(batch_id)
                if batch:
                    self._batches[batch_id] = batch.model_copy(update={
                        "status": "failed",
                        "failed_at": now,
                        "errors": {"message": f"Input file is not valid UTF-8: {exc}"},
                    })
            return

        results: list[str] = []
        completed = 0
        failed = 0

        for line in lines:
            with self._lock:
                current = self._batches.get(batch_id)
                if current and current.status == "cancelling":
                    break
            result = self._execute_jsonl_request(line)
            results.append(json.dumps(result))
            if result.get("error") is None:
                completed += 1
            else:
                failed += 1

        now = int(time.time())
        with self._lock:
            current = self._batches.get(batch_id)
            if not current:
                return
            if current.status == "cancelling":
                self._batches[batch_id] = current.model_copy(update={
                    "status": "cancelled",
                    "cancelled_at": now,
                })
                return
            batch = current.model_copy(update={"status": "finalizing", "finalizing_at": now})
            self._batches[batch_id] = batch

        output_bytes = "\n".join(results).encode("utf-8")
        output_file = self.upload_file(
            filename=f"batch_{batch_id}_output.jsonl",
            purpose="batch_output",
            content=output_bytes,
        )

        now = int(time.time())
        with self._lock:
            batch = self._batches[batch_id]
            batch = batch.model_copy(update={
                "status": "completed",
                "completed_at": now,
                "output_file_id": output_file.id,
                "request_counts": BatchRequestCounts(
                    total=len(lines),
                    completed=completed,
                    failed=failed,
                ),
            })
            self._batches[batch_id] = batch

    def _execute_jsonl_request(self, line: str) -> dict[str, Any]:
        result_id = f"batch_req_{uuid4().hex}"
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            return {"id": result_id, "custom_id": None, "response": None, "error": {"code": "parse_error", "message": str(exc)}}

        custom_id = item.get("custom_id")
        body = item.get("body", {})

        try:
            req = ChatCompletionRequest(**body)
            response = self._cp.handle_chat_completion(req)
            return {
                "id": result_id,
                "custom_id": custom_id,
                "response": {"status_code": 200, "body": response.model_dump()},
                "error": None,
            }
        except HTTPException as exc:
            return {
                "id": result_id,
                "custom_id": custom_id,
                "response": None,
                "error": {"code": str(exc.status_code), "message": exc.detail},
            }
        except Exception as exc:
            return {
                "id": result_id,
                "custom_id": custom_id,
                "response": None,
                "error": {"code": "internal_error", "message": str(exc)},
            }
