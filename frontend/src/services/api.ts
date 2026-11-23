
import type {
  HealthStatus,
  PoseAssessment,
  QualityAssessment,
  SessionUploadResponse,
  TrackBox,
  TrackingAssessment,
  BrowserPoseCrop,
  BrowserPoseSubmission,
  BowlerProgressResponse,
} from '../types';

const API_BASE = '/api';

/**
 * Fetch the health status of the backend API.
 */
export async function fetchHealth(): Promise<HealthStatus> {
  const response = await fetch(`${API_BASE}/health`);
  if (!response.ok) {
    throw new Error(`Health check failed: ${response.status}`);
  }
  return response.json();
}

/**
 * Upload a new bowling session.
 */
export function uploadSession(
  formData: FormData,
  onProgress: (percentage: number) => void,
): Promise<SessionUploadResponse> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open('POST', `${API_BASE}/sessions`);

    request.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };

    request.onerror = () =>
      reject(new Error('Upload failed. Check your connection and try again.'));

    request.onload = () => {
      let payload: { detail?: string | { msg?: string }[] };

      try {
        payload = JSON.parse(request.responseText) as typeof payload;
      } catch {
        reject(new Error('The server returned an unreadable response.'));
        return;
      }

      if (request.status < 200 || request.status >= 300) {
        const detail = Array.isArray(payload.detail)
          ? payload.detail.map((item) => item.msg).filter(Boolean).join(' ')
          : payload.detail;

        reject(new Error(detail || `Upload failed (${request.status}).`));
        return;
      }

      resolve(payload as SessionUploadResponse);
    };

    request.send(formData);
  });
}

/**
 * Load previously uploaded sessions.
 */
export async function listSessions(): Promise<SessionUploadResponse[]> {
  const response = await fetch(`${API_BASE}/sessions`);

  if (!response.ok) {
    throw new Error(`Sessions could not be loaded (${response.status}).`);
  }

  return response.json();
}

/**
 * Check the technical quality of a session video.
 */
export async function checkVideoQuality(
  sessionId: string,
): Promise<QualityAssessment> {
  const response = await fetch(
    `${API_BASE}/sessions/${encodeURIComponent(sessionId)}/quality-check`,
    { method: 'POST' },
  );

  const payload = await response.json() as QualityAssessment | { detail?: string };

  if (!response.ok) {
    throw new Error(
      'detail' in payload
        ? payload.detail || `Quality check failed (${response.status}).`
        : `Quality check failed (${response.status}).`,
    );
  }

  return payload as QualityAssessment;
}

/**
 * Run the legacy backend pose assessment.
 * Retained for backward compatibility during migration.
 */
export async function assessPose(
  sessionId: string,
): Promise<PoseAssessment> {
  const response = await fetch(
    `${API_BASE}/sessions/${encodeURIComponent(sessionId)}/pose-assessment`,
    { method: 'POST' },
  );

  const payload = await response.json() as PoseAssessment | { detail?: string };

  if (!response.ok) {
    throw new Error(
      'detail' in payload
        ? payload.detail || `Pose assessment failed (${response.status}).`
        : `Pose assessment failed (${response.status}).`,
    );
  }

  return payload as PoseAssessment;
}

/**
 * Prepare tracked bowler crops for browser-side MoveNet inference.
 */
export async function getBrowserPoseCrops(
  sessionId: string,
): Promise<BrowserPoseCrop[]> {
  const response = await fetch(
    `${API_BASE}/sessions/${encodeURIComponent(sessionId)}/browser-pose-crops`,
  );

  const payload = await response.json() as BrowserPoseCrop[] | { detail?: string };

  if (!response.ok) {
    throw new Error(
      'detail' in payload
        ? payload.detail || `Browser pose crops could not be loaded (${response.status}).`
        : `Browser pose crops could not be loaded (${response.status}).`,
    );
  }

  return payload as BrowserPoseCrop[];
}

/**
 * Submit browser-generated MoveNet predictions to Python.
 * Python maps coordinates to the original video and performs
 * validation, measurements, and report generation.
 */
export async function assessPoseWithBrowserPredictions(
  sessionId: string,
  submission: BrowserPoseSubmission,
  refresh = false,
): Promise<PoseAssessment> {
  const response = await fetch(
    `${API_BASE}/sessions/${encodeURIComponent(sessionId)}/pose-assessment?refresh=${refresh}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(submission),
    },
  );

  const payload = await response.json() as PoseAssessment | { detail?: string };

  if (!response.ok) {
    throw new Error(
      'detail' in payload
        ? payload.detail || `Browser pose assessment failed (${response.status}).`
        : `Browser pose assessment failed (${response.status}).`,
    );
  }

  return payload as PoseAssessment;
}

/** Load a persisted pose assessment without rerunning browser inference. */
export async function getSavedPoseAssessment(sessionId: string): Promise<PoseAssessment | null> {
  const response = await fetch(
    `${API_BASE}/sessions/${encodeURIComponent(sessionId)}/pose-assessment`,
  );
  if (response.status === 404) return null;
  const payload = await response.json() as PoseAssessment | { detail?: string };
  if (!response.ok) {
    throw new Error(
      'detail' in payload
        ? payload.detail || `Saved pose assessment could not be loaded (${response.status}).`
        : `Saved pose assessment could not be loaded (${response.status}).`,
    );
  }
  return payload as PoseAssessment;
}

/**
 * Get the URL of the original session video.
 */
export function sessionVideoUrl(sessionId: string): string {
  return `${API_BASE}/sessions/${encodeURIComponent(sessionId)}/video`;
}

/**
 * Get the URL of a tracking preview frame.
 */
export function trackingPreviewUrl(
  sessionId: string,
  frameNumber: number,
): string {
  return `${API_BASE}/sessions/${encodeURIComponent(sessionId)}/subject-tracking-preview/${frameNumber}?coach_facing=true`;
}

/**
 * Start subject tracking from a coach-selected bounding box.
 */
export async function trackSubject(
  sessionId: string,
  timestampSeconds: number,
  box: TrackBox,
): Promise<TrackingAssessment> {
  const response = await fetch(
    `${API_BASE}/sessions/${encodeURIComponent(sessionId)}/subject-tracking`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        timestamp_seconds: timestampSeconds,
        box,
      }),
    },
  );

  const payload = await response.json() as TrackingAssessment | { detail?: string };

  if (!response.ok) {
    throw new Error(
      'detail' in payload
        ? payload.detail || `Tracking failed (${response.status}).`
        : `Tracking failed (${response.status}).`,
    );
  }

  return payload as TrackingAssessment;
}

/**
 * Confirm the active delivery interval.
 */
export async function confirmSubjectInterval(
  sessionId: string,
  startSeconds: number,
  endSeconds: number,
): Promise<TrackingAssessment> {
  const response = await fetch(
    `${API_BASE}/sessions/${encodeURIComponent(sessionId)}/subject-interval`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        start_seconds: startSeconds,
        end_seconds: endSeconds,
      }),
    },
  );

  const payload = await response.json() as TrackingAssessment | { detail?: string };

  if (!response.ok) {
    throw new Error(
      'detail' in payload
        ? payload.detail || `Interval confirmation failed (${response.status}).`
        : `Interval confirmation failed (${response.status}).`,
    );
  }

  return payload as TrackingAssessment;
}

/**
 * Load the saved subject tracking assessment.
 */
export async function getSubjectTracking(
  sessionId: string,
): Promise<TrackingAssessment> {
  const response = await fetch(
    `${API_BASE}/sessions/${encodeURIComponent(sessionId)}/subject-tracking`,
  );

  const payload = await response.json() as TrackingAssessment | { detail?: string };

  if (!response.ok) {
    throw new Error(
      'detail' in payload
        ? payload.detail || `Tracking could not be loaded (${response.status}).`
        : `Tracking could not be loaded (${response.status}).`,
    );
  }

  return payload as TrackingAssessment;
}


/** Load the saved video and pose-analysis history for one bowler. */
export async function getBowlerProgress(bowlerName: string): Promise<BowlerProgressResponse> {
  const response = await fetch(
    `${API_BASE}/bowlers/progress?bowler_name=${encodeURIComponent(bowlerName)}`,
  );
  const payload = await response.json() as BowlerProgressResponse | { detail?: string };
  if (!response.ok) {
    throw new Error(
      'detail' in payload
        ? payload.detail || `Bowler history could not be loaded (${response.status}).`
        : `Bowler history could not be loaded (${response.status}).`,
    );
  }
  return payload as BowlerProgressResponse;
}
