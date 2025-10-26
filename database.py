"""Database management for motion detection events."""

import logging
import os
import sqlite3
from datetime import datetime

from config import DatabaseConfig


class EventDatabase:
    """Manages SQLite database for motion detection events."""
    
    def __init__(self, config):
        """Initialize database with configuration."""
        self.config = config
        self.db_path = config.db_path
        self._init_database()
        
    def _init_database(self):
        """Initialize the database and create Events table if it doesn't exist."""
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS Events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        Epoch INTEGER NOT NULL,
                        Month INTEGER NOT NULL,
                        Day INTEGER NOT NULL,
                        Year INTEGER NOT NULL,
                        Size INTEGER NOT NULL,
                        Path TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                conn.commit()
                logging.info(f"✅ Database initialized: {self.db_path}")
        except sqlite3.Error as e:
            logging.error(f"❌ Database initialization failed: {e}")
            raise
            
    def add_event(self, file_path):
        """Add a new video event to the database.
        
        Args:
            file_path: Path to the recorded video file
            
        Returns:
            bool: True if event was added successfully, False otherwise
        """
        try:
            # Get file information
            if not os.path.exists(file_path):
                logging.error(f"❌ File not found for database entry: {file_path}")
                return False
                
            file_size = os.path.getsize(file_path)
            now = datetime.now()
            epoch_time = int(now.timestamp())
            
            # Insert into database
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO Events (Epoch, Month, Day, Year, Size, Path)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (epoch_time, now.month, now.day, now.year, file_size, file_path))
                conn.commit()
                
                logging.info(f"📊 Event recorded in database: {os.path.basename(file_path)} ({file_size} bytes)")
                return True
                
        except sqlite3.Error as e:
            logging.error(f"❌ Failed to add event to database: {e}")
            return False
            
    def get_recent_events(self, limit=10):
        """Get recent events from the database.
        
        Args:
            limit: Maximum number of events to return
            
        Returns:
            List of tuples containing event data
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT Epoch, Month, Day, Year, Size, Path 
                    FROM Events 
                    ORDER BY Epoch DESC 
                    LIMIT ?
                ''', (limit,))
                return cursor.fetchall()
        except sqlite3.Error as e:
            logging.error(f"❌ Failed to retrieve events: {e}")
            return []
            
    def get_event_count(self):
        """Get total number of events in database.
        
        Returns:
            int: Total number of events
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM Events')
                return cursor.fetchone()[0]
        except sqlite3.Error as e:
            logging.error(f"❌ Failed to get event count: {e}")
            return 0

    def get_event_count_24h(self):
        """Get number of events from the last 24 hours starting at midnight.
        
        Returns:
            int: Number of events from last 24 hours
        """
        try:
            from datetime import datetime, timedelta
            
            # Get current time and calculate midnight 24 hours ago
            now = datetime.now()
            midnight_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
            midnight_24h_ago = midnight_today - timedelta(days=1)
            
            # Convert to Unix timestamp
            start_epoch = int(midnight_24h_ago.timestamp())
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM Events WHERE Epoch >= ?', (start_epoch,))
                return cursor.fetchone()[0]
        except sqlite3.Error as e:
            logging.error(f"❌ Failed to get 24h event count: {e}")
            return 0
        except Exception as e:
            logging.error(f"❌ Error calculating 24h event count: {e}")
            return 0
            
    def get_events_by_date(self, year, month, day=None):
        """Get events for a specific date.
        
        Args:
            year: Year to filter by
            month: Month to filter by  
            day: Optional day to filter by
            
        Returns:
            List of tuples containing event data
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                if day is not None:
                    cursor.execute('''
                        SELECT Epoch, Month, Day, Year, Size, Path 
                        FROM Events 
                        WHERE Year = ? AND Month = ? AND Day = ?
                        ORDER BY Epoch DESC
                    ''', (year, month, day))
                else:
                    cursor.execute('''
                        SELECT Epoch, Month, Day, Year, Size, Path 
                        FROM Events 
                        WHERE Year = ? AND Month = ?
                        ORDER BY Epoch DESC
                    ''', (year, month))
                return cursor.fetchall()
        except sqlite3.Error as e:
            logging.error(f"❌ Failed to retrieve events by date: {e}")
            return []