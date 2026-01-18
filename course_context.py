"""Course PDF context extraction for providing domain knowledge to the grader."""
import pdfplumber
import os
from typing import List, Dict


class CourseContext:
    """Extracts and manages course content from AI_Notes.pdf."""
    
    def __init__(self, course_pdf_path: str = "AI_Notes.pdf"):
        """Initialize with course PDF path."""
        self.course_pdf_path = course_pdf_path
        self._content_cache = None
    
    def extract_course_content(self) -> str:
        """Extract all text content from the course PDF."""
        if self._content_cache:
            return self._content_cache
        
        if not os.path.exists(self.course_pdf_path):
            return ""
        
        text = ""
        try:
            with pdfplumber.open(self.course_pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            print(f"Warning: Could not extract course content: {str(e)}")
            return ""
        
        self._content_cache = text
        return text
    
    def get_relevant_sections(self, question_text: str, max_chunks: int = 3) -> str:
        """Get relevant sections from course content based on question.
        
        This is a simple implementation. For better results, you could use
        embeddings and semantic search.
        """
        course_content = self.extract_course_content()
        
        if not course_content:
            return ""
        
        # Simple keyword-based relevance
        question_lower = question_text.lower()
        lines = course_content.split('\n')
        
        relevant_sections = []
        current_section = []
        in_relevant_section = False
        
        # Keywords from question
        keywords = set(word.lower() for word in question_text.split() if len(word) > 3)
        
        for i, line in enumerate(lines):
            line_lower = line.lower()
            
            # Check if line contains relevant keywords
            line_keywords = set(word.lower() for word in line.split() if len(word) > 3)
            relevance_score = len(keywords & line_keywords)
            
            if relevance_score > 0 or any(keyword in line_lower for keyword in keywords):
                in_relevant_section = True
                current_section.append(line)
            elif in_relevant_section:
                # End of relevant section
                if current_section:
                    relevant_sections.append('\n'.join(current_section))
                    current_section = []
                in_relevant_section = False
                if len(relevant_sections) >= max_chunks:
                    break
            elif current_section and len(current_section) > 10:
                # Too long without relevance, reset
                current_section = []
        
        if current_section and len(relevant_sections) < max_chunks:
            relevant_sections.append('\n'.join(current_section))
        
        # Return top relevant sections
        result = '\n\n---\n\n'.join(relevant_sections[:max_chunks])
        
        # If no specific sections found, return a summary of course content
        if not result:
            # Return first 2000 characters as general context
            result = course_content[:2000]
        
        return result
    
    def get_course_summary(self, max_length: int = 3000) -> str:
        """Get a summary of the course content."""
        content = self.extract_course_content()
        if len(content) > max_length:
            return content[:max_length] + "..."
        return content

