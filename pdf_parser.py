"""PDF parsing module for extracting questions and answers from exam PDFs."""
import os
import json
import re
import pathlib
import time
import logging
import google.generativeai as genai
from typing import List, Dict
from config import GEMINI_API_KEY, GEMINI_MODEL, UPLOADS_DIR

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class PDFParser:
    """Parses PDF files to extract questions and answers using Gemini API."""
    
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
    
    def parse_with_gemini(self, pdf_path: str) -> List[Dict[str, str]]:
        """Use Gemini API to parse PDF and extract Q&A pairs.
        
        This method uploads the PDF file to Gemini and lets it extract Q&A pairs.
        Includes detailed logging to identify bottlenecks.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            List of dictionaries with 'question' and 'answer' keys
        """
        if not self.model:
            raise Exception("Gemini API key not configured. Please set GEMINI_API_KEY in .env file.")
        
        pdf_path_obj = pathlib.Path(pdf_path)
        file_size = os.path.getsize(pdf_path) if os.path.exists(pdf_path) else 0
        logger.info(f"Starting PDF parsing: {pdf_path_obj.name} ({file_size / 1024:.2f} KB)")
        
        prompt = """Extract ALL question-answer pairs from this PDF document.

CRITICAL REQUIREMENTS:
1. Extract EVERY question-answer pair you can find in the document
2. Only include pairs where BOTH question AND answer exist
3. Preserve all text, but fix spacing issues and formatting
4. Return ONLY valid JSON, no markdown, no explanations
5. Escape all special characters properly in JSON (use \\n for newlines, \\" for quotes)
6. Ensure the JSON is complete and properly closed

Return a JSON object with this exact structure:
{
  "qa_pairs": [
    {
      "question": "complete question text here",
      "answer": "complete answer/solution text here"
    }
  ]
}

IMPORTANT: Make sure all newlines in text are escaped as \\n in the JSON strings.
Extract all pairs now and return ONLY the JSON:"""

        try:
            # Step 1: Upload PDF file to Gemini
            upload_start = time.time()
            print(f"[Step 1/5] Uploading PDF file to Gemini... ({file_size / 1024:.2f} KB)")
            logger.info("Step 1: Uploading PDF file to Gemini...")
            uploaded_file = genai.upload_file(path=str(pdf_path_obj), mime_type='application/pdf')
            upload_time = time.time() - upload_start
            print(f"[Step 1/5] ✓ Upload completed in {upload_time:.2f}s. File ID: {uploaded_file.name[:20]}...")
            logger.info(f"✓ File upload initiated in {upload_time:.2f}s. File ID: {uploaded_file.name}")
            
            # Step 2: Wait for file to be processed
            processing_start = time.time()
            print(f"[Step 2/5] Waiting for Gemini to process the file... (current state: {uploaded_file.state.name})")
            logger.info(f"Step 2: Waiting for Gemini to process the file... (state: {uploaded_file.state.name})")
            poll_count = 0
            initial_state = uploaded_file.state.name
            
            while uploaded_file.state.name == "PROCESSING":
                poll_count += 1
                time.sleep(2)
                uploaded_file = genai.get_file(uploaded_file.name)
                if poll_count % 5 == 0:  # Log every 10 seconds
                    elapsed = time.time() - processing_start
                    print(f"[Step 2/5] Still processing... ({elapsed:.1f}s elapsed, {poll_count} polls)")
                    logger.info(f"  Still processing... ({elapsed:.1f}s elapsed)")
            
            processing_time = time.time() - processing_start
            final_state = uploaded_file.state.name
            if initial_state != "PROCESSING":
                print(f"[Step 2/5] ✓ File was already processed (state: {initial_state} → {final_state}) in {processing_time:.2f}s")
            else:
                print(f"[Step 2/5] ✓ Processing completed in {processing_time:.2f}s ({poll_count} polls, state: {final_state})")
            logger.info(f"✓ File processing completed in {processing_time:.2f}s ({poll_count} polls, state: {final_state})")
            
            if uploaded_file.state.name == "FAILED":
                raise Exception(f"File upload failed: {uploaded_file.state}")
            
            # Step 3: Generate content using the uploaded PDF
            generation_start = time.time()
            print(f"[Step 3/5] Sending prompt to Gemini for Q&A extraction...")
            logger.info("Step 3: Sending prompt to Gemini for Q&A extraction...")
            contents = [uploaded_file, prompt]
            response = self.model.generate_content(
                contents,
                generation_config={
                    "temperature": 0.1,
                    "max_output_tokens": 32768,
                }
            )
            generation_time = time.time() - generation_start
            response_length = len(response.text) if response.text else 0
            print(f"[Step 3/5] ✓ Response received in {generation_time:.2f}s ({response_length:,} characters)")
            logger.info(f"✓ Gemini response received in {generation_time:.2f}s ({response_length} characters)")
            
            # Step 4: Clean up uploaded file
            cleanup_start = time.time()
            print(f"[Step 4/5] Cleaning up uploaded file...")
            logger.info("Step 4: Cleaning up uploaded file...")
            cleanup_time = 0
            try:
                genai.delete_file(uploaded_file.name)
                cleanup_time = time.time() - cleanup_start
                print(f"[Step 4/5] ✓ Cleanup completed in {cleanup_time:.2f}s")
                logger.info(f"✓ File cleanup completed in {cleanup_time:.2f}s")
            except Exception as e:
                cleanup_time = time.time() - cleanup_start
                print(f"[Step 4/5] ⚠ Cleanup failed: {str(e)}")
                logger.warning(f"⚠ File cleanup failed: {str(e)}")
            
            # Step 5: Parse response
            parsing_start = time.time()
            print(f"[Step 5/5] Parsing JSON response...")
            logger.info("Step 5: Parsing JSON response...")
            
            response_text = response.text.strip()
            # Debug: Show first 500 chars of response
            print(f"[DEBUG] Response preview (first 500 chars): {response_text[:500]}...")
            logger.debug(f"Response preview: {response_text[:500]}")
            
            # Extract JSON from response (handle markdown code blocks)
            if "```" in response_text:
                # Try to extract JSON from code blocks
                json_matches = re.findall(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', response_text, re.DOTALL)
                if json_matches:
                    response_text = json_matches[0]
                else:
                    # Try without closing backticks (incomplete response)
                    json_matches = re.findall(r'```(?:json)?\s*(\{[\s\S]*)', response_text, re.DOTALL)
                    if json_matches:
                        response_text = json_matches[0]
            
            # Extract JSON object - find the first { and try to match to the end
            json_start = response_text.find('{')
            if json_start != -1:
                json_text = response_text[json_start:]
                
                # Try to find the matching closing brace
                # Count braces to find the end
                brace_count = 0
                in_string = False
                escape_next = False
                json_end = -1
                
                for i, char in enumerate(json_text):
                    if escape_next:
                        escape_next = False
                        continue
                    if char == '\\':
                        escape_next = True
                        continue
                    if char == '"' and not escape_next:
                        in_string = not in_string
                        continue
                    if not in_string:
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                json_end = i + 1
                                break
                
                if json_end > 0:
                    json_text = json_text[:json_end]
                # If we couldn't find the end, try to fix incomplete JSON
                elif json_text.count('{') > json_text.count('}'):
                    # Missing closing braces - try to complete it
                    missing_braces = json_text.count('{') - json_text.count('}')
                    # Try to extract what we can
                    json_text = json_text.rstrip() + '}' * missing_braces
            else:
                json_text = response_text
            
            # Try to fix common JSON issues before parsing
            # Replace unescaped newlines in string values (but be careful)
            # This is a simplified approach - we'll try parsing first
            
            # Parse JSON
            result = None
            json_error = None
            try:
                result = json.loads(json_text)
            except json.JSONDecodeError as e:
                json_error = str(e)
                # Try to fix unescaped newlines in string values
                # This regex finds string values and escapes newlines
                def fix_newlines(match):
                    content = match.group(1)
                    # Only fix if it's not already escaped
                    if '\n' in content and '\\n' not in content:
                        content = content.replace('\n', '\\n').replace('\r', '\\r')
                    return f'"{content}"'
                
                # Try to fix string values with unescaped newlines
                try:
                    # Pattern: "..." where ... might contain unescaped newlines
                    fixed_json = re.sub(r'"([^"\\]*(?:\\.[^"\\]*)*)"', fix_newlines, json_text)
                    result = json.loads(fixed_json)
                except:
                    # If that didn't work, try a simpler approach - just try to extract pairs manually
                    qa_pairs = self._extract_pairs_from_text(response_text)
                    if qa_pairs:
                        return qa_pairs
                    raise Exception(f"Failed to parse JSON response from Gemini. Error: {json_error}. Response preview: {response_text[:1000]}")
            
            if result is None:
                raise Exception(f"Failed to parse JSON response from Gemini. Response preview: {response_text[:1000]}")
            
            # Extract qa_pairs from result
            qa_pairs = []
            if isinstance(result, dict):
                pairs = result.get("qa_pairs", result.get("questions", result.get("pairs", [])))
                if not pairs and isinstance(result, list):
                    pairs = result
            elif isinstance(result, list):
                pairs = result
            else:
                pairs = []
            
            # Validate and format pairs
            validated_pairs = []
            for pair in pairs:
                if isinstance(pair, dict):
                    question = str(pair.get("question", "")).strip()
                    answer = str(pair.get("answer", "")).strip()
                    if question and answer:
                        validated_pairs.append({
                            "question": question,
                            "answer": answer
                        })
            
            parsing_time = time.time() - parsing_start
            total_time = time.time() - upload_start
            print(f"[Step 5/5] ✓ Parsing completed in {parsing_time:.2f}s. Found {len(validated_pairs)} Q&A pairs")
            print(f"\n{'='*70}")
            print(f"PERFORMANCE SUMMARY")
            print(f"{'='*70}")
            print(f"Total time: {total_time:.2f}s")
            print(f"  • Upload:      {upload_time:.2f}s ({upload_time/total_time*100:.1f}%)")
            print(f"  • Processing:   {processing_time:.2f}s ({processing_time/total_time*100:.1f}%)")
            print(f"  • Generation:   {generation_time:.2f}s ({generation_time/total_time*100:.1f}%)")
            print(f"  • Cleanup:      {cleanup_time:.2f}s ({cleanup_time/total_time*100:.1f}%)")
            print(f"  • Parsing:      {parsing_time:.2f}s ({parsing_time/total_time*100:.1f}%)")
            print(f"{'='*70}\n")
            logger.info(f"✓ Parsing completed in {parsing_time:.2f}s. Found {len(validated_pairs)} Q&A pairs")
            logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            logger.info(f"Total processing time: {total_time:.2f}s")
            logger.info(f"  - Upload: {upload_time:.2f}s ({upload_time/total_time*100:.1f}%)")
            logger.info(f"  - Processing: {processing_time:.2f}s ({processing_time/total_time*100:.1f}%)")
            logger.info(f"  - Generation: {generation_time:.2f}s ({generation_time/total_time*100:.1f}%)")
            logger.info(f"  - Parsing: {parsing_time:.2f}s ({parsing_time/total_time*100:.1f}%)")
            logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            
            return validated_pairs
            
        except Exception as e:
            logger.error(f"❌ Error parsing PDF: {str(e)}")
            raise Exception(f"Error parsing PDF with Gemini: {str(e)}")
    
    def _extract_pairs_from_text(self, text: str) -> List[Dict[str, str]]:
        """Fallback method to extract Q&A pairs from text when JSON parsing fails."""
        qa_pairs = []
        
        # Try multiple patterns to extract Q&A pairs
        
        # Pattern 1: Standard JSON format {"question": "...", "answer": "..."}
        # Handle both escaped and unescaped newlines
        pattern1 = r'"question"\s*:\s*"((?:[^"\\]|\\.|\\n|\n)*?)"\s*,\s*"answer"\s*:\s*"((?:[^"\\]|\\.|\\n|\n)*?)"'
        matches = re.finditer(pattern1, text, re.DOTALL)
        
        for match in matches:
            question = match.group(1)
            answer = match.group(2)
            # Handle both escaped and unescaped newlines
            question = question.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
            answer = answer.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
            
            if question.strip() and answer.strip():
                qa_pairs.append({
                    "question": question.strip(),
                    "answer": answer.strip()
                })
        
        # If we found pairs, return them
        if qa_pairs:
            return qa_pairs
        
        # Pattern 2: Try to extract from incomplete JSON (truncated response)
        # Look for question fields even if answer is incomplete
        pattern2 = r'"question"\s*:\s*"((?:[^"\\]|\\.|\\n|\n)*?)"'
        question_matches = list(re.finditer(pattern2, text, re.DOTALL))
        
        # Try to find corresponding answers
        for i, q_match in enumerate(question_matches):
            question = q_match.group(1).replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
            
            # Look for answer after this question
            search_start = q_match.end()
            answer_pattern = r'"answer"\s*:\s*"((?:[^"\\]|\\.|\\n|\n)*?)"'
            answer_match = re.search(answer_pattern, text[search_start:], re.DOTALL)
            
            if answer_match:
                answer = answer_match.group(1).replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
                if question.strip() and answer.strip():
                    qa_pairs.append({
                        "question": question.strip(),
                        "answer": answer.strip()
                    })
            else:
                # Answer might be incomplete - try to extract what we can
                # Look for "answer": " and take everything until end or next question
                answer_start = text.find('"answer": "', search_start)
                if answer_start != -1:
                    answer_start += len('"answer": "')
                    # Find next question or end of text
                    next_question = text.find('"question":', answer_start)
                    if next_question != -1:
                        answer_text = text[answer_start:next_question].rstrip().rstrip('"').rstrip(',')
                    else:
                        answer_text = text[answer_start:].rstrip().rstrip('"').rstrip(',')
                    
                    answer = answer_text.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
                    if question.strip() and answer.strip():
                        qa_pairs.append({
                            "question": question.strip(),
                            "answer": answer.strip()
                        })
        
        return qa_pairs
