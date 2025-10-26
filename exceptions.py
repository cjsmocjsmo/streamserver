"""Exception classes for the stream server."""


class StreamServerError(Exception):
    """Base exception for stream server errors."""
    pass


class CameraError(StreamServerError):
    """Exception raised for camera-related errors."""
    pass