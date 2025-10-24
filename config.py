"""Configuration management for the stream server."""

import os
from dataclasses import dataclass


@dataclass
class MotionConfig:
    """Motion detection configuration."""
    threshold: int = 25
    min_area: int = 1000
    learning_rate: float = 0.001


@dataclass
class VideoConfig:
    """Video recording configuration."""
    fps: int = 30
    pre_buffer_duration: int = 5  # seconds
    post_motion_duration: int = 5  # seconds
    output_dir: str = "recordings"
    fourcc: str = "mp4v"


@dataclass
class CameraConfig:
    """Camera configuration."""
    resolution = (640, 480)
    format: str = "RGB888"


@dataclass
class ServerConfig:
    """HTTP server configuration."""
    host: str = ""
    port: int = 8000


@dataclass
class DatabaseConfig:
    """Database configuration."""
    db_name: str = "events.db"
    
    @property
    def db_path(self):
        """Get full database path."""
        return os.path.join(VideoConfig().output_dir, self.db_name)


@dataclass
class AppConfig:
    """Main application configuration."""
    motion = None
    video = None
    camera = None
    server = None
    database = None
    
    def __post_init__(self):
        """Initialize sub-configs if not provided."""
        if self.motion is None:
            self.motion = MotionConfig()
        if self.video is None:
            self.video = VideoConfig()
        if self.camera is None:
            self.camera = CameraConfig()
        if self.server is None:
            self.server = ServerConfig()
        if self.database is None:
            self.database = DatabaseConfig()