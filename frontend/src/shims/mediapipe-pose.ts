
/**
 * Compatibility shim for the unused MediaPipe Pose runtime.
 *
 * This application uses TensorFlow.js MoveNet only.
 * The pose-detection package statically imports MediaPipe,
 * so this shim prevents the unused runtime from breaking Vite builds.
 */
export class Pose {
  constructor() {
    throw new Error(
      'MediaPipe Pose is not enabled. This application uses MoveNet.',
    );
  }
}
