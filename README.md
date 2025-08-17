# NewsBreak Ad Assistant Chatbot Analysis

This script analyzes CSV files containing chatbot conversations to understand what tasks the bot can and cannot handle, identify common topics, and find areas for improvement.

## What it does

The script processes each CSV conversation file and uses GPT to:
- Extract conversation transcripts
- Identify conversation topics and user tasks
- Determine if tasks were solved
- Find reasons for failures
- Identify bot capabilities and limitations
- Generate summary statistics and visualizations

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set your Cooper API key (optional):**
   ```bash
   export COOPER_API_KEY="your-cooper-api-key-here"
   ```

   Optional: If using a different Cooper endpoint or model:
   ```bash
   export COOPER_BASE_URL="http://your-cooper-endpoint/v1/chat/completions"
   export COOPER_MODEL="gpt-4o"
   ```

   Note: The script comes with default Cooper API credentials, so you may not need to set these.

## Usage

### Basic usage
```bash
# Analyze all CSV files in current directory
python analyze_chats.py

# Analyze files in a specific directory
python analyze_chats.py --input_glob "Bot_714b4955-90a2-4693-9380-a28dffee2e3a_Year_2025_4a86f154be3a4925a510e33bdda399b3 (3)/*.csv"

# Limit to first 10 files for testing
python analyze_chats.py --sample_limit 10
```

### Test without API calls
```bash
# Quick test to verify file processing works
python analyze_chats.py --dry_run --sample_limit 3
```

## Output files

The script creates an `analysis_out/` directory with:

- **`per_chat.jsonl`** - Raw GPT analysis for each conversation
- **`summary.csv`** - Summary table with topics, solved status, etc.
- **`topic_stats.csv`** - Counts and solve rates per topic
- **`reasons.csv`** - Top failure reasons
- **`topics.png`** - Bar chart of most common topics
- **`reasons.png`** - Bar chart of failure reasons
- **`report.md`** - Human-readable summary report

## CSV file format

The script expects CSV files with these columns:
- `Sender type` - Identifies user vs bot messages
- `Time in GMT` - Timestamp for each message
- `Message` - The actual message content
- `Data` - Additional structured data (optional)

## Cost optimization

- **Transcript truncation**: Long conversations are truncated to 8000 characters
- **Rate limiting**: Built-in rate limiting (50 requests/minute)
- **Sample testing**: Use `--sample_limit` to test with fewer files first
- **Dry run**: Use `--dry_run` to test file processing without API calls

## Example analysis

The script will identify topics like:
- Account management
- Ad policy questions
- Campaign optimization
- Pixel tracking setup
- Business verification
- Technical support
- Escalation requests

And categorize conversations as:
- **Solved**: User's task was completed
- **Needs human**: Requires human intervention
- **Missing info**: User didn't provide required information
- **Policy limitation**: Bot cannot perform requested action

## Troubleshooting

- **API errors**: Check your API key and rate limits
- **File parsing issues**: Use `--dry_run` to test file processing
- **Memory issues**: Use `--sample_limit` to process fewer files at once
- **Column detection**: The script tries to auto-detect column names, but may need adjustment for unusual formats
