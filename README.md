# MemoWrite

A personalized learning system that helps users memorize exam answers through spaced repetition. The system grades open-ended answers using AI (Gemini 2.0 Flash) and tracks progress to optimize learning.

## Features

- **AI-Powered PDF Parsing**: Automatically extracts questions and answers from exam PDFs using Gemini API
- **Semantic Grading**: LLM evaluates answer quality, not just keyword matching
- **Detailed Feedback**: Shows what concepts are missing or incorrect
- **Spaced Repetition**: Optimizes review schedule for long-term retention (SM-2 algorithm)
- **Progress Tracking**: Visual dashboard of mastery and improvement
- **Personalized Learning**: Adapts to user's performance patterns

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API Key

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_gemini_api_key_here
DATABASE_PATH=data/course_notes.db
MAX_ANSWER_LENGTH=5000
GRADING_STRICTNESS=0.7
```

Get your Gemini API key from [Google AI Studio](https://makersuite.google.com/app/apikey).

### 3. Run the Application

```bash
streamlit run app.py
```

The application will open in your browser at `http://localhost:8501`.

## Usage

### Upload Questions

1. Go to the "Upload Questions" page
2. Upload a PDF file containing exam questions and answers
3. The system will use Gemini API to extract Q&A pairs
4. Review the extracted pairs and save them to the database

### Study

1. Go to the "Study" page
2. Click "Get Next Question" to start
3. Type your answer in the text area
4. Click "Submit Answer" to get AI-powered grading
5. Review your score, feedback, and missing concepts
6. Continue with the next question

### Track Progress

1. Go to the "Progress Dashboard" page
2. View overall statistics (mastery, attempts, success rate)
3. See detailed progress for each question
4. Check which questions are due for review

## How It Works

### Spaced Repetition Algorithm

The system uses the SM-2 algorithm to optimize review timing:
- Questions you answer correctly are scheduled further in the future
- Questions you struggle with are reviewed more frequently
- The algorithm adapts based on your performance

### AI Grading

The grader uses Gemini 2.0 Flash to:
- Compare your answer against the reference answer
- Evaluate understanding and completeness
- Identify missing concepts
- Provide detailed feedback for improvement

## Project Structure

```
MemoWrite/
├── app.py                 # Main Streamlit application
├── pdf_parser.py          # PDF extraction logic
├── database.py            # SQLite database operations
├── grader.py              # LLM-based answer grading
├── spaced_repetition.py   # SR algorithm implementation
├── course_context.py      # Course PDF processing
├── config.py              # Configuration settings
├── requirements.txt       # Python dependencies
├── README.md              # This file
└── data/
    ├── course_notes.db    # SQLite database
    └── uploads/           # Uploaded PDFs storage
```

## Configuration

You can adjust settings in `config.py` or via environment variables:

- `GRADING_STRICTNESS`: How strict the grading is (0.0 = lenient, 1.0 = strict)
- `SR_INITIAL_EASE`: Initial ease factor for spaced repetition
- `MAX_ANSWER_LENGTH`: Maximum length for user answers

## Troubleshooting

### API Key Issues
- Make sure your `.env` file is in the project root
- Verify your Gemini API key is valid
- Check that you have API quota available

### PDF Parsing Issues
- Ensure PDFs contain clearly formatted questions and answers
- Try different PDF formats if parsing fails
- Check that the PDF text is selectable (not scanned images)

### Database Issues
- Delete `data/course_notes.db` to reset the database
- Ensure the `data/` directory exists and is writable

## License

This project is for educational purposes.

