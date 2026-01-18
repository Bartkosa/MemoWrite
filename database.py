"""Database operations for MemoWrite."""
import sqlite3
import os
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple
from config import DATABASE_PATH


class Database:
    """Manages SQLite database operations."""
    
    def __init__(self):
        """Initialize database connection and create tables if they don't exist."""
        self.db_path = DATABASE_PATH
        self._create_tables()
    
    def _get_connection(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _create_tables(self):
        """Create all necessary database tables."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                name TEXT,
                picture_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Check if questions table exists and has user_id column
        cursor.execute("PRAGMA table_info(questions)")
        questions_columns = [col[1] for col in cursor.fetchall()]
        table_exists = len(questions_columns) > 0
        
        if table_exists and 'user_id' not in questions_columns:
            # Table exists but no user_id - add it (migration)
            try:
                cursor.execute("ALTER TABLE questions ADD COLUMN user_id TEXT")
                # Migrate existing data - set a default user_id for existing questions
                # This is a one-time migration, existing data will be assigned to a system user
                cursor.execute("UPDATE questions SET user_id = 'system' WHERE user_id IS NULL")
            except sqlite3.OperationalError:
                pass
        
        # Questions table - now with user_id
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                question_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                question_text TEXT NOT NULL,
                reference_answer TEXT NOT NULL,
                source_pdf TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # Check if user_answers table exists and has user_id column
        cursor.execute("PRAGMA table_info(user_answers)")
        user_answers_columns = [col[1] for col in cursor.fetchall()]
        table_exists_answers = len(user_answers_columns) > 0
        
        if table_exists_answers and 'user_id' not in user_answers_columns:
            # Table exists but no user_id - add it (migration)
            try:
                cursor.execute("ALTER TABLE user_answers ADD COLUMN user_id TEXT")
                # Migrate: get user_id from associated question
                cursor.execute("""
                    UPDATE user_answers 
                    SET user_id = (SELECT user_id FROM questions WHERE questions.question_id = user_answers.question_id)
                    WHERE user_id IS NULL
                """)
            except sqlite3.OperationalError:
                pass
        
        # User answers table - add user_id for additional safety
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_answers (
                answer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER NOT NULL,
                user_id TEXT NOT NULL,
                user_answer TEXT NOT NULL,
                score REAL,
                feedback TEXT,
                missing_concepts TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (question_id) REFERENCES questions(question_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # Spaced repetition table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS spaced_repetition (
                sr_id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER NOT NULL UNIQUE,
                ease_factor REAL DEFAULT 2.5,
                interval INTEGER DEFAULT 1,
                repetitions INTEGER DEFAULT 0,
                next_review_date DATE,
                last_review_date DATE,
                FOREIGN KEY (question_id) REFERENCES questions(question_id)
            )
        """)
        
        # User progress table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_progress (
                progress_id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER NOT NULL,
                mastery_level REAL DEFAULT 0.0,
                total_attempts INTEGER DEFAULT 0,
                correct_attempts INTEGER DEFAULT 0,
                last_reviewed TIMESTAMP,
                FOREIGN KEY (question_id) REFERENCES questions(question_id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    # User operations
    def get_or_create_user(self, user_id: str, email: str, name: str = None, picture_url: str = None) -> str:
        """Get existing user or create new user. Returns user_id."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Try to get existing user
        cursor.execute("SELECT user_id FROM users WHERE user_id = ? OR email = ?", (user_id, email))
        existing = cursor.fetchone()
        
        if existing:
            # Update user info if provided
            if name or picture_url:
                cursor.execute("""
                    UPDATE users SET name = COALESCE(?, name), picture_url = COALESCE(?, picture_url)
                    WHERE user_id = ?
                """, (name, picture_url, existing[0]))
            conn.commit()
            conn.close()
            return existing[0]
        else:
            # Create new user
            cursor.execute("""
                INSERT INTO users (user_id, email, name, picture_url)
                VALUES (?, ?, ?, ?)
            """, (user_id, email, name, picture_url))
            conn.commit()
            conn.close()
            return user_id
    
    # Questions CRUD operations
    def add_question(self, user_id: str, question_text: str, reference_answer: str, source_pdf: str = None) -> int:
        """Add a new question to the database for a specific user."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO questions (user_id, question_text, reference_answer, source_pdf)
            VALUES (?, ?, ?, ?)
        """, (user_id, question_text, reference_answer, source_pdf))
        question_id = cursor.lastrowid
        conn.commit()
        
        # Initialize spaced repetition entry
        cursor.execute("""
            INSERT INTO spaced_repetition (question_id, next_review_date)
            VALUES (?, ?)
        """, (question_id, date.today()))
        
        # Initialize progress entry
        cursor.execute("""
            INSERT INTO user_progress (question_id)
            VALUES (?)
        """, (question_id,))
        
        conn.commit()
        conn.close()
        return question_id
    
    def get_question(self, user_id: str, question_id: int) -> Optional[Dict]:
        """Get a question by ID for a specific user."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM questions WHERE question_id = ? AND user_id = ?", (question_id, user_id))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def get_all_questions(self, user_id: str) -> List[Dict]:
        """Get all questions for a specific user."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM questions WHERE user_id = ? ORDER BY question_id", (user_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def get_questions_count(self, user_id: str) -> int:
        """Get total number of questions for a specific user."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM questions WHERE user_id = ?", (user_id,))
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def delete_all_questions(self, user_id: str):
        """Delete all questions and related data for a specific user."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get question IDs for this user
        cursor.execute("SELECT question_id FROM questions WHERE user_id = ?", (user_id,))
        question_ids = [row[0] for row in cursor.fetchall()]
        
        if question_ids:
            placeholders = ','.join('?' * len(question_ids))
            # Delete in order to respect foreign key constraints
            cursor.execute(f"DELETE FROM user_answers WHERE question_id IN ({placeholders})", question_ids)
            cursor.execute(f"DELETE FROM spaced_repetition WHERE question_id IN ({placeholders})", question_ids)
            cursor.execute(f"DELETE FROM user_progress WHERE question_id IN ({placeholders})", question_ids)
            cursor.execute("DELETE FROM questions WHERE user_id = ?", (user_id,))
        
        conn.commit()
        conn.close()
    
    def update_question(self, user_id: str, question_id: int, question_text: str, reference_answer: str) -> bool:
        """Update a question's text and answer for a specific user."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE questions
                SET question_text = ?, reference_answer = ?
                WHERE question_id = ? AND user_id = ?
            """, (question_text, reference_answer, question_id, user_id))
            conn.commit()
            conn.close()
            return cursor.rowcount > 0
        except Exception as e:
            conn.close()
            raise Exception(f"Error updating question: {str(e)}")
    
    def delete_question(self, user_id: str, question_id: int) -> bool:
        """Delete a specific question and all related data for a specific user."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # First verify the question belongs to the user
            cursor.execute("SELECT question_id FROM questions WHERE question_id = ? AND user_id = ?", (question_id, user_id))
            if not cursor.fetchone():
                conn.close()
                return False
            
            # Delete in order to respect foreign key constraints
            cursor.execute("DELETE FROM user_answers WHERE question_id = ?", (question_id,))
            cursor.execute("DELETE FROM spaced_repetition WHERE question_id = ?", (question_id,))
            cursor.execute("DELETE FROM user_progress WHERE question_id = ?", (question_id,))
            cursor.execute("DELETE FROM questions WHERE question_id = ? AND user_id = ?", (question_id, user_id))
            deleted = cursor.rowcount > 0
            conn.commit()
            conn.close()
            return deleted
        except Exception as e:
            conn.close()
            raise Exception(f"Error deleting question: {str(e)}")
    
    # User answers operations
    def add_user_answer(self, user_id: str, question_id: int, user_answer: str, score: float, 
                       feedback: str, missing_concepts: str) -> int:
        """Add a user's answer with grading results."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_answers (user_id, question_id, user_answer, score, feedback, missing_concepts)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, question_id, user_answer, score, feedback, missing_concepts))
        answer_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return answer_id
    
    def get_user_answers(self, question_id: int) -> List[Dict]:
        """Get all user answers for a question."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM user_answers 
            WHERE question_id = ? 
            ORDER BY timestamp DESC
        """, (question_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    # Spaced repetition operations
    def get_spaced_repetition(self, question_id: int) -> Optional[Dict]:
        """Get spaced repetition data for a question."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM spaced_repetition WHERE question_id = ?
        """, (question_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def update_spaced_repetition(self, question_id: int, ease_factor: float, 
                                 interval: int, repetitions: int, 
                                 next_review_date: date, last_review_date: date = None):
        """Update spaced repetition data for a question."""
        conn = self._get_connection()
        cursor = conn.cursor()
        if last_review_date is None:
            last_review_date = date.today()
        cursor.execute("""
            UPDATE spaced_repetition
            SET ease_factor = ?, interval = ?, repetitions = ?, 
                next_review_date = ?, last_review_date = ?
            WHERE question_id = ?
        """, (ease_factor, interval, repetitions, next_review_date, last_review_date, question_id))
        conn.commit()
        conn.close()
    
    def get_questions_due_for_review(self, user_id: str) -> List[Dict]:
        """Get all questions that are due for review for a specific user."""
        conn = self._get_connection()
        cursor = conn.cursor()
        today = date.today()
        cursor.execute("""
            SELECT q.*, sr.*
            FROM questions q
            JOIN spaced_repetition sr ON q.question_id = sr.question_id
            WHERE q.user_id = ? AND sr.next_review_date <= ?
            ORDER BY sr.next_review_date ASC, sr.ease_factor ASC
        """, (user_id, today))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def get_next_question_for_review(self, user_id: str) -> Optional[Dict]:
        """Get the next question that should be reviewed for a specific user."""
        due_questions = self.get_questions_due_for_review(user_id)
        if due_questions:
            return due_questions[0]
        
        # If no questions are due, get the one with the earliest next_review_date for this user
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT q.*, sr.*
            FROM questions q
            JOIN spaced_repetition sr ON q.question_id = sr.question_id
            WHERE q.user_id = ?
            ORDER BY sr.next_review_date ASC
            LIMIT 1
        """, (user_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    # Progress operations
    def update_progress(self, question_id: int, score: float):
        """Update user progress for a question."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get current progress
        cursor.execute("""
            SELECT * FROM user_progress WHERE question_id = ?
        """, (question_id,))
        row = cursor.fetchone()
        
        if row:
            current = dict(row)
            total_attempts = current['total_attempts'] + 1
            correct_attempts = current['correct_attempts']
            if score >= 70:  # Consider 70% as passing
                correct_attempts += 1
            
            mastery_level = (correct_attempts / total_attempts) * 100 if total_attempts > 0 else 0
            
            cursor.execute("""
                UPDATE user_progress
                SET mastery_level = ?, total_attempts = ?, correct_attempts = ?,
                    last_reviewed = CURRENT_TIMESTAMP
                WHERE question_id = ?
            """, (mastery_level, total_attempts, correct_attempts, question_id))
        else:
            # Create new progress entry
            mastery_level = 100.0 if score >= 70 else 0.0
            cursor.execute("""
                INSERT INTO user_progress (question_id, mastery_level, total_attempts, correct_attempts, last_reviewed)
                VALUES (?, ?, 1, ?, CURRENT_TIMESTAMP)
            """, (question_id, mastery_level, 1 if score >= 70 else 0))
        
        conn.commit()
        conn.close()
    
    def get_progress_stats(self, user_id: str) -> Dict:
        """Get overall progress statistics for a specific user."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total_questions,
                AVG(p.mastery_level) as avg_mastery,
                SUM(p.total_attempts) as total_attempts,
                SUM(p.correct_attempts) as total_correct
            FROM user_progress p
            JOIN questions q ON p.question_id = q.question_id
            WHERE q.user_id = ?
        """, (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        stats = dict(row) if row else {}
        total_attempts = stats.get('total_attempts', 0) or 0
        if total_attempts > 0:
            stats['success_rate'] = (stats.get('total_correct', 0) / total_attempts) * 100
        else:
            stats['success_rate'] = 0
        
        return stats
    
    def get_all_progress(self, user_id: str) -> List[Dict]:
        """Get progress for all questions for a specific user."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.*, q.question_text
            FROM user_progress p
            JOIN questions q ON p.question_id = q.question_id
            WHERE q.user_id = ?
            ORDER BY p.mastery_level ASC, p.last_reviewed DESC
        """, (user_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

