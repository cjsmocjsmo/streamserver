"""Video recording and buffer management."""

import cv2
import logging
import os
import time
from collections import deque
from datetime import datetime

import numpy as np

from config import VideoConfig
from database import EventDatabase


class CircularVideoBuffer:
    """Circular buffer for storing video frames."""
    
    def __init__(self, config):
        """Initialize circular buffer with configuration.
        
        Args:
            config: Video configuration
        """
        self.config = config
        self.max_frames = int(config.pre_buffer_duration * config.fps)
        self.buffer = deque(maxlen=self.max_frames)
        self.fps = config.fps
        
        logging.info(f"✅ Circular buffer initialized ({self.max_frames} frames, {config.pre_buffer_duration}s)")
        
    def add_frame(self, frame):
        """Add a frame to the circular buffer.
        
        Args:
            frame: Video frame to add
        """
        if frame is not None:
            timestamp = time.time()
            self.buffer.append((frame.copy(), timestamp))
        
    def get_prebuffer_frames(self):
        """Get all frames currently in the buffer.
        
        Returns:
            List of (frame, timestamp) tuples
        """
        return list(self.buffer)
        
    def clear(self):
        """Clear the buffer."""
        self.buffer.clear()
        
    def is_full(self):
        """Check if buffer is at capacity.
        
        Returns:
            bool: True if buffer is full
        """
        return len(self.buffer) == self.max_frames


class VideoRecorder:
    """Manages video recording with motion detection integration."""
    
    def __init__(self, config, database):
        """Initialize video recorder.
        
        Args:
            config: Video configuration
            database: Database instance for event logging
        """
        self.config = config
        self.output_dir = config.output_dir
        self.fps = config.fps
        self.post_motion_duration = config.post_motion_duration
        self.fourcc_str = config.fourcc
        
        # Recording state
        self.is_recording = False
        self.current_writer = None
        self.current_filename = None
        self.recording_start_time = None
        self.post_motion_frames = 0
        
        # Database integration
        self.database = database
        
        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
        
        logging.info(f"✅ Video recorder initialized (FPS: {self.fps}, dir: {self.output_dir})")
        
    def start_recording(self, prebuffer_frames, frame_size):
        """Start recording with prebuffer frames.
        
        Args:
            prebuffer_frames: List of (frame, timestamp) tuples from buffer
            frame_size: (width, height) of video frames
            
        Returns:
            bool: True if recording started successfully
        """
        if self.is_recording:
            logging.warning("⚠️ Recording already in progress")
            return False
            
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.current_filename = os.path.join(self.output_dir, f"motion_{timestamp}.mp4")
            
            # Initialize video writer
            fourcc = cv2.VideoWriter_fourcc(*self.fourcc_str)
            self.current_writer = cv2.VideoWriter(
                self.current_filename, fourcc, self.fps, frame_size
            )
            
            if not self.current_writer.isOpened():
                logging.error(f"❌ Failed to open video writer for {self.current_filename}")
                return False
                
            # Write prebuffer frames first
            for frame, _ in prebuffer_frames:
                if frame is not None:
                    self.current_writer.write(frame)
                    
            self.is_recording = True
            self.recording_start_time = time.time()
            self.post_motion_frames = 0
            
            logging.info(f"🔴 Started recording: {os.path.basename(self.current_filename)}")
            return True
            
        except Exception as e:
            logging.error(f"❌ Failed to start recording: {e}")
            self._cleanup_recording()
            return False
        
    def add_frame(self, frame):
        """Add a frame to the current recording.
        
        Args:
            frame: Video frame to add
            
        Returns:
            bool: True if frame was added successfully
        """
        if not self.is_recording or self.current_writer is None:
            return False
            
        try:
            if frame is not None:
                self.current_writer.write(frame)
                self.post_motion_frames += 1
            
            # Check if we should stop recording
            max_post_frames = int(self.post_motion_duration * self.fps)
            if self.post_motion_frames >= max_post_frames:
                self.stop_recording()
                return False
                
            return True
            
        except Exception as e:
            logging.error(f"❌ Error adding frame to recording: {e}")
            return False
            
    def stop_recording(self):
        """Stop the current recording.
        
        Returns:
            bool: True if recording was stopped successfully
        """
        if not self.is_recording:
            return False
            
        try:
            duration = time.time() - self.recording_start_time if self.recording_start_time else 0
            
            # Clean up video writer
            self._cleanup_recording()
            
            # Add event to database
            if self.current_filename and os.path.exists(self.current_filename):
                self.database.add_event(self.current_filename)
            
            logging.info(f"⏹️ Stopped recording: {os.path.basename(self.current_filename or 'unknown')} "
                        f"(Duration: {duration:.1f}s)")
            
            # Reset state
            self.is_recording = False
            self.current_filename = None
            self.recording_start_time = None
            self.post_motion_frames = 0
            
            return True
            
        except Exception as e:
            logging.error(f"❌ Error stopping recording: {e}")
            return False
            
    def _cleanup_recording(self):
        """Clean up video writer resources."""
        if self.current_writer:
            try:
                self.current_writer.release()
            except Exception as e:
                logging.error(f"❌ Error releasing video writer: {e}")
            finally:
                self.current_writer = None
                
    def force_stop(self):
        """Force stop recording (for emergency cleanup)."""
        if self.is_recording:
            logging.warning("⚠️ Force stopping recording")
            self._cleanup_recording()
            self.is_recording = False
            self.current_filename = None
            self.recording_start_time = None
            self.post_motion_frames = 0