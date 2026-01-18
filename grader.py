"""LLM-based grading module for evaluating user answers."""
import json
import google.generativeai as genai
from typing import Dict, Tuple, List
from config import GEMINI_API_KEY, GEMINI_MODEL, GRADING_STRICTNESS
from course_context import CourseContext


class Grader:
    """Grades user answers using Gemini API with semantic evaluation."""
    
    def __init__(self):
        """Initialize the grader with Gemini API."""
        if not GEMINI_API_KEY:
            raise Exception("GEMINI_API_KEY not set in environment variables")
        
        genai.configure(api_key=GEMINI_API_KEY)
        self.model = genai.GenerativeModel(GEMINI_MODEL)
        self.course_context = CourseContext()
    
    def grade_answer(self, question: str, reference_answer: str, 
                    user_answer: str) -> Dict[str, any]:
        """Grade a user's answer against the reference answer.
        
        Args:
            question: The question text
            reference_answer: The reference/correct answer
            user_answer: The user's answer to grade
        
        Returns:
            Dictionary with:
            - score: float (0-100)
            - feedback: str (detailed feedback)
            - missing_concepts: str (list of missing concepts)
        """
        # Get relevant course context
        relevant_context = self.course_context.get_relevant_sections(question)
        
        # Prepare grading prompt
        prompt = f"""You are an expert AI course instructor grading an exam answer.

COURSE CONTEXT (for reference):
{relevant_context[:2000]}

QUESTION:
{question}

REFERENCE ANSWER (what a complete answer should include):
{reference_answer}

STUDENT'S ANSWER:
{user_answer}

TASK:
Evaluate the student's answer and provide:
1. A numerical score from 0-100 based on:
   - Accuracy and correctness of concepts
   - Completeness compared to reference answer
   - Understanding demonstrated
   - Use grading strictness level: {GRADING_STRICTNESS} (0.0 = lenient, 1.0 = strict)

2. Detailed feedback explaining:
   - What the student got right
   - What is missing or incorrect
   - Suggestions for improvement

3. A list of missing concepts that should have been mentioned

Format your response as JSON:
{{
    "score": <number 0-100>,
    "feedback": "<detailed feedback text>",
    "missing_concepts": "<comma-separated list of missing concepts>"
}}

Return ONLY valid JSON, no other text."""

        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Clean response - remove markdown code blocks if present
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()
            
            # Parse JSON response
            result = json.loads(response_text)
            
            # Validate and ensure score is in range
            score = float(result.get("score", 0))
            score = max(0, min(100, score))  # Clamp to 0-100
            
            return {
                "score": score,
                "feedback": result.get("feedback", "No feedback provided."),
                "missing_concepts": result.get("missing_concepts", "None identified.")
            }
            
        except json.JSONDecodeError as e:
            # Fallback if JSON parsing fails
            return {
                "score": 50.0,
                "feedback": f"Error parsing grading response: {str(e)}. Please try again.",
                "missing_concepts": "Unable to identify missing concepts."
            }
        except Exception as e:
            raise Exception(f"Error grading answer: {str(e)}")
    
    def grade_batch(self, qa_pairs: List[Tuple[str, str, str]]) -> List[Dict]:
        """Grade multiple answers (for future batch processing).
        
        Args:
            qa_pairs: List of tuples (question, reference_answer, user_answer)
        
        Returns:
            List of grading results
        """
        results = []
        for question, ref_answer, user_answer in qa_pairs:
            result = self.grade_answer(question, ref_answer, user_answer)
            results.append(result)
        return results

