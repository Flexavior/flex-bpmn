"""Optional Camunda 8 REST deploy (disabled unless explicitly enabled)."""

from __future__ import annotations

import requests

from app.config import CAMUNDA_BASE_URL, CAMUNDA_DEPLOY_ENABLED, CAMUNDA_TOKEN
from app.utils.logger import get_logger

log = get_logger(__name__)


class CamundaError(Exception):
    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


def deploy_bpmn(process_id: str, bpmn: str) -> dict:
    if not CAMUNDA_DEPLOY_ENABLED:
        raise CamundaError(
            "Camunda deploy is disabled. Set CAMUNDA_DEPLOY_ENABLED=true in backend/.env "
            "and restart the API after c8run is running on port 8080.",
            status_code=503,
        )
    if "http://www.omg.org/spec/BPMN/20100524/MODEL" not in bpmn:
        raise CamundaError("Refusing to deploy XML that is not BPMN 2.0 MODEL.", status_code=422)
    url = CAMUNDA_BASE_URL.rstrip("/") + "/v2/deployments"
    headers = {"Accept": "application/json"}
    if CAMUNDA_TOKEN:
        headers["Authorization"] = f"Bearer {CAMUNDA_TOKEN}"
    files = {
        "resources": (f"{process_id}.bpmn", bpmn.encode("utf-8"), "application/xml"),
    }
    try:
        resp = requests.post(url, files=files, headers=headers, timeout=(5, 30))
    except requests.RequestException as exc:
        raise CamundaError(
            f"Cannot reach Camunda at {url}. Start c8run first (see README).",
            status_code=503,
        ) from exc
    if resp.status_code >= 400:
        raise CamundaError(
            f"Camunda rejected deploy (HTTP {resp.status_code}): {resp.text[:300]}",
            status_code=resp.status_code if resp.status_code < 500 else 502,
        )
    try:
        body = resp.json()
    except ValueError:
        body = {"raw": resp.text[:300]}
    log.info("Deployed %s to Camunda", process_id)
    return {"process_id": process_id, "deployment": body}
