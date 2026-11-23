
import * as tf from '@tensorflow/tfjs';
import * as poseDetection from '@tensorflow-models/pose-detection';

import type {
  BrowserPoseCrop,
  BrowserPoseSubmission,
  BrowserFramePrediction,
  BrowserKeypoint,
} from '../types';

const KEYPOINT_NAMES = [
  'nose',
  'left_eye',
  'right_eye',
  'left_ear',
  'right_ear',
  'left_shoulder',
  'right_shoulder',
  'left_elbow',
  'right_elbow',
  'left_wrist',
  'right_wrist',
  'left_hip',
  'right_hip',
  'left_knee',
  'right_knee',
  'left_ankle',
  'right_ankle',
];

let detector: poseDetection.PoseDetector | null = null;
let detectorPromise: Promise<poseDetection.PoseDetector> | null = null;

/**
 * Load MoveNet Lightning once and reuse it.
 */
export async function loadMoveNet(): Promise<poseDetection.PoseDetector> {
  if (detector) return detector;

  if (detectorPromise) return detectorPromise;

  detectorPromise = (async () => {
    try {
      const webglAvailable = await tf.setBackend('webgl');

      if (!webglAvailable) {
        await tf.setBackend('cpu');
      }

      await tf.ready();

      const loadedDetector = await poseDetection.createDetector(
        poseDetection.SupportedModels.MoveNet,
        {
          modelType: poseDetection.movenet.modelType.SINGLEPOSE_LIGHTNING,
          enableSmoothing: false,
        },
      );

      detector = loadedDetector;
      return loadedDetector;
    } catch (error) {
      detectorPromise = null;
      throw new Error(
        `MoveNet could not be loaded: ${
          error instanceof Error ? error.message : String(error)
        }`,
      );
    }
  })();

  return detectorPromise;
}

/**
 * Load a crop image from the backend.
 */
async function loadCropImage(imageUrl: string): Promise<HTMLImageElement> {
  const image = new Image();
  image.src = imageUrl;

  try {
    await image.decode();
  } catch {
    throw new Error(`Could not load browser pose crop: ${imageUrl}`);
  }

  if (!image.naturalWidth || !image.naturalHeight) {
    throw new Error(`Invalid crop image: ${imageUrl}`);
  }

  return image;
}

/**
 * Keep normalized coordinates within the range 0 to 1.
 */
function normalizeCoordinate(value: number, dimension: number): number {
  return Math.max(0, Math.min(1, value / dimension));
}

/**
 * Run MoveNet on one cropped bowler image.
 */
async function predictCrop(
  model: poseDetection.PoseDetector,
  crop: BrowserPoseCrop,
): Promise<BrowserFramePrediction> {
  const image = await loadCropImage(crop.image_url);

  const poses = await model.estimatePoses(image, {
    maxPoses: 1,
    flipHorizontal: false,
  });

  // A missed frame must not cancel the whole video analysis. Preserve the
  // sampled moment and send explicit zero-confidence landmarks so the backend
  // can mark it as unavailable while still analysing every other frame.
  const detectedKeypoints = poses[0]?.keypoints ?? [];

  const keypoints: BrowserKeypoint[] = KEYPOINT_NAMES.map((name) => {
    const point = detectedKeypoints.find(
      (keypoint) => keypoint.name === name,
    );

    if (!point) {
      return { name, x: 0.5, y: 0.5, confidence: 0 };
    }

    return {
      name,
      x: normalizeCoordinate(point.x, image.naturalWidth),
      y: normalizeCoordinate(point.y, image.naturalHeight),
      confidence: Math.max(0, Math.min(1, point.score ?? 0)),
    };
  });

  return {
    frame_number: crop.frame_number,
    timestamp_seconds: crop.timestamp_seconds,
    keypoints,
  };
}

/**
 * Run browser-side MoveNet inference on all prepared crops.
 * Individual frames with no pose are retained with zero-confidence landmarks;
 * they do not stop inference for the remaining frames.
 */
export async function runBrowserPoseInference(
  crops: BrowserPoseCrop[],
  onProgress?: (completed: number, total: number) => void,
): Promise<BrowserPoseSubmission> {
  if (!crops.length) {
    throw new Error('No browser pose crops were provided.');
  }

  const model = await loadMoveNet();

  const frames: BrowserFramePrediction[] = [];

  // Process sequentially to avoid excessive browser memory usage.
  for (let index = 0; index < crops.length; index += 1) {
    const prediction = await predictCrop(model, crops[index]);

    frames.push(prediction);
    onProgress?.(index + 1, crops.length);
  }

  return { frames };
}

/**
 * Release the MoveNet detector when it is no longer needed.
 */
export async function disposeMoveNet(): Promise<void> {
  if (detector) {
    detector.dispose();
    detector = null;
  }

  detectorPromise = null;
}
