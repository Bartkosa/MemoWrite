"""Spaced repetition algorithm implementation (SM-2 based)."""
from datetime import date, timedelta
from typing import Dict, Optional
from config import SR_INITIAL_EASE, SR_MIN_EASE, SR_EASY_BONUS


class SpacedRepetition:
    """Implements SM-2 spaced repetition algorithm."""
    
    def __init__(self):
        """Initialize with default parameters."""
        self.initial_ease = SR_INITIAL_EASE
        self.min_ease = SR_MIN_EASE
        self.easy_bonus = SR_EASY_BONUS
    
    def calculate_next_review(self, current_ease: float, current_interval: int,
                             current_repetitions: int, quality: float) -> Dict:
        """Calculate next review parameters based on performance.
        
        Args:
            current_ease: Current ease factor
            current_interval: Current interval in days
            current_repetitions: Number of successful repetitions
            quality: Performance quality (0-5 scale, mapped from score 0-100)
                     - 5: Perfect (90-100)
                     - 4: Good (80-89)
                     - 3: Pass (70-79)
                     - 2: Fail (60-69)
                     - 1: Poor (50-59)
                     - 0: Very Poor (0-49)
        
        Returns:
            Dictionary with updated ease_factor, interval, repetitions, next_review_date
        """
        # Map score to quality (0-5 scale for SM-2)
        if quality >= 90:
            quality_rating = 5
        elif quality >= 80:
            quality_rating = 4
        elif quality >= 70:
            quality_rating = 3
        elif quality >= 60:
            quality_rating = 2
        elif quality >= 50:
            quality_rating = 1
        else:
            quality_rating = 0
        
        # SM-2 algorithm
        if quality_rating >= 3:  # Pass or better
            if current_repetitions == 0:
                new_interval = 1
            elif current_repetitions == 1:
                new_interval = 6
            else:
                new_interval = int(current_interval * current_ease)
            
            new_repetitions = current_repetitions + 1
            
            # Update ease factor
            new_ease = current_ease + (0.1 - (5 - quality_rating) * (0.08 + (5 - quality_rating) * 0.02))
            new_ease = max(self.min_ease, new_ease)
            
            # Easy bonus
            if quality_rating == 5:
                new_ease += self.easy_bonus - 1.0
            
        else:  # Failed - reset
            new_repetitions = 0
            new_interval = 1
            new_ease = max(self.min_ease, current_ease - 0.2)
        
        # Calculate next review date
        next_review_date = date.today() + timedelta(days=new_interval)
        
        return {
            "ease_factor": round(new_ease, 2),
            "interval": new_interval,
            "repetitions": new_repetitions,
            "next_review_date": next_review_date
        }
    
    def get_priority_score(self, next_review_date: date, ease_factor: float,
                          repetitions: int) -> float:
        """Calculate priority score for question selection.
        
        Lower scores = higher priority (should be reviewed first).
        """
        days_overdue = (date.today() - next_review_date).days
        
        # Higher priority for:
        # - Overdue questions
        # - Lower ease factor (harder questions)
        # - Fewer repetitions (newer questions)
        
        priority = days_overdue * 10  # Overdue penalty
        priority += (3.0 - ease_factor) * 5  # Difficulty bonus
        priority -= repetitions * 0.5  # Newness bonus
        
        return priority

