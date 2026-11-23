import type { PoseAssessment } from '../types/index.ts';

type RegionResult = PoseAssessment['regions'][number];

export interface CoachRegionStatus {
  label: string;
  tone: 'green' | 'amber' | 'red' | 'muted';
  explanation: string;
}

export function coachRegionEvidence(region: RegionResult) {
  return {
    detected: { count: region.visible_frames, total: region.sampled_frames },
    sufficient: { count: region.sufficient_evidence_frames, total: region.sampled_frames },
    validated: { count: region.validated_visible_frames, total: region.sampled_frames },
  };
}

/** Translate backend region evidence and validation states without deriving new coverage metrics. */
export function coachRegionStatus(region: RegionResult, schemaVersion: number): CoachRegionStatus {
  if (schemaVersion < 2 || region.validation_status === 'unavailable') {
    return {
      label: region.visible_frames > 0 ? 'Validation unavailable' : 'Insufficient evidence',
      tone: 'muted',
      explanation: region.visible_frames > 0
        ? 'Some landmarks were detected, but this result does not include enough validation data to assess the region.'
        : 'There was not enough landmark evidence to assess this region.',
    };
  }

  if (region.validation_status === 'invalid' || region.failed_frames > 0) {
    return {
      label: 'Some checks flagged landmarks',
      tone: 'red',
      explanation: 'Checks flagged predicted landmarks in some moments. Review the sampled frames below.',
    };
  }

  if (region.validation_status === 'valid') {
    return {
      label: 'Checks passed where evidence was available',
      tone: 'green',
      explanation: 'Applicable checks passed for the moments with sufficient evidence. This does not assess bowling technique.',
    };
  }

  if (region.validation_status === 'limited') {
    return {
      label: 'Limited evidence',
      tone: 'amber',
      explanation: region.insufficient_evidence_frames > 0
        ? 'Some sampled moments did not have enough clear landmarks to complete the region checks.'
        : 'Some region checks could not be completed. Review the sampled frames below.',
    };
  }

  return {
    label: 'Insufficient evidence',
    tone: 'muted',
    explanation: 'There was not enough evidence to assess this region.',
  };
}

export function coachFrameStatus(outcome: PoseAssessment['frames'][number]['validation_outcome'], detected: boolean) {
  if (outcome === 'validated') return 'Landmarks detected; applicable checks passed.';
  if (outcome === 'partially_validated') return 'Landmarks detected; some checks were limited.';
  if (outcome === 'validation_failed') return 'Some predicted landmarks were flagged for review.';
  if (outcome === 'insufficient_evidence') {
    return detected
      ? 'A pose was detected, but there was not enough evidence to check it.'
      : 'The pose was not clear enough to assess in this moment.';
  }
  return 'Validation was not available for this moment.';
}
