"""Coach feedback and printable session-report endpoints."""
import html, json, uuid
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from app.core.config import settings

router = APIRouter()

class CoachFeedback(BaseModel):
    coach_name: str = Field(min_length=1, max_length=100)
    rating: int = Field(ge=1, le=5)
    comment: str = Field(min_length=1, max_length=3000)
    delivery_frame_number: int | None = Field(default=None, ge=0)
    recommendation: str = Field(default="", max_length=2000)


def _paths(session_id):
    try: sid = str(uuid.UUID(session_id))
    except ValueError: raise HTTPException(404, "Session not found.") from None
    root = Path(settings.sessions_dir).resolve()
    meta = root / f"{sid}.json"
    if not meta.is_file(): raise HTTPException(404, "Session not found.")
    return sid, root

@router.get("/sessions/{session_id}/coach-feedback")
def list_feedback(session_id: str):
    sid, root = _paths(session_id); path = root / f"{sid}.feedback.json"
    if not path.exists(): return {"session_id":sid,"feedback":[]}
    try: return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError): raise HTTPException(500,"Feedback could not be read.") from None

@router.post("/sessions/{session_id}/coach-feedback")
def add_feedback(session_id: str, payload: CoachFeedback):
    sid, root = _paths(session_id); path = root / f"{sid}.feedback.json"
    try:
        current = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"session_id":sid,"feedback":[]}
        entry = payload.model_dump() | {"created_at":datetime.now(timezone.utc).isoformat(),"feedback_id":str(uuid.uuid4())}
        current["feedback"].append(entry)
        temp = path.with_suffix(".feedback.part")
        temp.write_text(json.dumps(current, indent=2), encoding="utf-8"); temp.replace(path)
        return entry
    except (OSError, ValueError): raise HTTPException(500,"Feedback could not be saved.") from None

@router.get("/sessions/{session_id}/report", response_class=HTMLResponse)
def session_report(session_id: str):
    sid, root = _paths(session_id)
    meta = json.loads((root/f"{sid}.json").read_text(encoding="utf-8"))
    pose_path = root/f"{sid}.pose.json"
    if not pose_path.exists(): raise HTTPException(409,"Run pose assessment before generating a report.")
    pose = json.loads(pose_path.read_text(encoding="utf-8"))
    feedback_path = root/f"{sid}.feedback.json"
    feedback = json.loads(feedback_path.read_text(encoding="utf-8")) if feedback_path.exists() else {"feedback":[]}
    bio = pose.get("biomechanics", {})
    rows = "".join(f"<tr><td>{html.escape(k.replace('_',' ').title())}</td><td>{html.escape(str(v.get('median')))}</td><td>{html.escape(str(v.get('valid_frames')))} / {html.escape(str(v.get('sampled_frames')))}</td></tr>" for k,v in bio.get("summary",{}).items())
    notes = "".join(f"<li><b>{html.escape(x.get('title','Coach note'))}</b> — {html.escape(x.get('comment',''))} (Rating: {x.get('rating','-')}/5)</li>" for x in feedback.get("feedback",[]))
    observations = "".join(f"<li><b>{html.escape(x.get('title','Observation'))}:</b> {html.escape(x.get('finding',''))}<br><small>{html.escape(x.get('caveat',''))}</small></li>" for x in bio.get("observations",[]))
    title = html.escape(meta.get("bowler_name","Bowling session"))
    limitations = "".join(f"<li>{html.escape(x)}</li>" for x in bio.get("scientific_limitations",[]))
    return HTMLResponse(f'''<!doctype html><html><head><meta charset="utf-8"><title>CricketBowlingCoach report</title><style>body{{font:15px Arial;max-width:900px;margin:40px auto;padding:0 20px;color:#18212f}}h1,h2{{color:#173b63}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccd4df;padding:9px;text-align:left}}.note{{background:#f2f6fb;padding:14px;border-radius:8px}}@media print{{button{{display:none}}}}</style></head><body><button onclick="window.print()">Print / Save as PDF</button><h1>CricketBowlingCoach — Session report</h1><h2>{title}</h2><p>Date: {html.escape(str(meta.get('session_date','Not recorded')))} · Bowling type: {html.escape(str(meta.get('bowling_type','Not recorded')))} · Camera: End-on, batsman's end</p><h2>Pose summary</h2><p>{html.escape(str(pose.get('summary','')))}</p><p>Detected frames: {pose.get('detected_frame_count',0)} / {pose.get('sampled_frame_count',0)}</p><h2>Front-view measurements</h2><table><tr><th>Measurement</th><th>Median</th><th>Valid frames</th></tr>{rows}</table><h2>Technique observations for coach review</h2><ul>{observations or '<li>No sufficiently supported observations were generated.</li>'}</ul><h2>Coach feedback</h2><ul>{notes or '<li>No coach feedback recorded.</li>'}</ul><h2>Interpretation limitations</h2><div class="note"><ul>{limitations}</ul><p>Measurements are 2D image-plane estimates, not 3D biomechanical measurements or medical diagnoses. A coach must interpret them in context.</p></div><p>Generated by CricketBowlingCoach.</p></body></html>''')
