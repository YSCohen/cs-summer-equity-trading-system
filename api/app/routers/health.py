from fastapi import APIRouter
import os
import socket
import time

router = APIRouter(tags=["Health"])

START_TIME = time.time()


@router.get("/probe")
async def probe():
    hostname = socket.gethostname()  # In K8s, this defaults to the Pod Name

    return {
        "status": "ok",
        # K8s Downward API Info
        "k8s_node": os.getenv("NODE_NAME", "unknown"),
        "k8s_namespace": os.getenv("POD_NAMESPACE", "unknown"),
        "k8s_pod_ip": os.getenv("POD_IP", "unknown"),
        "k8s_pod_name": hostname,
        # GitOps Info
        "environment": os.getenv("ENVIRONMENT", "dev"),
        # Runtime Info
        "process_id": os.getpid(),
        "uptime_seconds": round(time.time() - START_TIME, 2),
        "Image": os.getenv("CURRENT_IMAGE", "unknown"),
    }
