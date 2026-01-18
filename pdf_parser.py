"""PDF parsing module for extracting questions and answers from exam PDFs."""
import pdfplumber
import os
import json
import re
import google.generativeai as genai
from typing import List, Dict, Tuple
from config import GEMINI_API_KEY, GEMINI_MODEL, UPLOADS_DIR


class PDFParser:
    """Parses PDF files to extract questions and answers."""
    
    def __init__(self):
        """Initialize the PDF parser with Gemini API."""
        if GEMINI_API_KEY:
            genai.configure(api_key=GEMINI_API_KEY)
            self.model = genai.GenerativeModel(GEMINI_MODEL)
        else:
            self.model = None
    
    def save_uploaded_pdf(self, uploaded_file) -> str:
        """Save uploaded PDF file to uploads directory."""
        file_path = os.path.join(UPLOADS_DIR, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return file_path
    
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract all text from a PDF file."""
        text = ""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            raise Exception(f"Error extracting text from PDF: {str(e)}")
        return text
    
    def _fix_text_spacing(self, text: str) -> str:
        """Fix spacing issues in extracted text."""
        if not text:
            return text
        
        # Fix: add space between lowercase and uppercase (e.g., "HelloWorld" -> "Hello World")
        text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
        
        # Fix: add space after punctuation if missing (but not for decimals)
        text = re.sub(r'([.!?])([A-Za-z])', r'\1 \2', text)
        text = re.sub(r'([,;:])([A-Za-z])', r'\1 \2', text)
        
        # Fix: add space before opening parentheses/brackets if missing
        text = re.sub(r'([A-Za-z0-9])(\()', r'\1 \2', text)
        
        # Normalize whitespace
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        # Clean up each line
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)
        
        # Remove double spaces
        while '  ' in text:
            text = text.replace('  ', ' ')
        
        return text.strip()
    
    def parse_with_gemini(self, pdf_path: str) -> List[Dict[str, str]]:
        """Use Gemini API to parse PDF and extract Q&A pairs."""
        if not self.model:
            raise Exception("Gemini API key not configured. Please set GEMINI_API_KEY in .env file.")
        
        # Process page by page for better reliability
        return self._parse_pdf_page_by_page(pdf_path)
    
    def _parse_pdf_page_by_page(self, pdf_path: str) -> List[Dict[str, str]]:
        """Process PDF page by page to ensure all content is covered."""
        all_qa_pairs = []
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
                print(f"Processing PDF with {total_pages} pages...")
                
                # Process pages in batches to avoid token limits
                # Group pages together (e.g., 3-5 pages per batch)
                pages_per_batch = 3
                
                for batch_start in range(0, total_pages, pages_per_batch):
                    batch_end = min(batch_start + pages_per_batch, total_pages)
                    batch_pages = range(batch_start, batch_end)
                    
                    # Extract text from this batch of pages
                    batch_text = ""
                    for page_num in batch_pages:
                        page = pdf.pages[page_num]
                        page_text = page.extract_text()
                        if page_text:
                            batch_text += f"\n--- Page {page_num + 1} ---\n{page_text}\n"
                    
                    if not batch_text.strip():
                        continue
                    
                    print(f"Processing pages {batch_start + 1}-{batch_end} ({len(batch_text)} chars)...")
                    
                    # Try delimiter method first
                    batch_pairs = self._parse_with_delimiter_method(batch_text)
                    
                    # If that didn't work, try JSON method
                    if not batch_pairs:
                        batch_pairs = self._parse_with_json_method(batch_text)
                    
                    if batch_pairs:
                        print(f"  Found {len(batch_pairs)} Q&A pairs in pages {batch_start + 1}-{batch_end}")
                        all_qa_pairs.extend(batch_pairs)
                    else:
                        print(f"  No Q&A pairs found in pages {batch_start + 1}-{batch_end}")
                
        except Exception as e:
            print(f"Error processing PDF page by page: {str(e)}")
            # Fallback to full text extraction
            pdf_text = self.extract_text_from_pdf(pdf_path)
            return self._parse_with_delimiter_method(pdf_text) or self._parse_with_json_method(pdf_text)
        
        # Remove duplicates
        seen = set()
        unique_pairs = []
        for pair in all_qa_pairs:
            question_key = pair['question'].strip()[:150].lower()
            if question_key not in seen:
                seen.add(question_key)
                unique_pairs.append(pair)
        
        print(f"Total unique Q&A pairs: {len(unique_pairs)}")
        return unique_pairs
    
    def _parse_large_pdf_in_chunks(self, pdf_text: str, chunk_size: int) -> List[Dict[str, str]]:
        """Process large PDFs in chunks to avoid token limits."""
        all_qa_pairs = []
        
        # Split text into chunks with overlap to avoid cutting questions/answers in half
        overlap_size = 10000  # Increased overlap to ensure we don't split Q&A pairs
        chunks = []
        
        start = 0
        while start < len(pdf_text):
            end = start + chunk_size
            chunk = pdf_text[start:end]
            
            # Try to break at a good point to avoid cutting questions/answers
            if end < len(pdf_text):
                # Look for a good break point (paragraph break, question marker, etc.)
                # Try to find a question number or clear separator
                break_point = -1
                
                # Look for question markers near the end
                for marker in ['\n\nQuestion', '\n\nQ', '\n\n1.', '\n\n2.', '\n\n3.', '\n\n4.', '\n\n5.']:
                    pos = chunk.rfind(marker)
                    if pos > chunk_size * 0.7:  # If found in last 30%
                        break_point = pos
                        break
                
                # If no question marker, try paragraph break
                if break_point == -1:
                    break_point = chunk.rfind('\n\n')
                
                # If still nothing, try single newline
                if break_point == -1:
                    break_point = chunk.rfind('\n')
                
                # If still nothing, try sentence end
                if break_point == -1:
                    break_point = chunk.rfind('. ')
                
                if break_point > chunk_size * 0.7:  # Only use if it's in the last 30%
                    chunk = chunk[:break_point + 1]
                    end = start + break_point + 1
            
            chunks.append((start, end, chunk))
            start = end - overlap_size  # Overlap with next chunk
        
        print(f"Processing PDF in {len(chunks)} chunks...")
        
        # Process each chunk
        for i, (chunk_start, chunk_end, chunk_text) in enumerate(chunks):
            try:
                print(f"Processing chunk {i+1}/{len(chunks)} (chars {chunk_start}-{chunk_end})...")
                
                # Try delimiter method first
                chunk_pairs = self._parse_with_delimiter_method(chunk_text)
                
                # If that didn't work, try JSON method
                if not chunk_pairs:
                    chunk_pairs = self._parse_with_json_method(chunk_text)
                
                # Add chunk info for debugging
                if chunk_pairs:
                    print(f"  Found {len(chunk_pairs)} Q&A pairs in chunk {i+1}")
                    all_qa_pairs.extend(chunk_pairs)
                else:
                    print(f"  No Q&A pairs found in chunk {i+1}")
                    
            except Exception as e:
                # Continue with next chunk if one fails
                print(f"Warning: Error processing chunk {i+1}/{len(chunks)}: {str(e)}")
                continue
        
        print(f"Total Q&A pairs found: {len(all_qa_pairs)}")
        
        # Remove duplicates (might occur due to overlap)
        seen = set()
        unique_pairs = []
        for pair in all_qa_pairs:
            # Use question text as key for deduplication (first 150 chars)
            question_key = pair['question'].strip()[:150].lower()
            if question_key not in seen:
                seen.add(question_key)
                unique_pairs.append(pair)
        
        print(f"After deduplication: {len(unique_pairs)} unique Q&A pairs")
        
        return unique_pairs
    
    def _parse_with_delimiter_method(self, pdf_text: str) -> List[Dict[str, str]]:
        """Parse using delimiter-based format - more reliable than JSON."""
        # Don't truncate here - let the chunking handle large PDFs
        # But still limit for single requests
        max_text_length = 200000
        if len(pdf_text) > max_text_length:
            pdf_text = pdf_text[:max_text_length] + "\n[... text truncated ...]"
        
        prompt = f"""You are extracting question-answer pairs from an exam document.

CRITICAL: Extract EVERY question-answer pair you can find. Do not skip any.

For each question-answer pair, format it EXACTLY like this:

===QUESTION===
[the complete question text here]
===ANSWER===
[the complete answer/solution text here]
===

Repeat this format for EVERY question-answer pair in the document.

IMPORTANT RULES:
1. Extract ALL questions - do not skip any, even if they seem similar
2. Only include pairs where BOTH question AND answer exist
3. Preserve all text exactly as it appears, including formatting
4. Use the exact delimiters: ===QUESTION=== and ===ANSWER===
5. Separate each pair with ===
6. If a question spans multiple lines, include all lines
7. If an answer spans multiple paragraphs, include all paragraphs

Document content:
{pdf_text}

Now extract ALL question-answer pairs:"""

        try:
            response = self.model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.1,
                    "max_output_tokens": 32768,  # Maximum for Gemini 2.0 Flash
                }
            )
            response_text = response.text.strip()
            
            if not response_text:
                return []
            
            # Parse delimiter-based format using regex (more reliable)
            import re
            qa_pairs = []
            
            # Primary pattern: ===QUESTION=== ... ===ANSWER=== ... ===
            pattern = r'===QUESTION===\s*(.*?)\s*===ANSWER===\s*(.*?)\s*==='
            matches = re.finditer(pattern, response_text, re.DOTALL | re.IGNORECASE)
            
            for match in matches:
                question = match.group(1).strip()
                answer = match.group(2).strip()
                if question and answer:
                    # Fix spacing issues
                    question = self._fix_text_spacing(question)
                    answer = self._fix_text_spacing(answer)
                    qa_pairs.append({
                        "question": question,
                        "answer": answer
                    })
            
            # Alternative pattern if the first one doesn't match (variations)
            if not qa_pairs:
                # Try without the final === separator
                pattern2 = r'===QUESTION===\s*(.*?)\s*===ANSWER===\s*(.*?)(?=\s*===QUESTION===|\Z)'
                matches2 = re.finditer(pattern2, response_text, re.DOTALL | re.IGNORECASE)
                for match in matches2:
                    question = match.group(1).strip()
                    answer = match.group(2).strip()
                    if question and answer:
                        # Fix spacing issues
                        question = self._fix_text_spacing(question)
                        answer = self._fix_text_spacing(answer)
                        qa_pairs.append({
                            "question": question,
                            "answer": answer
                        })
            
            return qa_pairs if qa_pairs else []
            
        except Exception as e:
            return []  # Return empty, will try JSON method
    
    def _parse_with_json_method(self, pdf_text: str) -> List[Dict[str, str]]:
        """Fallback JSON parsing method."""
        # Don't truncate here - let the chunking handle large PDFs
        max_text_length = 200000
        if len(pdf_text) > max_text_length:
            pdf_text = pdf_text[:max_text_length] + "\n[... text truncated ...]"
        
        prompt = f"""Extract all question-answer pairs from this exam document.

Return a JSON array. Each object must have:
- "question": (string) the question text
- "answer": (string) the answer text

Only include pairs where both question AND answer exist.
Escape special characters properly in JSON (\\n for newlines, \\" for quotes).

Document:
{pdf_text}

Return JSON array:"""

        try:
            response = self.model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.1,
                    "max_output_tokens": 32768,  # Maximum for Gemini 2.0 Flash
                }
            )
            response_text = response.text.strip()
            
            if not response_text:
                return []
            
            # Extract JSON
            json_text = self._extract_json_from_response(response_text)
            
            # Try to parse
            try:
                qa_pairs = json.loads(json_text)
            except json.JSONDecodeError:
                qa_pairs = self._parse_json_manually(json_text)
                if not qa_pairs:
                    qa_pairs = self._parse_structured_text(response_text)
            
            # Validate
            if isinstance(qa_pairs, dict):
                qa_pairs = [qa_pairs]
            
            validated_pairs = []
            for pair in qa_pairs:
                if isinstance(pair, dict):
                    question = str(pair.get("question", "")).strip()
                    answer = str(pair.get("answer", "")).strip()
                    if question and answer:
                        # Fix spacing issues
                        question = self._fix_text_spacing(question)
                        answer = self._fix_text_spacing(answer)
                        validated_pairs.append({
                            "question": question,
                            "answer": answer
                        })
            
            return validated_pairs
            
        except Exception as e:
            raise Exception(f"Error parsing PDF: {str(e)}")
    
    def _extract_json_from_response(self, response_text: str) -> str:
        """Extract JSON from Gemini response, handling various formats."""
        import re
        
        # Remove markdown code blocks
        if "```" in response_text:
            # Extract content between code blocks
            matches = re.findall(r'```(?:json)?\s*(.*?)```', response_text, re.DOTALL)
            if matches:
                return matches[0].strip()
        
        # Try to find JSON array pattern - be more specific
        # Look for [ followed by content and ending with ]
        json_match = re.search(r'(\[[\s\S]*\])', response_text, re.DOTALL)
        if json_match:
            return json_match.group(1)
        
        # Try to find just the array content if brackets are missing
        # Look for patterns like {"question":..., "answer":...}
        obj_pattern = r'\{[^}]*"question"[^}]*"answer"[^}]*\}'
        if re.search(obj_pattern, response_text):
            # Wrap in array
            return '[' + response_text + ']'
        
        # If no clear JSON found, return the whole response
        return response_text.strip()
    
    def _fix_json_issues(self, json_text: str) -> str:
        """Try to fix common JSON formatting issues."""
        import re
        
        # Remove any leading/trailing whitespace
        json_text = json_text.strip()
        
        # Ensure it starts with [ and ends with ]
        if not json_text.startswith('['):
            # Try to find the start
            start_idx = json_text.find('[')
            if start_idx != -1:
                json_text = json_text[start_idx:]
        
        if not json_text.endswith(']'):
            # Try to find the end
            end_idx = json_text.rfind(']')
            if end_idx != -1:
                json_text = json_text[:end_idx + 1]
        
        # Try to fix unescaped newlines within string values
        # This is a simplified approach - find string values and escape newlines
        # Pattern: "..." where ... might contain unescaped newlines
        def escape_string_content(match):
            content = match.group(1)
            # Escape newlines, quotes, and backslashes
            content = content.replace('\\', '\\\\')  # Escape backslashes first
            content = content.replace('"', '\\"')   # Escape quotes
            content = content.replace('\n', '\\n')   # Escape newlines
            content = content.replace('\r', '\\r')   # Escape carriage returns
            content = content.replace('\t', '\\t')   # Escape tabs
            return f'"{content}"'
        
        # This is complex - instead, let's try a simpler approach
        # Use json.JSONDecoder with strict=False if available, or try manual repair
        
        return json_text
    
    def _parse_json_manually(self, json_text: str) -> List[Dict[str, str]]:
        """Manually parse JSON-like text when standard parsing fails."""
        import re
        
        qa_pairs = []
        
        # Try to find JSON objects with question and answer fields
        # Pattern: {"question": "...", "answer": "..."}
        pattern = r'\{\s*"question"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,\s*"answer"\s*:\s*"((?:[^"\\]|\\.)*)"\s*\}'
        matches = re.finditer(pattern, json_text, re.DOTALL)
        
        for match in matches:
            question = match.group(1)
            answer = match.group(2)
            # Unescape JSON escape sequences
            question = question.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
            answer = answer.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
            
            if question.strip():
                qa_pairs.append({
                    "question": question.strip(),
                    "answer": answer.strip()
                })
        
        return qa_pairs
    
    def _parse_structured_text(self, text: str) -> List[Dict[str, str]]:
        """Fallback: Parse structured text format if JSON fails."""
        import re
        
        qa_pairs = []
        
        # Try to find patterns like "Question: ... Answer: ..."
        pattern = r'(?:Question|Q)[\s:]*([^\n]+(?:\n(?!Answer|Q)[^\n]+)*)[\s\n]*(?:Answer|A)[\s:]*([^\n]+(?:\n(?!Question|Q)[^\n]+)*)'
        matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        
        for match in matches:
            question = match.group(1).strip()
            answer = match.group(2).strip()
            if question and answer:
                qa_pairs.append({
                    "question": question,
                    "answer": answer
                })
        
        # If no matches, try numbered format
        if not qa_pairs:
            # Pattern for "1. Question text\nAnswer: ..."
            pattern2 = r'\d+[\.\)]\s*([^\n]+(?:\n(?!\d+[\.\)]|Answer)[^\n]+)*)[\s\n]*(?:Answer|Solution)[\s:]*([^\n]+(?:\n(?!\d+[\.\)])[^\n]+)*)'
            matches2 = re.finditer(pattern2, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
            
            for match in matches2:
                question = match.group(1).strip()
                answer = match.group(2).strip()
                if question and answer:
                    qa_pairs.append({
                        "question": question,
                        "answer": answer
                    })
        
        return qa_pairs if qa_pairs else []
    
    def _parse_with_alternative_method(self, pdf_text: str) -> List[Dict[str, str]]:
        """Alternative parsing method using a simpler format request."""
        # Use a delimiter-based format that's easier to parse
        prompt = f"""Extract all question-answer pairs from this document.

For each pair, format it as:
QUESTION_START
[question text here]
QUESTION_END
ANSWER_START
[answer text here]
ANSWER_END

Repeat for all pairs found.

Document:
{pdf_text[:100000]}

Extract all pairs now:"""
        
        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Parse the delimiter-based format
            qa_pairs = []
            parts = response_text.split("QUESTION_START")
            
            for part in parts[1:]:  # Skip first empty part
                if "QUESTION_END" in part and "ANSWER_START" in part and "ANSWER_END" in part:
                    question = part.split("QUESTION_END")[0].strip()
                    answer_part = part.split("ANSWER_START")[1]
                    answer = answer_part.split("ANSWER_END")[0].strip()
                    
                    if question and answer:
                        qa_pairs.append({
                            "question": question,
                            "answer": answer
                        })
            
            return qa_pairs if qa_pairs else []
        except Exception:
            return []
    
    def parse_pdf(self, pdf_path: str, use_gemini: bool = True) -> List[Dict[str, str]]:
        """Parse PDF and extract Q&A pairs.
        
        Args:
            pdf_path: Path to the PDF file
            use_gemini: Whether to use Gemini API for parsing (recommended)
        
        Returns:
            List of dictionaries with 'question' and 'answer' keys
        """
        if use_gemini and self.model:
            return self.parse_with_gemini(pdf_path)
        else:
            # Fallback to simple text extraction and pattern matching
            return self._parse_with_patterns(pdf_path)
    
    def _parse_with_patterns(self, pdf_path: str) -> List[Dict[str, str]]:
        """Fallback parsing method using pattern matching."""
        text = self.extract_text_from_pdf(pdf_path)
        
        # Simple pattern matching for Q&A pairs
        # This is a basic implementation - can be improved
        qa_pairs = []
        lines = text.split('\n')
        
        current_question = None
        current_answer = []
        in_answer = False
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Detect question markers
            if any(marker in line.lower() for marker in ['question', 'q:', 'q.', '?']):
                if current_question and current_answer:
                    qa_pairs.append({
                        "question": current_question,
                        "answer": " ".join(current_answer)
                    })
                current_question = line
                current_answer = []
                in_answer = False
            # Detect answer markers
            elif any(marker in line.lower() for marker in ['answer', 'a:', 'a.', 'solution']):
                in_answer = True
                if line.lower().startswith(('answer', 'a:', 'a.')):
                    answer_text = line.split(':', 1)[-1].strip() if ':' in line else line
                    if answer_text:
                        current_answer.append(answer_text)
            elif in_answer:
                current_answer.append(line)
            elif not current_question:
                # Might be a question without explicit marker
                if '?' in line:
                    current_question = line
        
        # Add last pair
        if current_question and current_answer:
            qa_pairs.append({
                "question": current_question,
                "answer": " ".join(current_answer)
            })
        
        return qa_pairs

