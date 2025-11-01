"""Configuration management for the RTSP stream server."""

from dataclasses import dataclass


@dataclass
class CameraConfig:
    """Camera configuration optimized for Pi 3B+ with H.264."""
    resolution = (1280, 720)  # 720p - good balance for Pi 3B+
    format = "YUV420"  # Required for H.264 encoding


@dataclass
class ServerConfig:
    """RTSP server configuration."""
    host = ""  # Bind to all interfaces
    port = 8554  # Non-privileged RTSP port (554 requires root)


@dataclass
class AppConfig:
    """Main application configuration."""
    camera = None
    server = None
    
    def __post_init__(self):
        """Initialize sub-configs if not provided."""
        if self.camera is None:
            self.camera = CameraConfig()
        if self.server is None:
            self.server = ServerConfig()