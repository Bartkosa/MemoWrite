"""Main Streamlit application for MemoWrite."""
import streamlit as st
import os
import pandas as pd
import re
from datetime import date
from typing import List, Dict
from database import Database
from pdf_parser import PDFParser
from grader import Grader
from spaced_repetition import SpacedRepetition
from config import GEMINI_API_KEY
from auth import require_auth, get_user_email, get_user_name, get_user_picture, logout


def fix_text_spacing(text: str) -> str:
    """Fix spacing issues in extracted text.
    
    Adds spaces between words that are stuck together, fixes common issues:
    - Words stuck together: "HelloWorld" -> "Hello World"
    - Missing spaces after punctuation: "Hello.World" -> "Hello. World"
    - Multiple spaces -> single space
    """
    if not text:
        return text
    
    # Fix: add space between lowercase and uppercase (e.g., "HelloWorld" -> "Hello World")
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    
    # Fix: add space after punctuation if missing (but not for decimals like 3.14)
    text = re.sub(r'([.!?])([A-Za-z])', r'\1 \2', text)
    text = re.sub(r'([,;:])([A-Za-z])', r'\1 \2', text)
    
    # Fix: add space before opening parentheses/brackets if missing
    text = re.sub(r'([A-Za-z0-9])(\()', r'\1 \2', text)
    
    # Fix: normalize whitespace (multiple spaces/newlines -> single)
    text = re.sub(r'[ \t]+', ' ', text)  # Multiple spaces -> single space
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)  # Multiple newlines -> double
    
    # Remove leading/trailing whitespace from each line
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)
    
    # Final cleanup: remove any remaining double spaces
    while '  ' in text:
        text = text.replace('  ', ' ')
    
    return text.strip()

# Page configuration
st.set_page_config(
    page_title="MemoWrite",
    page_icon="📚",
    layout="wide"
)

# Initialize session state
if 'db' not in st.session_state:
    st.session_state.db = Database()

if 'grader' not in st.session_state:
    try:
        st.session_state.grader = Grader()
    except Exception as e:
        st.session_state.grader = None
        st.session_state.grader_error = str(e)

if 'sr' not in st.session_state:
    st.session_state.sr = SpacedRepetition()

if 'current_question' not in st.session_state:
    st.session_state.current_question = None

if 'last_grading_result' not in st.session_state:
    st.session_state.last_grading_result = None


def main():
    """Main application entry point."""
    # Require authentication
    require_auth()
    
    # Get user information
    user_email = get_user_email()
    user_name = get_user_name()
    user_picture = get_user_picture()
    
    # Get or create user in database
    if user_email:
        # Ensure user_id is set in session state
        if 'user_id' not in st.session_state or not st.session_state.user_id:
            # Use email as user_id for simplicity
            user_id = st.session_state.db.get_or_create_user(
                user_id=user_email,
                email=user_email,
                name=user_name,
                picture_url=user_picture
            )
            st.session_state.user_id = user_id
        else:
            user_id = st.session_state.user_id
    else:
        st.error("❌ User email not available. Please log in again.")
        st.stop()
    
    # Display user info in sidebar
    st.sidebar.title("User")
    if user_picture:
        st.sidebar.image(user_picture, width=60)
    st.sidebar.write(f"**{user_name or 'User'}**")
    st.sidebar.caption(user_email)
    if st.sidebar.button("🚪 Logout", type="secondary"):
        logout()
    
    st.sidebar.divider()
    
    st.title("📚 MemoWrite")
    st.markdown("Personalized learning with spaced repetition and AI-powered grading")
    
    # Check API key
    if not GEMINI_API_KEY:
        st.error("⚠️ GEMINI_API_KEY not configured. Please set it in your .env file.")
        st.stop()
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    page_options = ["📤 Upload Questions", "📖 Study", "📊 Progress Dashboard", "⚙️ Manage Questions"]
    
    # Get page from session state or use radio selection
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "📤 Upload Questions"
    
    # If page was set programmatically (e.g., from "Go study!" button), use that
    page = st.session_state.current_page
    
    # Create radio button and update session state if user manually selects
    selected_page = st.sidebar.radio(
        "Go to",
        page_options,
        index=page_options.index(page) if page in page_options else 0
    )
    
    # Update session state if user manually changed page
    if selected_page != st.session_state.current_page:
        st.session_state.current_page = selected_page
        page = selected_page
    
    if page == "📤 Upload Questions":
        show_upload_page()
    elif page == "📖 Study":
        show_study_page()
    elif page == "📊 Progress Dashboard":
        show_progress_page()
    elif page == "⚙️ Manage Questions":
        show_manage_questions_page()


def save_questions_to_database(qa_pairs: List[Dict[str, str]], source_pdf_name: str) -> int:
    """Save Q&A pairs to database.
    
    Args:
        qa_pairs: List of dictionaries with 'question' and 'answer' keys
        source_pdf_name: Name of the source PDF file
        
    Returns:
        Number of questions successfully saved
    """
    user_id = st.session_state.get('user_id')
    if not user_id:
        # Try to get or create user if not set
        user_email = get_user_email()
        if user_email:
            user_name = get_user_name()
            user_picture = get_user_picture()
            user_id = st.session_state.db.get_or_create_user(
                user_id=user_email,
                email=user_email,
                name=user_name,
                picture_url=user_picture
            )
            st.session_state.user_id = user_id
        else:
            raise Exception("User not authenticated. Please log in again.")
    
    saved_count = 0
    for pair in qa_pairs:
        try:
            # Fix spacing before saving
            question = fix_text_spacing(pair['question'])
            answer = fix_text_spacing(pair['answer'])
            
            st.session_state.db.add_question(
                user_id=user_id,
                question_text=question,
                reference_answer=answer,
                source_pdf=source_pdf_name
            )
            saved_count += 1
        except Exception as e:
            st.warning(f"Error saving question: {str(e)}")
    
    return saved_count


def show_upload_page():
    """Display the PDF upload page."""
    st.header("Upload Exam Questions")
    st.markdown("Upload a PDF file containing exam questions and answers.")
    
    # Ensure user_id is set
    user_id = st.session_state.get('user_id')
    if not user_id:
        user_email = get_user_email()
        if user_email:
            user_name = get_user_name()
            user_picture = get_user_picture()
            user_id = st.session_state.db.get_or_create_user(
                user_id=user_email,
                email=user_email,
                name=user_name,
                picture_url=user_picture
            )
            st.session_state.user_id = user_id
        else:
            st.error("❌ User not authenticated. Please log in again.")
            return
    
    # ========== FILE UPLOAD AND PARSING SECTION ==========
    uploaded_file = st.file_uploader(
        "Choose a PDF file",
        type=['pdf'],
        help="Upload a PDF with questions and answers",
        key="pdf_uploader"
    )
    
    # Check if we have cached parsed results for this file
    cached_file_name = st.session_state.get('last_parsed_filename')
    cached_qa_pairs = st.session_state.get('cached_qa_pairs', [])
    
    # If file changed or no cache exists, parse the PDF
    # Skip parsing if we just saved (to prevent re-parsing after save)
    if uploaded_file is not None:
        # Reset just_saved flag if a new file is uploaded
        if cached_file_name != uploaded_file.name:
            st.session_state.just_saved = False
        
        if not st.session_state.get('just_saved', False):
            if cached_file_name != uploaded_file.name or not cached_qa_pairs:
                # New file or no cache - parse it
                parser = PDFParser()
                
                with st.spinner("Processing PDF..."):
                    try:
                        # Save uploaded file
                        pdf_path = parser.save_uploaded_pdf(uploaded_file)
                        
                        # Parse PDF
                        st.info("Extracting questions and answers using Gemini API...")
                        
                        # Parse with progress updates
                        try:
                            qa_pairs = parser.parse_with_gemini(pdf_path)
                            # Cache the results (even if empty, so we know parsing completed)
                            st.session_state.last_parsed_filename = uploaded_file.name
                            st.session_state.cached_qa_pairs = qa_pairs
                            
                            # Check if parsing returned empty results
                            if not qa_pairs or len(qa_pairs) == 0:
                                st.warning("⚠️ No questions and answers found in the PDF. Please check the format.")
                                return
                            
                            # Show success and rerun to display preview
                            st.success(f"✅ Successfully extracted {len(qa_pairs)} question-answer pairs! Loading preview...")
                            st.rerun()
                        except Exception as parse_error:
                            raise parse_error
                    except Exception as e:
                        st.error(f"❌ Error processing PDF: {str(e)}")
                        st.info("Tip: Make sure your PDF contains clearly formatted questions and answers.")
                        return
        elif cached_qa_pairs:
            # Use cached results - no need to parse again (after save, just show the preview)
            qa_pairs = cached_qa_pairs
            if len(qa_pairs) == 0:
                st.warning("⚠️ No questions and answers found in the PDF. Please check the format.")
                return
    
    # ========== PREVIEW SECTION ==========
    # Only show preview if we have cached results with at least one Q&A pair
    # Check both uploaded_file and cached_filename to handle reruns
    has_uploaded_file = uploaded_file is not None or cached_file_name is not None
    if has_uploaded_file and cached_qa_pairs and len(cached_qa_pairs) > 0:
        qa_pairs = cached_qa_pairs
        st.divider()
        st.success(f"✅ Successfully extracted {len(qa_pairs)} question-answer pairs!")
        
        # Save button at the top
        col_top1, col_top2 = st.columns([1, 4])
        with col_top1:
            if st.button("💾 Save to Database", type="primary", use_container_width=True, key="save_top"):
                try:
                    with st.spinner("Saving questions to database..."):
                        # Use cached filename if uploaded_file is None (after rerun)
                        source_pdf_name = uploaded_file.name if uploaded_file else cached_file_name
                        saved_count = save_questions_to_database(qa_pairs, source_pdf_name)
                        
                        # Don't clear cache - keep it so preview can still be shown after rerun
                        # Cache will be cleared automatically when a new file is uploaded
                        
                        st.success(f"✅ Saved {saved_count} questions to database!")
                        st.balloons()
                        # Set flags
                        st.session_state.show_go_study = True
                        st.session_state.just_saved = True  # Prevent re-parsing
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ Error saving to database: {str(e)}")
        
        with col_top2:
            st.info(f"Ready to save {len(qa_pairs)} question-answer pairs to your database.")
        
        # Show "Go study!" button if save was successful (at top)
        if st.session_state.get('show_go_study', False):
            st.markdown("---")
            if st.button("📖 Go study!", type="primary", use_container_width=True, key="go_study_top"):
                # Navigate to Study page
                st.session_state.current_page = "📖 Study"
                st.session_state.show_go_study = False
                st.session_state.just_saved = False  # Reset flag
                st.rerun()
        
        # Show preview of ALL questions
        with st.expander(f"📋 Preview all {len(qa_pairs)} extracted Q&A pairs", expanded=True):
            for i, pair in enumerate(qa_pairs, 1):
                # Fix spacing issues
                question = fix_text_spacing(pair['question'])
                answer = fix_text_spacing(pair['answer'])
                
                st.markdown(f"### Question {i} of {len(qa_pairs)}")
                st.markdown("**Question:**")
                st.text_area(
                    f"Q{i}",
                    value=question,
                    height=min(200, len(question.split('\n')) * 25 + 50),
                    key=f"preview_q_{i}",
                    label_visibility="collapsed"
                )
                st.markdown("**Answer:**")
                st.text_area(
                    f"A{i}",
                    value=answer,
                    height=min(300, len(answer.split('\n')) * 25 + 50),
                    key=f"preview_a_{i}",
                    label_visibility="collapsed"
                )
                if i < len(qa_pairs):
                    st.divider()
        
        # Save button at the bottom
        st.divider()
        col_bottom1, col_bottom2 = st.columns([1, 4])
        with col_bottom1:
            if st.button("💾 Save to Database", type="primary", use_container_width=True, key="save_bottom"):
                try:
                    with st.spinner("Saving questions to database..."):
                        # Use cached filename if uploaded_file is None (after rerun)
                        source_pdf_name = uploaded_file.name if uploaded_file else cached_file_name
                        saved_count = save_questions_to_database(qa_pairs, source_pdf_name)
                        
                        # Don't clear cache - keep it so preview can still be shown after rerun
                        # Cache will be cleared automatically when a new file is uploaded
                        
                        st.success(f"✅ Saved {saved_count} questions to database!")
                        st.balloons()
                        # Set flags
                        st.session_state.show_go_study = True
                        st.session_state.just_saved = True  # Prevent re-parsing
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ Error saving to database: {str(e)}")
        
        with col_bottom2:
            st.info(f"Ready to save {len(qa_pairs)} question-answer pairs to your database.")
        
        # Show "Go study!" button at bottom if save was successful
        if st.session_state.get('show_go_study', False):
            st.markdown("---")
            if st.button("📖 Go study!", type="primary", use_container_width=True, key="go_study_bottom"):
                # Navigate to Study page
                st.session_state.current_page = "📖 Study"
                st.session_state.show_go_study = False
                st.session_state.just_saved = False  # Reset flag
                st.rerun()


def show_study_page():
    """Display the study page."""
    st.header("📖 Study Session")
    user_id = st.session_state.user_id
    
    # Get all questions for manual selection
    all_questions = st.session_state.db.get_all_questions(user_id)
    
    if not all_questions:
        st.info("No questions available. Please upload some questions first.")
        return
    
    # Main action: Get Next Question (prominent)
    st.subheader("Get Next Question")
    col_main = st.columns([1, 2, 1])
    with col_main[1]:
        if st.button("🔄 Get Next Question", type="primary", use_container_width=True, key="get_next_main"):
            user_id = st.session_state.user_id
            question_data = st.session_state.db.get_next_question_for_review(user_id)
            if question_data:
                st.session_state.current_question = question_data
                st.session_state.last_grading_result = None
                st.rerun()
            else:
                st.info("No questions due for review. You can select a specific question below.")
    
    # Alternative: Select specific question (less prominent)
    with st.expander("🔍 Or select a specific question", expanded=False):
        # Create a dropdown/selectbox for manual question selection
        question_options = {
            f"Q{q['question_id']}: {q['question_text'][:60]}{'...' if len(q['question_text']) > 60 else ''}": q['question_id']
            for q in all_questions
        }
        
        selected_question_label = st.selectbox(
            "Choose a question to practice:",
            options=list(question_options.keys()),
            index=0,
            key="question_selector"
        )
        
        selected_question_id = question_options[selected_question_label]
        
        # Button to load selected question
        if st.button("📝 Load Selected Question", use_container_width=True, key="load_selected"):
            user_id = st.session_state.user_id
            question_data = st.session_state.db.get_question(user_id, selected_question_id)
            if question_data:
                # Get spaced repetition data if available
                sr_data = st.session_state.db.get_spaced_repetition(selected_question_id)
                if sr_data:
                    question_data.update(sr_data)
                st.session_state.current_question = question_data
                st.session_state.last_grading_result = None
                st.rerun()
    
    st.markdown("---")
    
    # Display current question
    if st.session_state.current_question:
        question_data = st.session_state.current_question
        question_id = question_data['question_id']
        question_text = question_data['question_text']
        
        st.markdown("---")
        st.subheader("Question")
        st.markdown(f"**{question_text}**")
        
        # Show SR info
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Ease Factor", f"{question_data.get('ease_factor', 2.5):.2f}")
        with col2:
            st.metric("Repetitions", question_data.get('repetitions', 0))
        with col3:
            next_review = question_data.get('next_review_date')
            if next_review:
                if isinstance(next_review, str):
                    next_review = date.fromisoformat(next_review)
                days_until = (next_review - date.today()).days
                st.metric("Days Until Review", days_until)
        
        st.markdown("---")
        
        # Answer input
        st.subheader("Your Answer")
        user_answer = st.text_area(
            "Type your answer here:",
            height=200,
            key=f"answer_{question_id}",
            help="Write your answer to the question. It will be graded using AI."
        )
        
        col1, col2 = st.columns([1, 4])
        with col1:
            submit_button = st.button("✅ Submit Answer", type="primary")
        with col2:
            show_reference = st.button("👁️ Show Reference Answer")
        
        if show_reference:
            st.info(f"**Reference Answer:**\n\n{question_data['reference_answer']}")
        
        if submit_button and user_answer.strip():
            if st.session_state.grader is None:
                st.error("Grading service unavailable. Please check your API configuration.")
            else:
                with st.spinner("Grading your answer..."):
                    try:
                        grading_result = st.session_state.grader.grade_answer(
                            question=question_text,
                            reference_answer=question_data['reference_answer'],
                            user_answer=user_answer
                        )
                        
                        # Save answer and grading result
                        user_id = st.session_state.user_id
                        st.session_state.db.add_user_answer(
                            user_id=user_id,
                            question_id=question_id,
                            user_answer=user_answer,
                            score=grading_result['score'],
                            feedback=grading_result['feedback'],
                            missing_concepts=grading_result['missing_concepts']
                        )
                        
                        # Update spaced repetition
                        sr_data = st.session_state.db.get_spaced_repetition(question_id)
                        if sr_data:
                            new_sr = st.session_state.sr.calculate_next_review(
                                current_ease=sr_data['ease_factor'],
                                current_interval=sr_data['interval'],
                                current_repetitions=sr_data['repetitions'],
                                quality=grading_result['score']
                            )
                            
                            st.session_state.db.update_spaced_repetition(
                                question_id=question_id,
                                ease_factor=new_sr['ease_factor'],
                                interval=new_sr['interval'],
                                repetitions=new_sr['repetitions'],
                                next_review_date=new_sr['next_review_date'],
                                last_review_date=date.today()
                            )
                        
                        # Update progress
                        st.session_state.db.update_progress(
                            question_id=question_id,
                            score=grading_result['score']
                        )
                        
                        st.session_state.last_grading_result = {
                            'score': grading_result['score'],
                            'feedback': grading_result['feedback'],
                            'missing_concepts': grading_result['missing_concepts']
                        }
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Error grading answer: {str(e)}")
        
        # Display grading results
        if st.session_state.last_grading_result:
            st.markdown("---")
            st.subheader("📊 Grading Results")
            
            result = st.session_state.last_grading_result
            score = result['score']
            
            # Score display with color
            if score >= 90:
                score_color = "🟢"
            elif score >= 70:
                score_color = "🟡"
            else:
                score_color = "🔴"
            
            st.metric("Score", f"{score_color} {score:.1f}/100")
            
            # Feedback
            st.markdown("**Feedback:**")
            st.info(result['feedback'])
            
            # Missing concepts
            if result['missing_concepts'] and result['missing_concepts'].lower() != "none identified.":
                st.markdown("**Missing Concepts:**")
                st.warning(result['missing_concepts'])
            
            # Progress indicator
            st.progress(score / 100)
            
            # Next steps
            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("➡️ Next (Spaced Repetition)", type="primary"):
                    user_id = st.session_state.user_id
                    question_data = st.session_state.db.get_next_question_for_review(user_id)
                    if question_data:
                        st.session_state.current_question = question_data
                        st.session_state.last_grading_result = None
                        st.rerun()
                    else:
                        st.info("No more questions due for review. You can select a specific question from the expander above!")
            with col2:
                if st.button("🔄 Select Another Question"):
                    st.session_state.current_question = None
                    st.session_state.last_grading_result = None
                    st.rerun()
    
    else:
        st.info("👆 Click 'Get Next Question' above to start studying, or select a specific question from the expander!")


def show_progress_page():
    """Display the progress dashboard."""
    st.header("📊 Progress Dashboard")
    user_id = st.session_state.user_id
    
    # Overall statistics
    stats = st.session_state.db.get_progress_stats(user_id)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Questions", stats.get('total_questions', 0))
    with col2:
        avg_mastery = stats.get('avg_mastery', 0) or 0
        st.metric("Average Mastery", f"{avg_mastery:.1f}%")
    with col3:
        st.metric("Total Attempts", stats.get('total_attempts', 0))
    with col4:
        success_rate = stats.get('success_rate', 0) or 0
        st.metric("Success Rate", f"{success_rate:.1f}%")
    
    st.markdown("---")
    
    # Detailed progress table
    st.subheader("Question-by-Question Progress")
    user_id = st.session_state.user_id
    progress_data = st.session_state.db.get_all_progress(user_id)
    
    if progress_data:
        # Prepare data for display
        display_data = []
        for item in progress_data:
            display_data.append({
                "Question ID": item['question_id'],
                "Question": item['question_text'][:100] + "..." if len(item.get('question_text', '')) > 100 else item.get('question_text', ''),
                "Mastery": f"{item['mastery_level']:.1f}%",
                "Attempts": item['total_attempts'],
                "Correct": item['correct_attempts'],
                "Last Reviewed": item['last_reviewed'] if item['last_reviewed'] else "Never"
            })
        
        df = pd.DataFrame(display_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Questions due for review
        st.markdown("---")
        st.subheader("Questions Due for Review")
        user_id = st.session_state.user_id
        due_questions = st.session_state.db.get_questions_due_for_review(user_id)
        
        if due_questions:
            st.info(f"You have {len(due_questions)} question(s) due for review.")
            for q in due_questions[:5]:  # Show first 5
                with st.expander(f"Question {q['question_id']}: {q['question_text'][:80]}..."):
                    st.markdown(f"**Question:** {q['question_text']}")
                    st.markdown(f"**Next Review:** {q.get('next_review_date', 'N/A')}")
                    st.markdown(f"**Ease Factor:** {q.get('ease_factor', 2.5):.2f}")
        else:
            st.success("🎉 No questions due for review! You're all caught up!")
    else:
        st.info("No progress data yet. Start studying to see your progress!")


def show_manage_questions_page():
    """Display the question management page for editing and deleting questions."""
    st.header("⚙️ Manage Questions")
    st.markdown("Add, edit, or delete questions from your database.")
    user_id = st.session_state.user_id
    
    # Get all questions
    all_questions = st.session_state.db.get_all_questions(user_id)
    
    # Add new question section
    st.subheader("➕ Add New Question")
    with st.expander("Click to add a new question", expanded=False):
        with st.form("add_question_form"):
            new_question_text = st.text_area(
                "Question Text",
                placeholder="Enter the question here...",
                height=150,
                key="new_question_text"
            )
            
            new_answer_text = st.text_area(
                "Reference Answer",
                placeholder="Enter the reference answer here...",
                height=200,
                key="new_answer_text"
            )
            
            new_source_pdf = st.text_input(
                "Source PDF (optional)",
                placeholder="e.g., AI-Questions.pdf",
                key="new_source_pdf"
            )
            
            col1, col2 = st.columns([1, 4])
            with col1:
                add_button = st.form_submit_button("➕ Add Question", type="primary")
            
            if add_button:
                if new_question_text.strip() and new_answer_text.strip():
                    try:
                        user_id = st.session_state.user_id
                        question_id = st.session_state.db.add_question(
                            user_id=user_id,
                            question_text=new_question_text.strip(),
                            reference_answer=new_answer_text.strip(),
                            source_pdf=new_source_pdf.strip() if new_source_pdf.strip() else None
                        )
                        st.success(f"✅ Question {question_id} added successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error adding question: {str(e)}")
                else:
                    st.warning("⚠️ Question and answer cannot be empty!")
    
    st.markdown("---")
    
    if not all_questions:
        st.info("No questions in the database. Add a question above or upload a PDF!")
        return
    
    st.metric("Total Questions", len(all_questions))
    
    # Database management section
    with st.expander("🗑️ Clear All Questions", expanded=False):
        st.warning("⚠️ This will delete ALL your questions and progress data!")
        if st.button("🗑️ Clear All Questions", type="secondary", key="clear_all_questions"):
            st.session_state.db.delete_all_questions(user_id)
            st.success("✅ All questions deleted!")
            st.rerun()
    
    st.markdown("---")
    
    # Search/filter
    search_term = st.text_input("🔍 Search questions", placeholder="Type to filter questions...")
    
    # Filter questions based on search
    filtered_questions = all_questions
    if search_term:
        search_lower = search_term.lower()
        filtered_questions = [
            q for q in all_questions
            if search_lower in q['question_text'].lower() or search_lower in q['reference_answer'].lower()
        ]
    
    if not filtered_questions:
        st.warning("No questions match your search.")
        return
    
    st.info(f"Showing {len(filtered_questions)} of {len(all_questions)} questions")
    
    # Display questions with edit/delete options
    for question in filtered_questions:
        question_id = question['question_id']
        
        with st.expander(
            f"Question {question_id}: {question['question_text'][:80]}{'...' if len(question['question_text']) > 80 else ''}",
            expanded=False
        ):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.markdown(f"**Question ID:** {question_id}")
                st.markdown(f"**Source PDF:** {question.get('source_pdf', 'N/A')}")
                st.markdown(f"**Created:** {question.get('created_at', 'N/A')}")
            
            with col2:
                if st.button("🗑️ Delete", key=f"delete_{question_id}", type="secondary"):
                    user_id = st.session_state.user_id
                    if st.session_state.db.delete_question(user_id, question_id):
                        st.success(f"✅ Question {question_id} deleted!")
                        st.rerun()
                    else:
                        st.error(f"❌ Failed to delete question {question_id}")
            
            st.markdown("---")
            
            # Edit form
            st.subheader("Edit Question")
            
            with st.form(f"edit_form_{question_id}"):
                edited_question = st.text_area(
                    "Question Text",
                    value=question['question_text'],
                    height=150,
                    key=f"q_text_{question_id}"
                )
                
                edited_answer = st.text_area(
                    "Reference Answer",
                    value=question['reference_answer'],
                    height=200,
                    key=f"q_answer_{question_id}"
                )
                
                col1, col2 = st.columns([1, 4])
                with col1:
                    save_button = st.form_submit_button("💾 Save Changes", type="primary")
                with col2:
                    if save_button:
                        if edited_question.strip() and edited_answer.strip():
                            try:
                                user_id = st.session_state.user_id
                                if st.session_state.db.update_question(
                                    user_id=user_id,
                                    question_id=question_id,
                                    question_text=edited_question.strip(),
                                    reference_answer=edited_answer.strip()
                                ):
                                    st.success(f"✅ Question {question_id} updated successfully!")
                                    st.rerun()
                                else:
                                    st.error(f"❌ Failed to update question {question_id}")
                            except Exception as e:
                                st.error(f"❌ Error updating question: {str(e)}")
                        else:
                            st.warning("⚠️ Question and answer cannot be empty!")
            
            # Display current question and answer for reference
            st.markdown("---")
            st.markdown("**Current Question:**")
            st.text(question['question_text'])
            st.markdown("**Current Answer:**")
            st.text(question['reference_answer'])


if __name__ == "__main__":
    main()

