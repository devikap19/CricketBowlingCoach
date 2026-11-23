
"""CricketBowlingCoach API — Application configuration."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application-wide settings loaded from environment variables."""

    app_name: str = "CricketBowlingCoach API"
    app_version: str = "0.1.0"
    debug: bool = False

    # Storage paths (relative to project root)
    upload_dir: str = "../storage/uploads"
    processed_dir: str = "../storage/processed"
    reports_dir: str = "../storage/reports"
    sessions_dir: str = "../storage/sessions"
    max_upload_size_bytes: int = 200 * 1024 * 1024

    # Video quality thresholds
    quality_min_width: int = 640
    quality_min_height: int = 360
    quality_min_fps: float = 24.0
    quality_dark_pixel_threshold: int = 40
    quality_bright_pixel_threshold: int = 220
    quality_max_extreme_pixel_fraction: float = 0.35
    quality_min_blur_variance: float = 60.0
    quality_min_decodable_samples: int = 3

    # Pose analysis and sampling
    pose_sampling_interval_seconds: float = 0.5
    pose_max_sampled_frames: int = 60
    pose_confidence_threshold: float = 0.25
    pose_min_region_frame_coverage: float = 0.4
    pose_reliable_region_frame_coverage: float = 0.8
    pose_fallback_sample_frame_stride: int = 15

    # CORS
    cors_origins: list[str] = ["http://localhost:5173"]

    class Config:
        env_file = ".env"
        env_prefix = "CBC_"


settings = Settings()
