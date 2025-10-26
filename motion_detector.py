"""Motion detection using OpenCV."""

import cv2
import logging
import numpy as np
import time

from config import MotionConfig


class MotionDetector:
    """Handles motion detection using background subtraction."""
    
    def __init__(self, config):
        """Initialize motion detector with configuration.
        
        Args:
            config: Motion detection configuration
        """
        self.config = config
        self.threshold = config.threshold
        self.min_area = config.min_area
        self.learning_rate = config.learning_rate
        
        # Initialize background subtractor
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            detectShadows=True
        )
        
        self.last_motion_time = 0
        self.motion_detected = False
        
        logging.info(f"✅ Motion detector initialized (threshold: {self.threshold}, min_area: {self.min_area})")
        
    def detect_motion(self, frame):
        """Detect motion in the given frame.
        
        Args:
            frame: Input frame as numpy array
            
        Returns:
            tuple: (bool, list) - Motion detected flag and list of bounding boxes
        """
        if frame is None:
            return False, []
            
        try:
            # Apply background subtraction with learning rate
            fg_mask = self.bg_subtractor.apply(frame, learningRate=self.learning_rate)
            
            # Remove noise and fill holes
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
            
            # Find contours
            contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Check if any contour is large enough to be considered motion
            motion_detected = False
            motion_boxes = []
            
            for contour in contours:
                if cv2.contourArea(contour) > self.min_area:
                    motion_detected = True
                    # Get bounding box for this motion area
                    x, y, w, h = cv2.boundingRect(contour)
                    motion_boxes.append((x, y, w, h))
                    
            if motion_detected:
                self.last_motion_time = time.time()
                
            self.motion_detected = motion_detected
            return motion_detected, motion_boxes
            
        except Exception as e:
            logging.error(f"❌ Motion detection error: {e}")
            return False, []
            
    def is_motion_recent(self, timeout=2.0):
        """Check if motion was detected recently.
        
        Args:
            timeout: How many seconds to consider motion "recent"
            
        Returns:
            bool: True if motion was detected within timeout seconds
        """
        return (time.time() - self.last_motion_time) < timeout
        
    def reset(self):
        """Reset the motion detector state."""
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(detectShadows=True)
        self.last_motion_time = 0
        self.motion_detected = False
        logging.info("🔄 Motion detector reset")