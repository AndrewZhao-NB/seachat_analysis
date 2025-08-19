#!/usr/bin/env python3
import os, glob, json, time, math, textwrap, argparse, collections, re
import pandas as pd
# matplotlib removed - no charts needed
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# --------------- CONFIG ---------------
# Uses the Cooper internal GPT API.
# Set env vars:
#   COOPER_API_KEY=...   (optional; defaults to the one in the code)
#   COOPER_BASE_URL=...  (optional; defaults to the one in the code)
#   COOPER_MODEL=...     (optional; defaults to gpt-4o)
#
COOPER_MODEL = os.getenv("COOPER_MODEL", "gpt-4o")
COOPER_BASE_URL = os.getenv("COOPER_BASE_URL", "http://cooper.k8s.nb-prod.com/v1/chat/completions")
COOPER_API_KEY = os.getenv("COOPER_API_KEY", "nb-AAoDnr1JKoVz6WZgjucGRSo91c2mZa9EtYa9aOF91wPg1uw7W83utyKNGluOAy5L000")

MAX_TRANSCRIPT_CHARS = None   # no truncation - provide full conversation context
REQUESTS_PER_MINUTE = 500     # rate limiting (increased for much faster processing)
MAX_WORKERS = 10              # number of parallel API workers

# --------------- RATE LIMITER ---------------
class RateLimiter:
    def __init__(self, max_requests_per_minute):
        self.max_requests = max_requests_per_minute
        self.interval = 60.0 / max_requests_per_minute
        self.last_request_time = 0
        self.lock = threading.Lock()
        self.request_count = 0
        self.minute_start = time.time()
    
    def wait_if_needed(self):
        with self.lock:
            current_time = time.time()
            
            # Reset counter if a minute has passed
            if current_time - self.minute_start >= 60.0:
                self.request_count = 0
                self.minute_start = current_time
            
            # Check if we're at the limit
            if self.request_count >= self.max_requests:
                wait_time = 60.0 - (current_time - self.minute_start)
                if wait_time > 0:
                    print(f"  ⏳  Rate limit reached, waiting {wait_time:.1f}s...")
                    time.sleep(wait_time)
                    self.request_count = 0
                    self.minute_start = time.time()
            
            self.request_count += 1

# --------------- LLM CLIENT ---------------
import requests
def chat_complete(system, user, rate_limiter):
    rate_limiter.wait_if_needed()
    
    url = f"{COOPER_BASE_URL}"
    headers = {
        "Authorization": f"Bearer {COOPER_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": COOPER_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "max_tokens": 1000,
    }
    r = requests.post(url, headers=headers, json=body, timeout=120)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

# --------------- PROMPT ---------------
SYSTEM_PROMPT = """You are an analyst that classifies chatbot conversations.
Return STRICT JSON only (no commentary). Be concise, evidence-based, and avoid speculation.
"""

USER_PROMPT_TEMPLATE = """You are given a single conversation transcript between a user and a NewsBreak Ad Assistant chatbot.
Goal: analyze what the user was trying to accomplish, whether the bot solved it, and provide detailed analysis of failures.

CRITICAL: NEVER use generic responses like "none", "none-needed", or "no". Always provide specific, concrete, actionable information. If something doesn't apply, explain WHY it doesn't apply in specific terms.

EXAMPLES OF WHAT NOT TO DO:
❌ "specific_improvement_needed": "none-needed"
❌ "escalation_triggers": ["none"]
❌ "error_patterns": ["none"]

EXAMPLES OF WHAT TO DO INSTEAD:
✅ "specific_improvement_needed": "bot-handled-perfectly"
✅ "escalation_triggers": ["bot-solved-problem", "user-satisfied"]
✅ "error_patterns": ["system-functioning-perfectly", "no-technical-issues"]

Return STRICT JSON with this schema (do not add fields):
{{
  "topics": ["short, kebab-case tags"],
  "user_tasks_attempted": ["specific task the user wanted to complete"],
  "solved": true/false,
  "why_unsolved": ["detailed reason why the task failed"],
  "needs_human": true/false,
  "capabilities": ["what-the-bot-did-well"],
  "limitations": ["specific capabilities the bot lacks"],
  "failure_category": "missing-info|requires-human|feature-not-supported|bot-error|user-abandoned|incomplete-conversation|other",
  "missing_feature": "specific feature/functionality that the bot lacks (if feature-not-supported)",
  "feature_category": "account-management|billing|campaign-control|technical-support|integration|reporting|verification|other",
  "specific_improvement_needed": "concrete action item to fix this type of failure",
  "examples": [{{"speaker": "user|bot", "quote": "key quote showing the issue"}}, ... up to 2],
  "success_patterns": ["patterns that led to success if solved"],
  "demonstrated_skills": ["specific skills the bot showed"],
  "user_satisfaction_indicators": ["signs the user was satisfied if solved"],
  "conversation_flow": ["key conversation stages or transitions"],
  "escalation_triggers": ["what caused user to ask for human help"],
  "error_patterns": ["specific error messages or technical issues"],
  "user_emotion": "frustrated|satisfied|neutral|confused|grateful",
  "conversation_complexity": "simple|moderate|complex",
  "feature_priority_score": 1-5,
  "improvement_effort": "low|medium|high"
}}

Detailed Analysis Guidelines:
- "user_tasks_attempted": Be specific about what the user wanted (e.g., "reset password", "get refund", "change ad targeting"). If user never made a request, use ["no-user-request"].
- "why_unsolved": Explain exactly why it failed (e.g., "bot cannot access user account database", "bot lacks refund processing capability"). If user never made a request, use ["no-user-request-to-solve"].
- "failure_category": 
  * missing-info: User didn't provide required information
  * requires-human: Task needs human intervention (e.g., account verification, complex disputes)
  * feature-not-supported: Bot doesn't have this capability
  * bot-error: Bot made a mistake or gave wrong information
  * user-abandoned: User left before completion
  * incomplete-conversation: User never made a request or conversation was abandoned early
  * other: Doesn't fit above categories
- "missing_feature": When failure_category is "feature-not-supported", specify exactly what feature is missing (e.g., "password reset workflow", "refund processing system", "campaign modification API")
- "feature_category": Group missing features into categories:
  * account-management: User account operations (password reset, profile changes, access control)
  * billing: Payment, refunds, billing disputes, invoice access
  * campaign-control: Ad campaign creation, modification, targeting changes
  * technical-support: Bug reports, system issues, troubleshooting
  * integration: Third-party integrations, API access, webhook setup
  * reporting: Analytics, performance reports, data export
  * verification: Business verification, document processing, compliance checks
  * other: Doesn't fit above categories
- "specific_improvement_needed": Concrete action (e.g., "add form to collect business verification documents", "integrate with billing system API", "add password reset workflow"). If user never made a request, use "no-improvement-needed-user-abandoned". If no improvement is needed, explain WHY (e.g., "bot-handled-perfectly", "user-request-fulfilled", "conversation-successful"). NEVER use "none" or "none-needed" - always provide specific, actionable information or explain why no action is needed.
- "success_patterns": When solved=true, identify what worked well (e.g., "clear-step-by-step-guidance", "form-completion-workflow", "policy-explanation", "information-gathering"). If user never made a request, use ["bot-greeting-successful", "form-presentation-complete"].
- "demonstrated_skills": Specific skills the bot showed (e.g., "multi-step-instruction", "form-validation", "policy-clarification", "technical-troubleshooting"). If user never made a request, use ["greeting", "form-presentation", "template-rendering"].
- "user_satisfaction_indicators": Signs of user satisfaction (e.g., "user-thanked-bot", "user-confirmed-completion", "user-expressed-gratitude", "conversation-ended-positively"). If user never made a request, use ["conversation-initiated", "bot-ready-to-help"].
- "conversation_flow": Key stages in the conversation (e.g., "greeting", "problem-statement", "information-gathering", "solution-attempt", "resolution"). If user never made a request, use ["bot-greeting", "form-presentation", "user-abandoned"].
- "escalation_triggers": What caused escalation (e.g., "bot-cannot-access-system", "complex-technical-issue", "policy-question", "account-specific-problem"). If user never made a request, use ["user-abandoned-conversation", "no-escalation-needed"]. If no escalation occurred, explain WHY (e.g., ["bot-solved-problem", "user-satisfied", "conversation-completed-successfully"]). NEVER use "none" - always provide specific reason or explain why escalation wasn't needed.
- "error_patterns": Specific error messages or technical issues (e.g., "api-timeout", "permission-denied", "invalid-input", "system-unavailable"). If user never made a request, use ["no-errors-detected", "conversation-abandoned"]. If no errors occurred, explain WHY (e.g., ["system-functioning-perfectly", "all-requests-successful", "no-technical-issues"]). NEVER use "none" - always provide specific information or explain why no errors occurred.
- "user_emotion": Overall user emotional state (frustrated, satisfied, neutral, confused, grateful). If user never made a request, use "neutral".
- "conversation_complexity": How complex the conversation was (simple: 1-2 exchanges, moderate: 3-5 exchanges, complex: 6+ exchanges). If user never made a request, use "simple".
- "feature_priority_score": Rate missing features 1-5 (1=low impact, 5=critical blocker). If user never made a request, use 1.
- "improvement_effort": Estimate effort to implement (low: UI change, medium: API integration, high: new system). If user never made a request, use "low".

Transcript (UTC times, truncated if long):
----------------
{transcript}
----------------

FINAL REMINDER: NEVER use "none", "none-needed", or "no" in any field. Always provide specific, descriptive information or explain why something doesn't apply.
"""

# --------------- UTIL: PROCESS SINGLE FILE ---------------
def process_single_file(args):
    """Process a single CSV file and return the analysis result."""
    path, dry_run, rate_limiter = args
    base = os.path.basename(path)
    
    try:
        transcript = csv_to_transcript(path)
        if not transcript.strip():
            return {
                "file": base,
                "topics": ["empty-transcript"],
                "user_tasks_attempted": [],
                "solved": False,
                "why_unsolved": ["empty-transcript"],
                "needs_human": False,
                "capabilities": [],
                "examples": [],
                "failure_category": "other",
                "missing_feature": "no-missing-feature-empty-transcript",
                "feature_category": "no-feature-category-empty-transcript",
                "specific_improvement_needed": "no-improvement-needed-empty-transcript",
                "success_patterns": [],
                "demonstrated_skills": [],
                "user_satisfaction_indicators": [],
                "conversation_flow": [],
                "escalation_triggers": [],
                "error_patterns": [],
                "user_emotion": "neutral",
                "conversation_complexity": "simple",
                "feature_priority_score": 1,
                "improvement_effort": "low",
                "conversation_quality": "low-value",
                "filtered_reason": "empty-transcript"
            }
        
        # Check for incomplete conversations (no user input)
        if is_incomplete_conversation(transcript):
            return {
                "file": base,
                "topics": ["incomplete-conversation"],
                "user_tasks_attempted": ["no-user-request"],
                "solved": False,  # Not a success - no problem was solved
                "why_unsolved": ["no-user-request-to-solve"],
                "needs_human": False,
                "capabilities": ["greeting", "form-presentation"],
                "limitations": [],
                "examples": [],
                "failure_category": "incomplete-conversation",
                "missing_feature": "no-missing-feature-incomplete-conversation",
                "feature_category": "no-feature-category-incomplete-conversation",
                "specific_improvement_needed": "no-improvement-needed-user-abandoned",
                "success_patterns": ["bot-greeting-successful", "form-presentation-complete"],
                "demonstrated_skills": ["greeting", "form-presentation", "template-rendering"],
                "user_satisfaction_indicators": ["conversation-initiated", "bot-ready-to-help"],
                "conversation_flow": ["bot-greeting", "form-presentation", "user-abandoned"],
                "escalation_triggers": ["user-abandoned-conversation", "no-escalation-needed"],
                "error_patterns": ["no-errors-detected", "conversation-abandoned"],
                "user_emotion": "neutral",
                "conversation_complexity": "simple",
                "feature_priority_score": 1,
                "improvement_effort": "low",
                "conversation_quality": "low-value",
                "filtered_reason": "incomplete-conversation-no-user-input"
            }
        
        # Check for low-value conversations (just greetings, cancellations, etc.)
        if is_low_value_conversation(transcript):
            return {
                "file": base,
                "topics": ["low-value-conversation"],
                "user_tasks_attempted": ["minimal-interaction"],
                "solved": False,  # Not a success - no problem was solved
                "why_unsolved": ["no-substantial-request"],
                "needs_human": False,
                "capabilities": ["greeting", "basic-interaction"],
                "limitations": [],
                "examples": [],
                "failure_category": "low-value-conversation",
                "missing_feature": "no-missing-feature-low-value",
                "feature_category": "no-feature-category-low-value",
                "specific_improvement_needed": "no-improvement-needed-low-value",
                "success_patterns": ["bot-greeting-successful", "basic-interaction-complete"],
                "demonstrated_skills": ["greeting", "basic-interaction"],
                "user_satisfaction_indicators": ["conversation-initiated", "minimal-interaction"],
                "conversation_flow": ["bot-greeting", "user-minimal-response"],
                "escalation_triggers": ["no-escalation-needed", "minimal-interaction"],
                "error_patterns": ["no-errors-detected", "low-value-conversation"],
                "user_emotion": "neutral",
                "conversation_complexity": "simple",
                "feature_priority_score": 1,
                "improvement_effort": "low",
                "conversation_quality": "low-value",
                "filtered_reason": "low-value-2-or-fewer-user-messages"
            }

        if dry_run:
            return {
                "file": base,
                "topics": ["unknown"],
                "user_tasks_attempted": [],
                "solved": False,
                "why_unsolved": ["dry-run-no-llm"],
                "needs_human": False,
                "capabilities": [],
                "examples": [],
                "failure_category": "other",
                "missing_feature": "no-missing-feature-dry-run",
                "feature_category": "no-feature-category-dry-run",
                "specific_improvement_needed": "no-improvement-needed-dry-run",
                "success_patterns": [],
                "demonstrated_skills": [],
                "user_satisfaction_indicators": [],
                "conversation_flow": [],
                "escalation_triggers": [],
                "error_patterns": [],
                "user_emotion": "neutral",
                "conversation_complexity": "simple",
                "feature_priority_score": 1,
                "improvement_effort": "low",
                "conversation_quality": "unknown",
                "filtered_reason": "dry-run"
            }
        else:
            prompt = USER_PROMPT_TEMPLATE.format(transcript=transcript)
            try:
                content = chat_complete(SYSTEM_PROMPT, prompt, rate_limiter)
                obj = json.loads(content)
                result = {"file": base, **obj, "conversation_quality": "high-value", "filtered_reason": "none"}
                return result
            except Exception as e:
                return {
                    "file": base,
                    "topics": ["parse-error"],
                    "user_tasks_attempted": [],
                    "solved": False,
                    "why_unsolved": [f"exception: {type(e).__name__}"],
                    "needs_human": False,
                    "capabilities": [],
                    "limitations": [],
                    "examples": [],
                    "failure_category": "other",
                    "missing_feature": "no-missing-feature-parse-error",
                    "feature_category": "no-feature-category-parse-error",
                    "specific_improvement_needed": "no-improvement-needed-parse-error",
                    "success_patterns": [],
                    "demonstrated_skills": [],
                    "user_satisfaction_indicators": [],
                    "conversation_flow": [],
                    "escalation_triggers": [],
                    "error_patterns": [],
                    "user_emotion": "neutral",
                    "conversation_complexity": "simple",
                    "feature_priority_score": 1,
                    "improvement_effort": "low",
                    "conversation_quality": "error",
                    "filtered_reason": "parse-error"
                }
    except Exception as e:
        return {
            "file": base,
            "topics": ["file-error"],
            "user_tasks_attempted": [],
            "count": 0,
            "solved": False,
            "why_unsolved": [f"file-error: {type(e).__name__}"],
            "needs_human": False,
            "capabilities": [],
            "examples": [],
            "failure_category": "other",
            "missing_feature": "none",
            "feature_category": "none",
            "specific_improvement_needed": "none",
            "success_patterns": [],
            "demonstrated_skills": [],
            "user_satisfaction_indicators": [],
            "conversation_flow": [],
            "escalation_triggers": [],
            "error_patterns": [],
            "user_emotion": "neutral",
            "conversation_complexity": "simple",
            "feature_priority_score": 1,
            "improvement_effort": "low",
            "conversation_quality": "error",
            "filtered_reason": "file-error"
        }

# Feature consolidation moved to generate_executive_report.py

# categorize_technical_requirements function removed - no longer needed

# --------------- UTIL: DETECT INCOMPLETE CONVERSATIONS ---------------
def is_incomplete_conversation(transcript):
    """Detect if a conversation is incomplete (no user input)."""
    lines = transcript.split('\n')
    user_lines = [line for line in lines if 'user:' in line.lower() and line.strip()]
    # If no user lines or only empty user lines, it's incomplete
    return len(user_lines) == 0

def is_low_value_conversation(transcript):
    """Check if conversation has low analytical value based on user message count and content."""
    lines = transcript.split('\n')
    user_messages = []
    
    for line in lines:
        line = line.strip()
        if line and 'user:' in line.lower():
            # Extract just the message part after "user:"
            msg_part = line.split('user:', 1)[1].strip().lower()
            user_messages.append(msg_part)
    
    # HARD THRESHOLD: If user has 2 or fewer messages, filter out
    if len(user_messages) <= 2:
        return True
    
    # Additional content filtering for conversations with more than 2 messages
    meaningful_content = False
    for msg in user_messages:
        # Skip if it's just "cancel", "no", "stop"
        if msg in ['cancel', 'no', 'stop', 'quit', 'exit']:
            continue
        
        # Skip if it's just a form submission without context
        if msg == 'the user completes the submission of the form':
            continue
        
        # Skip if it's just a greeting
        if len(msg) < 20 and any(word in msg for word in ['hi', 'hello', 'hey', 'good morning', 'good afternoon']):
            continue
        
        # If we get here, there's meaningful content
        meaningful_content = True
        break
    
    return not meaningful_content

# --------------- UTIL: BUILD TRANSCRIPTS ---------------
def csv_to_transcript(csv_path):
    df = pd.read_csv(csv_path)
    # Try to accommodate column naming differences gracefully
    col_time = next((c for c in df.columns if "Time" in c), None)
    col_sender = next((c for c in df.columns if c.lower().startswith("sender type")), None)
    col_msg = next((c for c in df.columns if c.lower() == "message"), None)

    if col_time is None or col_sender is None or col_msg is None:
        # fallback: just join any text-looking columns
        text_cols = [c for c in df.columns if df[c].dtype == object]
        transcript = "\n".join(
            " | ".join(str(x) for x in row[text_cols].tolist())
            for _, row in df.iterrows()
        )
        if MAX_TRANSCRIPT_CHARS:
            return transcript[:MAX_TRANSCRIPT_CHARS]
        return transcript

    def normalize_sender(v):
        v = str(v).strip().lower()
        if v in ("web","user","customer","client"): return "user"
        if v in ("bot","assistant","agent","system"): return "bot"
        return v or "user"

    lines = []
    for _, row in df.iterrows():
        t = str(row[col_time]) if col_time in row else ""
        spk = normalize_sender(row[col_sender])
        msg = str(row[col_msg]) if col_msg in row and not (pd.isna(row[col_msg])) else ""
        if not msg: 
            continue
        # compact timestamp
        t = re.sub(r"\.\d+$","",t)
        lines.append(f"[{t}] {spk}: {msg}")

    transcript = "\n".join(lines)
    if MAX_TRANSCRIPT_CHARS:
        return transcript[:MAX_TRANSCRIPT_CHARS]
    return transcript

# --------------- MAIN ---------------
def main(input_glob, outdir, sample_limit=None, dry_run=False):
    os.makedirs(outdir, exist_ok=True)
    csv_files = sorted(glob.glob(input_glob))
    if sample_limit:
        csv_files = csv_files[:sample_limit]

    per_chat = []
    errs = 0
    
    # Initialize rate limiter
    rate_limiter = RateLimiter(REQUESTS_PER_MINUTE)
    start_time = time.time()  # Track total processing time

    if dry_run:
        # Sequential processing for dry run
        for i, path in enumerate(csv_files, 1):
            base = os.path.basename(path)
            print(f"Processing {i}/{len(csv_files)}: {base}")
            
            result = process_single_file((path, dry_run, rate_limiter))
            
            # Filter out low-value conversations completely
            if result.get("conversation_quality") == "low-value":
                reason = result.get('filtered_reason', 'unknown')
                if '2-or-fewer-user-messages' in reason:
                    print(f"  🚫  Filtered out: {base} (≤2 user messages)")
                else:
                    print(f"  🚫  Filtered out: {base} ({reason})")
                continue  # Skip this conversation entirely
            
            per_chat.append(result)
            
            if i % 10 == 0 or i == len(csv_files):
                filtered_count = i - len(per_chat)
                print(f"\n📊 Progress: {i}/{len(csv_files)} files processed ({i/len(csv_files)*100:.1f}%)")
                print(f"   🚫 Filtered out: {filtered_count} low-value conversations (≤2 user messages)")
                print(f"   ✅ High-value conversations: {len(per_chat)}")
                print()
    else:
        # Parallel processing for real API calls
        print(f"🚀 Starting parallel processing with {MAX_WORKERS} workers...")
        print(f"📊 Rate limit: {REQUESTS_PER_MINUTE} requests per minute")
        
        # Prepare arguments for parallel processing
        args_list = [(path, dry_run, rate_limiter) for path in csv_files]
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            print(f"  📤 Submitting {len(args_list)} tasks to {MAX_WORKERS} workers...")
            
            # Submit all tasks
            future_to_path = {executor.submit(process_single_file, args): args[0] for args in args_list}
            print(f"  ✅ All tasks submitted! Workers are now processing in parallel...")
            
            # Process completed tasks
            completed = 0
            start_time = time.time()
            for future in as_completed(future_to_path):
                path = future_to_path[future]
                base = os.path.basename(path)
                completed += 1
                
                try:
                    result = future.result()
                    
                    # Filter out low-value conversations completely
                    if result.get("conversation_quality") == "low-value":
                        reason = result.get('filtered_reason', 'unknown')
                        if '2-or-fewer-user-messages' in reason:
                            print(f"  🚫  Filtered out: {base} (≤2 user messages)")
                        else:
                            print(f"  🚫  Filtered out: {base} ({reason})")
                        continue  # Skip this conversation entirely
                    
                    per_chat.append(result)
                    
                    # Check for errors
                    if "parse-error" in result.get("topics", []) or "file-error" in result.get("topics", []):
                        errs += 1
                        print(f"  ❌  Error processing {base}")
                    else:
                        print(f"  ✅  Completed {base}")
                    
                    # Progress update
                    if completed % 10 == 0 or completed == len(csv_files):
                        elapsed = time.time() - start_time
                        rate = completed / elapsed if elapsed > 0 else 0
                        eta = (len(csv_files) - completed) / rate if rate > 0 else 0
                        filtered_count = len(csv_files) - len(per_chat) - errs
                        print(f"\n📊 Progress: {completed}/{len(csv_files)} files processed ({completed/len(csv_files)*100:.1f}%)")
                        print(f"   🚫 Filtered out: {filtered_count} low-value conversations (≤2 user messages)")
                        print(f"   🚨 Errors so far: {errs}")
                        print(f"   ⏱️  Processing rate: {rate:.1f} files/second")
                        print(f"   ⏳  Estimated time remaining: {eta:.1f} seconds")
                        print()
                        
                except Exception as e:
                    errs += 1
                    print(f"  ❌  Exception processing {base}: {e}")
                    # Add error result
                    # Don't add processing errors to results - they're not useful for analysis
                    print(f"  ❌  Processing error for {base}: {e}")
                    continue

    if not dry_run:
        total_time = time.time() - start_time
        avg_time_per_file = total_time / len(csv_files) if csv_files else 0
        print(f"\n🚀 Parallel Processing Summary:")
        print(f"   📊 Total files: {len(csv_files)}")
        print(f"   ⏱️  Total time: {total_time:.1f} seconds")
        print(f"   📈 Average time per file: {avg_time_per_file:.2f} seconds")
        print(f"   🔧 Workers used: {MAX_WORKERS}")
        print(f"   📊 Files per second: {len(csv_files)/total_time:.2f}")
        print()
    
    print(f"\n🎉 Processing complete! Starting analysis...")
    
    # Run summary step
    print(f"\n📊 Running summary analysis...")
    try:
        from summarize_results import generate_summary_report
        summary_stats = generate_summary_report(per_chat, outdir)
        print(f"  ✅ Summary analysis complete!")
    except ImportError:
        print(f"  ⚠️  Summary module not found, skipping summary step")
        summary_stats = None
    except Exception as e:
        print(f"  ❌ Summary analysis failed: {e}")
        summary_stats = None
    
    # Save raw data (needed for HTML report)
    raw_path = os.path.join(outdir, "per_chat.jsonl")
    with open(raw_path, "w", encoding="utf-8") as f:
        for r in per_chat:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  ✅  Created raw data: {raw_path}")

    # Problem-to-conversation mappings for clickable items (ONLY what's needed for HTML)
    problem_conversation_mapping = {
        'missing_features': {},
        'api_problems': {},
        'ui_problems': {},
        'integration_problems': {},
        'successful_capabilities': {}
    }

    # Process conversations to build mapping
    for r in per_chat:
        # Map missing features to conversations
        if r.get("failure_category") == "feature-not-supported":
            missing_feature = r.get("missing_feature", "unknown-feature")
            if missing_feature and missing_feature != "unknown-feature":
                if missing_feature not in problem_conversation_mapping['missing_features']:
                    problem_conversation_mapping['missing_features'][missing_feature] = []
                problem_conversation_mapping['missing_features'][missing_feature].append(r['file'])
                
                # Categorize by problem type
                if any(term in missing_feature.lower() for term in ['api', 'access', 'schema', 'system', 'database']):
                    if missing_feature not in problem_conversation_mapping['api_problems']:
                        problem_conversation_mapping['api_problems'][missing_feature] = []
                    problem_conversation_mapping['api_problems'][missing_feature].append(r['file'])
                
                if any(term in missing_feature.lower() for term in ['ui', 'interface', 'workflow', 'form', 'button', 'desktop']):
                    if missing_feature not in problem_conversation_mapping['ui_problems']:
                        problem_conversation_mapping['ui_problems'][missing_feature] = []
                    problem_conversation_mapping['ui_problems'][missing_feature].append(r['file'])
                
                if any(term in missing_feature.lower() for term in ['integration', 'clickmagick', 'weebly', 'wix', 'everflow']):
                    if missing_feature not in problem_conversation_mapping['integration_problems']:
                        problem_conversation_mapping['integration_problems'][missing_feature] = []
                    problem_conversation_mapping['integration_problems'][missing_feature].append(r['file'])
        
        # Map improvement needs to conversations
        improvement = r.get("specific_improvement_needed", "no-improvement-needed")
        if improvement and improvement != "no-improvement-needed":
            if improvement not in problem_conversation_mapping['missing_features']:
                problem_conversation_mapping['missing_features'][improvement] = []
            problem_conversation_mapping['missing_features'][improvement].append(r['file'])
            
            # Also categorize by problem type
            if any(term in improvement.lower() for term in ['api', 'access', 'schema', 'system', 'database']):
                if improvement not in problem_conversation_mapping['api_problems']:
                    problem_conversation_mapping['api_problems'][improvement] = []
                problem_conversation_mapping['api_problems'][improvement].append(r['file'])
            
            if any(term in improvement.lower() for term in ['ui', 'interface', 'workflow', 'form', 'button']):
                if improvement not in problem_conversation_mapping['ui_problems']:
                    problem_conversation_mapping['ui_problems'][improvement] = []
                problem_conversation_mapping['ui_problems'][improvement].append(r['file'])
            
            if any(term in improvement.lower() for term in ['integration', 'clickmagick', 'weebly', 'wix', 'everflow']):
                if improvement not in problem_conversation_mapping['integration_problems']:
                    problem_conversation_mapping['integration_problems'][improvement] = []
                problem_conversation_mapping['integration_problems'][improvement].append(r['file'])
        
        # Map successful capabilities to conversations
        if r.get("solved", False):
            for skill in r.get("demonstrated_skills", []):
                if skill:
                    if skill not in problem_conversation_mapping['successful_capabilities']:
                        problem_conversation_mapping['successful_capabilities'][skill] = []
                    problem_conversation_mapping['successful_capabilities'][skill].append(r['file'])

    # Save problem-to-conversation mapping (needed for HTML report)
    mapping_path = os.path.join(outdir, "problem_conversation_mapping.json")
    with open(mapping_path, "w", encoding="utf-8") as f:
        json.dump(problem_conversation_mapping, f, ensure_ascii=False, indent=2)
    print(f"  ✅  Created problem mapping: {mapping_path}")

    total_files = len(csv_files)
    filtered_count = total_files - len(per_chat) - errs
    
    print(f"\n🎯 Analysis Complete!")
    print(f"📊 Summary:")
    print(f"   📁 Total files processed: {total_files}")
    print(f"   🚫 Low-value conversations filtered: {filtered_count}")
    print(f"   🚨 Processing errors: {errs}")
    print(f"   ✅ High-value conversations analyzed: {len(per_chat)}")
    print(f"📁 Raw data: {raw_path}")
    print(f"📊 Problem mapping: {mapping_path}")
    print(f"💡 Run 'python generate_executive_report.py --analysis_dir {outdir} --output report.html --short' to generate HTML report")
    
    if errs > 0:
        print(f"\n⚠️  Warning: {errs} files had errors during processing")
    if filtered_count > 0:
        print(f"\n🚫 Note: {filtered_count} low-value conversations were filtered out (≤2 user messages, greetings, cancellations, etc.)")
    if len(per_chat) > 0:
        print(f"\n✅ {len(per_chat)} high-value conversations analyzed successfully!")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input_glob", default="Bot_714b4955-90a2-4693-9380-a28dffee2e3a_Year_2025_4a86f154be3a4925a510e33bdda399b3 (3)/*.csv", help="e.g., data/*.csv")
    ap.add_argument("--outdir", default="analysis_out")
    ap.add_argument("--sample_limit", type=int, default=None, help="limit number of files")
    ap.add_argument("--dry_run", action="store_true", help="skip API calls (for quick test)")
    ap.add_argument("--workers", type=int, default=10, help="number of parallel workers (default: 10)")

    args = ap.parse_args()
    
    # Update MAX_WORKERS
    MAX_WORKERS = args.workers
    
    main(args.input_glob, args.outdir, args.sample_limit, args.dry_run)
