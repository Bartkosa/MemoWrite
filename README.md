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

### 2. Database Setup (PostgreSQL Required)

This application requires PostgreSQL. You can use a local PostgreSQL instance or a cloud service.

#### Option A: Cloud PostgreSQL (Recommended for Deployment)

**For deployed apps, use a cloud PostgreSQL service:**

1. **Heroku Postgres** (if deploying to Heroku):
   - Add Heroku Postgres addon: `heroku addons:create heroku-postgresql:mini`
   - The `DATABASE_URL` is automatically set by Heroku

2. **Supabase** (Free tier available):
   - Sign up at [supabase.com](https://supabase.com)
   - Create a new project
   - Go to Settings → Database → Connection string
   - Copy the connection string (URI format)

3. **Neon** (Serverless PostgreSQL, free tier):
   - Sign up at [neon.tech](https://neon.tech)
   - Create a new project
   - Copy the connection string from the dashboard

4. **AWS RDS, Google Cloud SQL, Azure Database**:
   - Follow your cloud provider's documentation to create a PostgreSQL instance
   - Copy the connection string

#### Option B: Local PostgreSQL

1. Install PostgreSQL on your system
2. Create a database:
   ```sql
   CREATE DATABASE memowrite;
   ```
3. Note your connection details (host, port, username, password)

### 3. Configure Environment Variables

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_gemini_api_key_here
DATABASE_URL=postgresql://username:password@host:port/database
MAX_ANSWER_LENGTH=5000
GRADING_STRICTNESS=0.7
```

**For deployed apps (Streamlit Cloud, Heroku, etc.):**
- Set `DATABASE_URL` in your platform's environment variables/secrets
- Set `GEMINI_API_KEY` in your platform's secrets

Get your Gemini API key from [Google AI Studio](https://makersuite.google.com/app/apikey).

### 4. Run the Application

```bash
streamlit run app.py
```

The application will open in your browser at `http://localhost:8501`.

## Deployment

### Deploying to Streamlit Cloud

1. Push your code to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your repository
4. Add secrets in the Streamlit Cloud dashboard:
   - `DATABASE_URL`: Your PostgreSQL connection string (from Supabase, Neon, etc.)
   - `GEMINI_API_KEY`: Your Gemini API key
5. Deploy!

### Deploying to Heroku

1. Create a `Procfile`:
   ```
   web: streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
   ```
2. Add Heroku Postgres:
   ```bash
   heroku addons:create heroku-postgresql:mini
   ```
3. Set your Gemini API key:
   ```bash
   heroku config:set GEMINI_API_KEY=your_key_here
   ```
4. Deploy:
   ```bash
   git push heroku main
   ```

**Note**: The `DATABASE_URL` is automatically set by Heroku Postgres, so you don't need to set it manually.

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
├── database.py            # PostgreSQL database operations
├── grader.py              # LLM-based answer grading
├── spaced_repetition.py   # SR algorithm implementation
├── course_context.py      # Course PDF processing
├── config.py              # Configuration settings
├── requirements.txt       # Python dependencies
├── README.md              # This file
└── data/
    └── uploads/           # Uploaded PDFs storage
```

## Configuration

You can adjust settings in `config.py` or via environment variables:

- `DATABASE_URL`: **Required** - PostgreSQL connection string (e.g., `postgresql://user:pass@host:port/dbname`)
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

- **Missing DATABASE_URL**: The application requires `DATABASE_URL` to be set. Make sure it's in your `.env` file or environment variables
- **Connection errors**: Verify your `DATABASE_URL` connection string is correct
  - Format: `postgresql://username:password@host:port/database`
  - For cloud services, check your provider's dashboard for the connection string
- **Permission errors**: Ensure the database user has proper permissions (CREATE, INSERT, UPDATE, DELETE, SELECT)
- **Import errors**: Install `psycopg2-binary` if you get import errors: `pip install psycopg2-binary`
- **Cloud database**: For deployed apps, ensure your cloud PostgreSQL instance is accessible from your deployment platform

## License

This project is for educational purposes.

