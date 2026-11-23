/**
 * Health-check response from the API.
 */
export interface HealthStatus {
  status: 'healthy' | 'unhealthy';
  service: string;
  version: string;
}

/**
 * Bowling type supported by the application.
 */
export type BowlingType = 'fast' | 'medium' | 'spin';

/**
 * Reliability status for an individual measurement.
 */
export type ReliabilityStatus = 'reliable' | 'limited' | 'unavailable';

export type BowlingArm = 'right' | 'left';
export type CameraView = 'front' | 'side' | 'rear' | 'other';

export interface SessionUploadResponse {
  session_id: string;
  bowler_name: string;
  session_date: string;
  bowling_type: BowlingType;
  bowling_arm: BowlingArm;
  camera_view: CameraView;
  notes: string | null;
  original_filename: string;
  video_size_bytes: number;
  status: 'uploaded';
  created_at: string;
}

export type QualityMetricStatus = 'reliable' | 'limited' | 'unavailable';
export type OverallQualityStatus = 'suitable' | 'suitable_with_limitations' | 'not_suitable';

export interface QualityMetric {
  name: string;
  value: Record<string, unknown> | null;
  status: QualityMetricStatus;
  explanation: string;
  recommendation: string | null;
}

export interface QualityAssessment {
  session_id: string;
  assessed_at: string;
  overall_assessment: OverallQualityStatus;
  summary: string;
  metadata: {
    width: number | null;
    height: number | null;
    fps: number | null;
    total_frames: number | null;
    duration_seconds: number | null;
    file_size_bytes: number;
  };
  camera_view: string;
  metrics: QualityMetric[];
}

export interface PoseKeypoint {
  name: string;
  x: number | null;
  y: number | null;
  confidence: number | null;
  meets_threshold: boolean;
  raw_x: number | string | null;
  raw_y: number | string | null;
  raw_confidence: number | string | null;
  coordinate_valid: boolean;
  confidence_valid: boolean;
  anatomical_valid: boolean | null;
  temporal_valid: boolean | null;
  validated_visible: boolean;
  validation_state: LandmarkValidationState;
  validation_warnings: string[];
}

export type PoseValidationStatus = 'valid' | 'invalid' | 'limited' | 'unavailable';
export type FrameValidationOutcome = 'validated' | 'partially_validated' | 'insufficient_evidence' | 'validation_failed' | 'not_assessed';
export type LandmarkValidationState = 'confident_and_valid' | 'low_confidence' | 'missing_or_outside_frame' | 'anatomically_implausible' | 'temporally_inconsistent' | 'insufficient_evidence';

export interface TrackBox { x: number; y: number; width: number; height: number }
export interface TrackPoint {
  frame_number: number;
  timestamp_seconds: number;
  box: TrackBox | null;
  status: 'tracked' | 'uncertain' | 'lost' | 'outside_frame';
  feature_count: number;
  appearance_distance: number | null;
  appearance_distance_change?: number | null;
  center_movement_from_previous?: number | null;
  width_scale_from_previous?: number | null;
  height_scale_from_previous?: number | null;
}
export interface ActiveInterval {
  start_seconds: number;
  end_seconds: number;
  confidence: 'high' | 'medium' | 'low';
  reason: string;
}
export interface TrackingAssessment {
  session_id: string;
  selection_status: 'coach_selected';
  selected_at_seconds: number;
  selected_box: TrackBox;
  tracker_method: string;
  scale_estimation_method?: string | null;
  feature_count_semantics?: string;
  appearance_distance_metric?: string;
  appearance_signature: number[];
  duration_seconds: number;
  sampled_track_count: number;
  tracked_sample_count: number;
  tracking_coverage_percent: number;
  tracker_update_coverage_percent?: number | null;
  identity_validation_status?: 'not_independently_verified';
  identity_validation_explanation?: string;
  tracking_interruptions: { start_seconds: number; end_seconds: number; reason: string }[];
  track: TrackPoint[];
  proposed_intervals: ActiveInterval[];
  interval_detection_status: 'proposed' | 'uncertain' | 'unavailable';
  confirmed_interval: ActiveInterval | null;
  interval_source: 'automatic' | 'manual' | 'not_confirmed';
  active_frame_count: number;
  excluded_idle_frame_count: number;
  valid_bowler_pose_frame_count: number;
}

export interface PoseFrame {
  frame_number: number;
  timestamp_seconds: number | null;
  detected: boolean;
  keypoints: PoseKeypoint[];
  original_image_url: string;
  overlay_image_url: string;
  pose_validated: boolean;
  anatomically_plausible: boolean | null;
  validation_status: PoseValidationStatus;
  validation_outcome: FrameValidationOutcome;
  validation_warnings: string[];
  crop_diagnostics: PoseCropDiagnostics | null;
}

export interface PoseCropDiagnostics {
  frame_number: number;
  timestamp_seconds: number | null;
  tracker_frame_number: number | null;
  tracker_timestamp_seconds: number | null;
  tracker_status: TrackPoint['status'] | null;
  tracker_match_delta_seconds: number | null;
  tracker_match_tolerance_seconds: number | null;
  tracker_box: TrackBox | null;
  tracker_update_accepted: boolean | null;
  tracker_rejection_reason: string | null;
  crop: { left: number; top: number; right: number; bottom: number } | null;
  crop_width: number | null;
  crop_height: number | null;
  crop_clipped_by_image_bounds: boolean | null;
  crop_rejection_reason: string | null;
  pose_detected: boolean;
  confident_landmark_count: number;
  coordinates_mapped_to_original_frame: boolean | null;
}

export interface BiomechanicsMeasurement { value: number | null; unit: string; confidence: number | null; status: string; interpretation: string; }
export interface BiomechanicsAnalysis { camera_profile: string; coordinate_space: string; scientific_limitations: string[]; frames: { frame_number: number; timestamp_seconds: number | null; measurements: Record<string, BiomechanicsMeasurement> }[]; summary: Record<string, { median: number | null; min: number | null; max: number | null; valid_frames: number; sampled_frames: number }>; observations: { title: string; finding: string; type: string; evidence_frames: number; coach_action: string; caveat: string }[]; }

export interface PoseAssessment {
  session_id: string;
  assessed_at: string;
  model: string;
  model_input_size: number;
  confidence_threshold: number;
  sampling_interval_seconds: number;
  sampling_note: string;
  sampled_frame_count: number;
  detected_frame_count: number;
  overall_frame_detection_coverage_percent: number;
  overall_detection_status: QualityMetricStatus;
  raw_pose_detection_coverage_percent: number;
  valid_landmark_coverage_percent: number;
  anatomically_plausible_pose_coverage_percent: number;
  pose_validation_status: PoseValidationStatus;
  body_visibility_status: QualityMetricStatus;
  camera_view: CameraView;
  validation_evidence_frame_count: number;
  validation_failed_frame_count: number;
  insufficient_evidence_frame_count: number;
  manual_review_frame_numbers: number[];
  subject_identity_status: 'not_assessed' | 'coach_selected';
  subject_identity_explanation: string;
  tracking: TrackingAssessment | null;
  summary: string;
  regions: {
    name: string;
    visible_frames: number;
    sampled_frames: number;
    frame_coverage_percent: number;
    status: QualityMetricStatus;
    explanation: string;
    validated_visible_frames: number;
    validated_frame_coverage_percent: number;
    validation_status: PoseValidationStatus;
    validation_warnings: string[];
    sufficient_evidence_frames: number;
    failed_frames: number;
    insufficient_evidence_frames: number;
    validation_reason_counts: Record<string, number>;
  }[];
  keypoint_coverage: {
    name: string;
    mean_confidence: number;
    median_confidence: number;
    detected_frames: number;
    sampled_frames: number;
    visible_frame_percent: number;
    coordinate_valid_frames: number;
    validated_visible_frames: number;
    validated_visible_frame_percent: number;
    validation_warning_frames: number;
    validation_state_counts: Record<string, number>;
  }[];
  insufficient_detection_frames: { frame_number: number; timestamp_seconds: number | null; reason: string }[];
  frames: PoseFrame[];
  validation_schema_version: number;
  biomechanics?: BiomechanicsAnalysis;
}


export interface BowlerProgressEntry {
  session: SessionUploadResponse;
  analysis_available: boolean;
  pose_validation_status: PoseValidationStatus;
  detected_frame_count: number;
  sampled_frame_count: number;
  biomechanics_summary: Record<string, {
    median: number | null;
    min: number | null;
    max: number | null;
    valid_frames: number;
    sampled_frames: number;
  }>;
  biomechanics_frames: {
    frame_number: number | null;
    timestamp_seconds: number | null;
    measurements: Record<string, number | null>;
  }[];
}

export interface BowlerProgressResponse {
  bowler_name: string;
  sessions: BowlerProgressEntry[];
}

/**
 * Raw MoveNet keypoint returned by browser inference.
 * Coordinates are relative to the cropped image.
 */
export interface BrowserKeypoint {
  name: string;
  x: number;
  y: number;
  confidence: number;
}

/**
 * Raw predictions for one sampled video frame.
 */
export interface BrowserFramePrediction {
  frame_number: number;
  timestamp_seconds: number;
  keypoints: BrowserKeypoint[];
}

/**
 * Cropped frame prepared by the Python backend.
 */
export interface BrowserPoseCrop {
  frame_number: number;
  timestamp_seconds: number;
  image_url: string;
  crop: {
    left: number;
    top: number;
    right: number;
    bottom: number;
  };
}

/**
 * Predictions submitted by the browser to Python.
 */
export interface BrowserPoseSubmission {
  frames: BrowserFramePrediction[];
}
