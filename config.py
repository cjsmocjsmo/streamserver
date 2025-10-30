"""Configuration management for the simple stream server."""

from dataclasses import dataclass


@dataclass
class CameraConfig:
    """Camera configuration."""
    resolution = (640, 480)
    format = "RGB888"


@dataclass
class ServerConfig:
    """HTTP server configuration."""
    host = ""
    port = 8000


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