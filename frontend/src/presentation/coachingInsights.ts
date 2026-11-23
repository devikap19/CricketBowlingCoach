import type { BiomechanicsAnalysis } from '../types';

export type CoachingInsight = {
  id: string;
  title: string;
  status: 'positive' | 'review' | 'limited';
  observation: string;
  tryNext: string;
  benefit: string;
  evidence: string;
  coachCue: string;
};

const labels: Record<string, string> = {
  shoulder_line_tilt: 'Shoulder line',
  hip_line_tilt: 'Hip line',
  left_elbow_angle: 'Left arm bend',
  right_elbow_angle: 'Right arm bend',
  left_knee_angle: 'Left leg bend',
  right_knee_angle: 'Right leg bend',
};

function valuesFor(analysis: BiomechanicsAnalysis, key: string): number[] {
  return analysis.frames
    .map((frame) => frame.measurements[key]?.value)
    .filter((value): value is number => typeof value === 'number' && Number.isFinite(value));
}

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

function lineInsight(analysis: BiomechanicsAnalysis, key: 'shoulder_line_tilt' | 'hip_line_tilt'): CoachingInsight {
  const raw = valuesFor(analysis, key);
  const values = raw.map(Math.abs);
  const title = labels[key];
  const part = key === 'shoulder_line_tilt' ? 'shoulders' : 'hips';
  if (values.length < 3) {
    return {
      id: key, title, status: 'limited',
      observation: `Only ${values.length} moments show both ${part} clearly enough for this measurement. The app cannot fairly judge this part of the action yet.`,
      tryNext: key === 'shoulder_line_tilt'
        ? 'Review the original clip at the beginning, around the delivery stride and during the follow-through. Check that both shoulders stay in view.'
        : 'Review the original clip and make sure the waist/hip area is not hidden by clothing, arms or the edge of the frame.',
      benefit: key === 'shoulder_line_tilt'
        ? 'Seeing both shoulders through the action helps a coach judge balance and upper-body control.'
        : 'Clear hip landmarks help a coach see whether the body stays controlled as the bowler moves through the crease.',
      evidence: `${values.length} measurable moments out of ${analysis.frames.length}; no missing positions have been guessed.`,
      coachCue: key === 'shoulder_line_tilt' ? 'Keep the head and upper body relaxed; do not force the shoulders flat.' : 'Let the hips move naturally, while avoiding a sudden sideways collapse.',
    };
  }
  const range = Math.max(...values) - Math.min(...values);
  const typical = median(values);
  const status: CoachingInsight['status'] = range <= 8 ? 'positive' : range >= 16 ? 'review' : 'limited';
  if (key === 'shoulder_line_tilt') {
    return {
      id: key, title, status,
      observation: status === 'positive'
        ? `Your shoulder line stayed fairly similar across the visible moments (variation ${range.toFixed(1)}°). That is a useful sign of repeatability in this camera view.`
        : `Your shoulder line moved by ${range.toFixed(1)}° across the clip (typical absolute tilt ${typical.toFixed(1)}°). This may be natural rotation through the action, or a change in balance; the 2D view alone cannot decide which.`,
      tryNext: status === 'positive'
        ? 'Keep the same relaxed rhythm. Check that the head does not suddenly fall to one side as the bowling arm comes through.'
        : 'Watch the frames where the shoulder line changes most. Practise a slow walk-through: approach, gather, delivery stride and follow-through. Keep your head comfortably over your moving base; do not try to hold both shoulders perfectly level.',
      benefit: 'A controlled upper body can make the action easier to repeat and may help the bowler stay balanced. This measurement cannot promise extra pace or accuracy.',
      evidence: `${values.length} measurable moments; image-plane line variation, not a 3D shoulder rotation.`,
      coachCue: status === 'positive' ? 'Repeat the same relaxed upper-body rhythm.' : 'Head steady; chest controlled; allow natural shoulder turn.',
    };
  }
  return {
    id: key, title, status,
    observation: status === 'positive'
      ? `Your hip line stayed fairly similar across the sampled moments (variation ${range.toFixed(1)}°). The clip does not show a large repeated sideways change.`
      : `Your hip line changed by ${range.toFixed(1)}° across the clip (typical absolute tilt ${typical.toFixed(1)}°). This is worth checking against the video because normal bowling movement also changes hip position.`,
    tryNext: status === 'positive'
      ? 'Keep the movement comfortable and repeatable. Do not deliberately lock your hips to keep the line flat.'
      : 'Replay the moments with the largest hip-line change. Practise a slow approach into the delivery stride, keeping your trunk supported over your legs. Let the hips turn naturally rather than forcing them to stay level.',
    benefit: 'A controlled base can help the bowler transfer movement through the action and finish in balance. A flatter hip line is not automatically better.',
    evidence: `${values.length} measurable moments; projected hip-line variation only.`,
    coachCue: status === 'positive' ? 'Keep a comfortable, repeatable base.' : 'Support the trunk with the legs; avoid an uncontrolled sideways drop.',
  };
}

function jointInsight(analysis: BiomechanicsAnalysis, key: string, bowlingArm: 'left' | 'right'): CoachingInsight {
  const values = valuesFor(analysis, key);
  const title = labels[key] ?? key.replaceAll('_', ' ');
  const isElbow = key.includes('elbow');
  const side = key.startsWith('left') ? 'left' : 'right';
  const isBowlingArm = isElbow && side === bowlingArm;
  const summary = analysis.summary[key];
  if (values.length < 3) {
    return {
      id: key, title, status: 'limited',
      observation: `${title} could only be measured in ${values.length} moments. There is not enough clear evidence to say whether this movement is coordinated.`,
      tryNext: isBowlingArm
        ? 'Keep the bowling arm fully inside the frame. Review the original video and check that the arm moves smoothly through the action.'
        : isElbow
          ? 'Keep both arms visible and review how this arm works with the bowling arm. Do not try to copy a fixed elbow angle.'
          : 'Keep the full leg visible, especially the hip, knee and ankle, then review the landing and follow-through in the original clip.',
      benefit: isBowlingArm
        ? 'A clear, smooth arm path is important to review with a coach; this 2D angle cannot judge bowling legality or release speed.'
        : isElbow
          ? 'Coordinated arm movement can support balance and rhythm.'
          : 'A controlled leg movement can help the bowler stay balanced through the stride and finish.',
      evidence: `${values.length} measurable moments; other moments are left unavailable rather than estimated.`,
      coachCue: isBowlingArm ? 'Smooth bowling-arm path; never force the elbow to a number.' : isElbow ? 'Let the opposite arm support balance naturally.' : 'Land and move through the stride under control.',
    };
  }
  const min = Math.min(...values), max = Math.max(...values), range = max - min;
  const typical = summary?.median ?? median(values);
  if (isElbow && isBowlingArm) {
    return {
      id: key, title, status: 'limited',
      observation: `Your ${side} bowling-arm angle changed from ${min.toFixed(1)}° to ${max.toFixed(1)}° (median ${typical.toFixed(1)}°). The arm naturally changes shape during bowling, so this range is not a fault and cannot assess elbow legality.`,
      tryNext: 'Watch the bowling arm from the start of the action through release. Look for a smooth, repeatable path rather than a sudden stop or an intentional elbow snap. Practise shadow bowling slowly, then at a comfortable rhythm.',
      benefit: 'A repeatable arm path can help timing and control. This camera cannot measure release speed, and it must not be used to judge a throwing action or legality.',
      evidence: `${values.length} measurable moments; projected 2D shoulder–elbow–wrist angle.`,
      coachCue: 'Smooth arm path and consistent rhythm — do not chase a fixed elbow angle.',
    };
  }
  if (isElbow) {
    return {
      id: key, title, status: range > 100 ? 'review' : 'limited',
      observation: `Your ${side} support-arm angle varied by ${range.toFixed(1)}° (median ${typical.toFixed(1)}°). This arm can help with balance and timing, but the angle alone cannot tell us whether its movement is effective.`,
      tryNext: 'In a slow shadow-bowling drill, notice when the support arm rises and when it comes down. Try to make that movement smooth and timed with the bowling arm, rather than letting it swing randomly.',
      benefit: 'A well-timed support arm can help organise the upper body and maintain balance as the bowling arm comes through.',
      evidence: `${values.length} measurable moments; projected 2D angle, not a 3D joint measurement.`,
      coachCue: 'Use the non-bowling arm as a balance and timing aid; keep it relaxed.',
    };
  }
  return {
    id: key, title, status: range > 35 ? 'review' : 'limited',
    observation: `Your ${side} leg angle changed from ${min.toFixed(1)}° to ${max.toFixed(1)}° (median ${typical.toFixed(1)}°). Bending and straightening are expected as you move; the useful question is whether the leg supports a controlled stride.`,
    tryNext: 'Replay the frames around the largest change. Practise a slow approach and delivery stride, landing comfortably with the knee tracking in the same general direction as the foot. Do not lock the knee or force a deep bend.',
    benefit: 'A controlled stride and stable landing can help you keep balance and move smoothly into the follow-through.',
    evidence: `${values.length} measurable moments; projected 2D hip–knee–ankle angle.`,
    coachCue: 'Controlled stride; comfortable knee bend; finish balanced.',
  };
}

export function buildCoachingInsights(analysis: BiomechanicsAnalysis, bowlingArm: 'left' | 'right'): CoachingInsight[] {
  const insights = [
    lineInsight(analysis, 'shoulder_line_tilt'),
    lineInsight(analysis, 'hip_line_tilt'),
    ...['left_elbow_angle', 'right_elbow_angle', 'left_knee_angle', 'right_knee_angle']
      .filter((key) => (analysis.summary[key]?.valid_frames ?? 0) > 0)
      .map((key) => jointInsight(analysis, key, bowlingArm)),
  ];
  return insights;
}

export function frameStageLabel(index: number, total: number): string {
  if (total <= 1) return 'Only sampled moment';
  const fraction = index / (total - 1);
  if (fraction < 0.34) return 'Earlier in the selected clip';
  if (fraction < 0.67) return 'Middle of the selected clip';
  return 'Later in the selected clip';
}
