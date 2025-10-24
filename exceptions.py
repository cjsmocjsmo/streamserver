"""Exception classes for the stream server."""


class StreamServerError(Exception):
    """Base exception for stream server errors."""
    pass


class CameraError(StreamServerError):
    """Exception raised for camera-related errors."""
    pass


class RecordingError(StreamServerError):
    """Exception raised for video recording errors."""
    pass


class MotionDetectionError(StreamServerError):
    """Exception raised for motion detection errors."""
    pass


class DatabaseError(StreamServerError):
    """Exception raised for database-related errors."""
    pass


class ConfigurationError(StreamServerError):
    """Exception raised for configuration errors."""
    pass