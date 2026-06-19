"""FastAPI app — endpoints become functional as tasks are implemented."""
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI(title="Zycus AI Support API", version="0.2.0")


# ── request models ────────────────────────────────────────────────────────────

class TriageRequest(BaseModel):
    subject: str = ""
    body: str = ""
    use_fixtures: bool = False


# ── endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/triage")
def triage(req: TriageRequest) -> Any:
    from src.data_loader import DataAvailabilityError, DataFormatError
    from src.triage import triage_ticket

    if not req.subject and not req.body:
        raise HTTPException(status_code=422, detail="subject or body must be non-empty")

    try:
        result = triage_ticket(
            {"subject": req.subject, "body": req.body},
            use_fixtures=req.use_fixtures,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except (DataAvailabilityError, DataFormatError) as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return result.model_dump()


@app.get("/accounts/{account_id}/brief")
def account_brief(account_id: str, use_fixtures: bool = False) -> Any:
    from src.account_health import generate_account_brief
    from src.data_loader import DataAvailabilityError, DataFormatError

    try:
        result = generate_account_brief(account_id=account_id, use_fixtures=use_fixtures)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail=f"Account '{account_id}' not found in the loaded dataset.",
        )
    except (DataAvailabilityError, DataFormatError) as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return result.model_dump()
