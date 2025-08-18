#!/usr/bin/env python3
import os, glob, json, time, math, textwrap, argparse, collections, re
import pandas as pd
import matplotlib.pyplot as plt
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
            }
        
        # Check for incomplete conversations (no user input)
        if is_incomplete_conversation(transcript):
            return {
                "file": base,
                "topics": ["incomplete-conversation"],
                "user_tasks_attempted": ["no-user-request"],
                "solved": True,  # Not a failure - no request to solve
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
            }
        else:
            prompt = USER_PROMPT_TEMPLATE.format(transcript=transcript)
            try:
                content = chat_complete(SYSTEM_PROMPT, prompt, rate_limiter)
                obj = json.loads(content)
                result = {"file": base, **obj}
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
                }
    except Exception as e:
        return {
            "file": base,
            "topics": ["file-error"],
            "user_tasks_attempted": [],
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
        }

# --------------- UTIL: FEATURE CONSOLIDATION ---------------
def consolidate_similar_features(feature_name):
    """Consolidate similar features into meaningful categories."""
    feature_lower = feature_name.lower()
    
    # Cancellation-related features
    if any(term in feature_lower for term in ['cancellation', 'cancel']):
        return 'cancellation-processing-system'
    
    # Integration-related features
    if any(term in feature_lower for term in ['integration', 'clickmagick', 'weebly', 'wix', 'everflow']):
        return 'third-party-integration-support'
    
    # API and system access
    if any(term in feature_lower for term in ['api', 'access', 'schema', 'system']):
        return 'api-system-access'
    
    # UI/UX features
    if any(term in feature_lower for term in ['ui', 'interface', 'workflow', 'form', 'desktop']):
        return 'ui-ux-enhancements'
    
    # Live support features
    if any(term in feature_lower for term in ['live', 'agent', 'human', 'support']):
        return 'live-support-features'
    
    # Document and billing
    if any(term in feature_lower for term in ['invoice', 'billing', 'document', 'ticket']):
        return 'document-billing-system'
    
    # Ad management
    if any(term in feature_lower for term in ['ad', 'campaign', 'event', 'approval']):
        return 'ad-management-features'
    
    # Account management
    if any(term in feature_lower for term in ['account', 'verification', 'permission']):
        return 'account-management-features'
    
    return feature_name

def categorize_technical_requirements(improvement, technical_req_counts, api_counts, ui_counts, doc_counts):
    """Categorize technical requirements by implementation type."""
    improvement_lower = improvement.lower()
    
    # Count overall technical requirements
    technical_req_counts[improvement] += 1
    
    # API Integration requirements
    if any(term in improvement_lower for term in ['api', 'integrate', 'system', 'database']):
        api_counts[improvement] += 1
    
    # UI/Workflow requirements
    if any(term in improvement_lower for term in ['ui', 'interface', 'workflow', 'form', 'button']):
        ui_counts[improvement] += 1
    
    # Documentation/Knowledge requirements
    if any(term in improvement_lower for term in ['knowledge', 'guide', 'instruction', 'documentation', 'guide']):
        doc_counts[improvement] += 1

# --------------- UTIL: DETECT INCOMPLETE CONVERSATIONS ---------------
def is_incomplete_conversation(transcript):
    """Detect if a conversation is incomplete (no user input)."""
    lines = transcript.split('\n')
    user_lines = [line for line in lines if 'user:' in line.lower() and line.strip()]
    # If no user lines or only empty user lines, it's incomplete
    return len(user_lines) == 0

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
def main(input_glob, outdir, sample_limit=None, dry_run=False, no_executive_report=False):
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
            per_chat.append(result)
            
            if i % 10 == 0 or i == len(csv_files):
                print(f"\n📊 Progress: {i}/{len(csv_files)} files processed ({i/len(csv_files)*100:.1f}%)")
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
                        print(f"\n📊 Progress: {completed}/{len(csv_files)} files processed ({completed/len(csv_files)*100:.1f}%)")
                        print(f"   🚨 Errors so far: {errs}")
                        print(f"   ⏱️  Processing rate: {rate:.1f} files/second")
                        print(f"   ⏳  Estimated time remaining: {eta:.1f} seconds")
                        print()
                        
                except Exception as e:
                    errs += 1
                    print(f"  ❌  Exception processing {base}: {e}")
                    # Add error result
                    per_chat.append({
                        "file": base,
                        "topics": ["processing-error"],
                        "user_tasks_attempted": [],
                        "solved": False,
                        "why_unsolved": [f"processing-error: {type(e).__name__}"],
                        "needs_human": False,
                        "capabilities": [],
                        "limitations": [],
                        "examples": [],
                        "failure_category": "other",
                        "missing_feature": "no-missing-feature-processing-error",
                        "feature_category": "no-feature-category-processing-error",
                        "specific_improvement_needed": "no-improvement-needed-processing-error",
                    })

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
    
    # Save raw
    raw_path = os.path.join(outdir, "per_chat.jsonl")
    with open(raw_path, "w", encoding="utf-8") as f:
        for r in per_chat:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # Flatten to rows
    rows = []
    for r in per_chat:
        # Handle missing or None values safely
        topics = r.get("topics", []) or []
        user_tasks = r.get("user_tasks_attempted", []) or []
        why_unsolved = r.get("why_unsolved", []) or []
        capabilities = r.get("capabilities", []) or []
        limitations = r.get("limitations", []) or []
        
        rows.append({
            "file": r["file"],
            "topics": ",".join(str(t) for t in topics if t is not None),
            "user_tasks": "; ".join(str(t) for t in user_tasks if t is not None),
            "solved": bool(r.get("solved", False)),
            "needs_human": bool(r.get("needs_human", False)),
            "failure_category": str(r.get("failure_category", "unknown") or "unknown"),
            "missing_feature": str(r.get("missing_feature", "no-missing-feature") or "no-missing-feature"),
            "feature_category": str(r.get("feature_category", "no-feature-category") or "no-feature-category"),
            "why_unsolved": "; ".join(str(w) for w in why_unsolved if w is not None),
            "improvement_needed": str(r.get("specific_improvement_needed", "no-improvement-needed") or "no-improvement-needed"),
            "capabilities": "; ".join(str(c) for c in capabilities if c is not None),
            "success_patterns": "; ".join(str(s) for s in r.get("success_patterns", []) if s is not None),
            "demonstrated_skills": "; ".join(str(s) for s in r.get("demonstrated_skills", []) if s is not None),
            "user_satisfaction_indicators": "; ".join(str(s) for s in r.get("user_satisfaction_indicators", []) if s is not None),
            "conversation_flow": "; ".join(str(f) for f in r.get("conversation_flow", []) if f is not None),
            "escalation_triggers": "; ".join(str(e) for e in r.get("escalation_triggers", []) if e is not None),
            "error_patterns": "; ".join(str(e) for e in r.get("error_patterns", []) if e is not None),
            "user_emotion": str(r.get("user_emotion", "neutral") or "neutral"),
            "conversation_complexity": str(r.get("conversation_complexity", "simple") or "simple"),
            "feature_priority_score": int(r.get("feature_priority_score", 1) or 1),
            "improvement_effort": str(r.get("improvement_effort", "low") or "low"),
        })
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(outdir, "summary.csv"), index=False)
    print(f"  ✅  Created summary CSV with {len(rows)} rows")

    # Topic stats
    topic_counts = collections.Counter()
    topic_solved = collections.Counter()
    reason_counts = collections.Counter()
    failure_category_counts = collections.Counter()
    improvement_needed_counts = collections.Counter()
    missing_feature_counts = collections.Counter()
    feature_category_counts = collections.Counter()
    
    # Enhanced analysis counters for technical details
    technical_requirement_counts = collections.Counter()
    api_integration_counts = collections.Counter()
    ui_workflow_counts = collections.Counter()
    documentation_gap_counts = collections.Counter()

    # Initialize success analysis counters
    success_pattern_counts = collections.Counter()
    demonstrated_skills_counts = collections.Counter()
    user_satisfaction_counts = collections.Counter()
    
    # Initialize enhanced analysis counters
    conversation_flow_counts = collections.Counter()
    escalation_trigger_counts = collections.Counter()
    error_pattern_counts = collections.Counter()
    user_emotion_counts = collections.Counter()
    conversation_complexity_counts = collections.Counter()
    feature_priority_counts = collections.Counter()
    improvement_effort_counts = collections.Counter()
    
    for r in per_chat:
        topics = r.get("topics", []) or ["unlabeled"]
        for t in topics:
            topic_counts[t] += 1
            if r.get("solved", False):
                topic_solved[t] += 1
        
        for reason in r.get("why_unsolved", []):
            reason_counts[reason] += 1
        
        # Count failure categories
        failure_cat = r.get("failure_category", "unknown")
        if failure_cat is None:
            failure_cat = "unknown"
        failure_category_counts[failure_cat] += 1
        
        # Count improvement needs
        improvement = r.get("specific_improvement_needed", "no-improvement-needed")
        if improvement is None or improvement == "":
            improvement = "no-improvement-needed"
        if improvement != "no-improvement-needed":
            improvement_needed_counts[improvement] += 1
        
        # Count missing features (for feature-not-supported failures)
        if r.get("failure_category") == "feature-not-supported":
            missing_feature = r.get("missing_feature", "unknown-feature")
            if missing_feature and missing_feature != "unknown-feature":
                # Consolidate similar features
                consolidated_feature = consolidate_similar_features(missing_feature)
                missing_feature_counts[consolidated_feature] += 1
            
            feature_cat = r.get("feature_category", "other")
            if feature_cat:
                feature_category_counts[feature_cat] += 1
        
        # Analyze technical requirements from improvement needs
        improvement = r.get("specific_improvement_needed", "no-improvement-needed")
        if improvement and improvement != "no-improvement-needed":
            # Categorize technical requirements
            categorize_technical_requirements(improvement, technical_requirement_counts, 
                                           api_integration_counts, ui_workflow_counts, 
                                           documentation_gap_counts)
        
        # Count success patterns for solved conversations
        if r.get("solved", False):
            for pattern in r.get("success_patterns", []):
                if pattern:
                    success_pattern_counts[pattern] += 1
            
            for skill in r.get("demonstrated_skills", []):
                if skill:
                    demonstrated_skills_counts[skill] += 1
            
            for indicator in r.get("user_satisfaction_indicators", []):
                if indicator:
                    user_satisfaction_counts[indicator] += 1
        
        # Count enhanced analysis fields
        for flow in r.get("conversation_flow", []):
            if flow:
                conversation_flow_counts[flow] += 1
        
        for trigger in r.get("escalation_triggers", []):
            if trigger:
                escalation_trigger_counts[trigger] += 1
        
        for error in r.get("error_patterns", []):
            if error:
                error_pattern_counts[error] += 1
        
        emotion = r.get("user_emotion", "neutral")
        if emotion:
            user_emotion_counts[emotion] += 1
        
        complexity = r.get("conversation_complexity", "simple")
        if complexity:
            conversation_complexity_counts[complexity] += 1
        
        priority = r.get("feature_priority_score", 1)
        if priority:
            feature_priority_counts[priority] += 1
        
        effort = r.get("improvement_effort", "low")
        if effort:
            improvement_effort_counts[effort] += 1

    topic_stats = []
    for t, n in topic_counts.most_common():
        s = topic_solved[t]
        rate = (s / n) if n else 0.0
        topic_stats.append({"topic": t, "count": n, "solved": s, "solve_rate": round(rate, 3)})
    pd.DataFrame(topic_stats).to_csv(os.path.join(outdir, "topic_stats.csv"), index=False)

    pd.DataFrame(
        [{"reason": r, "count": c} for r, c in reason_counts.most_common()]
    ).to_csv(os.path.join(outdir, "reasons.csv"), index=False)

    # Failure category analysis
    failure_cat_data = [{"failure_category": str(f), "count": c} for f, c in failure_category_counts.most_common() if f is not None]
    pd.DataFrame(failure_cat_data).to_csv(os.path.join(outdir, "failure_categories.csv"), index=False)
    print(f"  ✅  Created failure categories CSV with {len(failure_cat_data)} categories")

    # Improvement needs analysis
    improvement_data = [{"improvement": str(i), "count": c} for i, c in improvement_needed_counts.most_common() if i is not None]
    pd.DataFrame(improvement_data).to_csv(os.path.join(outdir, "improvement_needs.csv"), index=False)
    print(f"  ✅  Created improvement needs CSV with {len(improvement_data)} improvements")

    # Missing features analysis
    missing_feature_data = [{"missing_feature": str(f), "count": c} for f, c in missing_feature_counts.most_common() if f is not None]
    pd.DataFrame(missing_feature_data).to_csv(os.path.join(outdir, "missing_features.csv"), index=False)
    print(f"  ✅  Created missing features CSV with {len(missing_feature_data)} features")

    # Feature categories analysis
    feature_cat_data = [{"feature_category": str(c), "count": count} for c, count in feature_category_counts.most_common() if c is not None]
    pd.DataFrame(feature_cat_data).to_csv(os.path.join(outdir, "feature_categories.csv"), index=False)
    print(f"  ✅  Created feature categories CSV with {len(feature_cat_data)} categories")
    
    # Success patterns analysis
    if success_pattern_counts:
        success_pattern_data = [{"success_pattern": str(p), "count": c} for p, c in success_pattern_counts.most_common() if p is not None]
        pd.DataFrame(success_pattern_data).to_csv(os.path.join(outdir, "success_patterns.csv"), index=False)
        print(f"  ✅  Created success patterns CSV with {len(success_pattern_data)} patterns")
    
    # Demonstrated skills analysis
    if demonstrated_skills_counts:
        skills_data = [{"demonstrated_skill": str(s), "count": c} for s, c in demonstrated_skills_counts.most_common() if s is not None]
        pd.DataFrame(skills_data).to_csv(os.path.join(outdir, "demonstrated_skills.csv"), index=False)
        print(f"  ✅  Created demonstrated skills CSV with {len(skills_data)} skills")
    
    # User satisfaction analysis
    if user_satisfaction_counts:
        satisfaction_data = [{"satisfaction_indicator": str(i), "count": c} for i, c in user_satisfaction_counts.most_common() if i is not None]
        pd.DataFrame(satisfaction_data).to_csv(os.path.join(outdir, "user_satisfaction.csv"), index=False)
        print(f"  ✅  Created user satisfaction CSV with {len(satisfaction_data)} indicators")
    
    # Enhanced analysis CSVs
    if conversation_flow_counts:
        flow_data = [{"conversation_flow": str(f), "count": c} for f, c in conversation_flow_counts.most_common() if f is not None]
        pd.DataFrame(flow_data).to_csv(os.path.join(outdir, "conversation_flows.csv"), index=False)
        print(f"  ✅  Created conversation flows CSV with {len(flow_data)} flows")
    
    if escalation_trigger_counts:
        trigger_data = [{"escalation_trigger": str(t), "count": c} for t, c in escalation_trigger_counts.most_common() if t is not None]
        pd.DataFrame(trigger_data).to_csv(os.path.join(outdir, "escalation_triggers.csv"), index=False)
        print(f"  ✅  Created escalation triggers CSV with {len(trigger_data)} triggers")
    
    if error_pattern_counts:
        error_data = [{"error_pattern": str(e), "count": c} for e, c in error_pattern_counts.most_common() if e is not None]
        pd.DataFrame(error_data).to_csv(os.path.join(outdir, "error_patterns.csv"), index=False)
        print(f"  ✅  Created error patterns CSV with {len(error_data)} patterns")
    
    if user_emotion_counts:
        emotion_data = [{"user_emotion": str(e), "count": c} for e, c in user_emotion_counts.most_common() if e is not None]
        pd.DataFrame(emotion_data).to_csv(os.path.join(outdir, "user_emotions.csv"), index=False)
        print(f"  ✅  Created user emotions CSV with {len(emotion_data)} emotions")
    
    if conversation_complexity_counts:
        complexity_data = [{"conversation_complexity": str(c), "count": count} for c, count in conversation_complexity_counts.most_common() if c is not None]
        pd.DataFrame(complexity_data).to_csv(os.path.join(outdir, "conversation_complexity.csv"), index=False)
        print(f"  ✅  Created conversation complexity CSV with {len(complexity_data)} complexity levels")
    
    if feature_priority_counts:
        priority_data = [{"feature_priority": str(p), "count": c} for p, c in feature_priority_counts.most_common() if p is not None]
        pd.DataFrame(priority_data).to_csv(os.path.join(outdir, "feature_priorities.csv"), index=False)
        print(f"  ✅  Created feature priorities CSV with {len(priority_data)} priority levels")
    
    if improvement_effort_counts:
        effort_data = [{"improvement_effort": str(e), "count": c} for e, c in improvement_effort_counts.most_common() if e is not None]
        pd.DataFrame(effort_data).to_csv(os.path.join(outdir, "improvement_efforts.csv"), index=False)
        print(f"  ✅  Created improvement efforts CSV with {len(effort_data)} effort levels")
    
    # Enhanced technical analysis CSVs
    if technical_requirement_counts:
        tech_req_data = [{"technical_requirement": str(r), "count": c} for r, c in technical_requirement_counts.most_common() if r is not None]
        pd.DataFrame(tech_req_data).to_csv(os.path.join(outdir, "technical_requirements.csv"), index=False)
        print(f"  ✅  Created technical requirements CSV with {len(tech_req_data)} requirements")
    
    if api_integration_counts:
        api_data = [{"api_integration": str(a), "count": c} for a, c in api_integration_counts.most_common() if a is not None]
        pd.DataFrame(api_data).to_csv(os.path.join(outdir, "api_integration_needs.csv"), index=False)
        print(f"  ✅  Created API integration needs CSV with {len(api_data)} needs")
    
    if ui_workflow_counts:
        ui_data = [{"ui_workflow": str(u), "count": c} for u, c in ui_workflow_counts.most_common() if u is not None]
        pd.DataFrame(ui_data).to_csv(os.path.join(outdir, "ui_workflow_needs.csv"), index=False)
        print(f"  ✅  Created UI workflow needs CSV with {len(ui_data)} needs")
    
    if documentation_gap_counts:
        doc_data = [{"documentation_gap": str(d), "count": c} for d, c in documentation_gap_counts.most_common() if d is not None]
        pd.DataFrame(doc_data).to_csv(os.path.join(outdir, "documentation_gaps.csv"), index=False)
        print(f"  ✅  Created documentation gaps CSV with {len(doc_data)} gaps")

    # Simple charts
    def bar_save(items, title, xlabel, outfile, topn=15):
        if not items: 
            print(f"  ⚠️  No data for {outfile} chart")
            return
        try:
            dfp = pd.DataFrame(items[:topn])
            # Filter out None values
            dfp = dfp.dropna()
            if dfp.empty:
                print(f"  ⚠️  No valid data for {outfile} chart after filtering")
                return
            plt.figure(figsize=(12, 8))  # Increased figure size
            bars = plt.bar(range(len(dfp)), dfp[dfp.columns[1]])
            plt.title(title, fontsize=14, pad=20)
            
            # Set x-axis labels with better positioning
            plt.xticks(range(len(dfp)), dfp[dfp.columns[0]], rotation=45, ha="right")
            
            # Adjust layout to prevent label cutoff
            plt.xlabel(xlabel, fontsize=12)
            plt.ylabel("count", fontsize=12)
            
            # Add value labels on top of bars
            for bar, value in zip(bars, dfp[dfp.columns[1]]):
                plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1, 
                        str(value), ha='center', va='bottom', fontsize=10)
            
            # Ensure labels are fully visible
            plt.subplots_adjust(bottom=0.3, left=0.1, right=0.95, top=0.9)
            plt.savefig(os.path.join(outdir, outfile), dpi=300, bbox_inches='tight')
            plt.close()
            print(f"  ✅  Created chart: {outfile}")
        except Exception as e:
            print(f"  ❌  Error creating chart {outfile}: {e}")

    print("\n📊 Creating charts...")
    bar_save(list(topic_counts.most_common()), "Top Topics", "topic", "topics.png")
    bar_save(list(reason_counts.most_common()), "Top Failure Reasons", "reason", "reasons.png")
    bar_save(list(failure_category_counts.most_common()), "Failure Categories", "category", "failure_categories.png")
    bar_save(list(improvement_needed_counts.most_common()), "Top Improvement Needs", "improvement", "improvement_needs.png")
    bar_save(list(missing_feature_counts.most_common()), "Missing Features", "feature", "missing_features.png")
    bar_save(list(feature_category_counts.most_common()), "Feature Categories", "category", "feature_categories.png")
    
    # Success analysis charts
    if success_pattern_counts:
        bar_save(list(success_pattern_counts.most_common()), "Success Patterns", "pattern", "success_patterns.png")
    if demonstrated_skills_counts:
        bar_save(list(demonstrated_skills_counts.most_common()), "Demonstrated Skills", "skill", "demonstrated_skills.png")
    if user_satisfaction_counts:
        bar_save(list(user_satisfaction_counts.most_common()), "User Satisfaction Indicators", "indicator", "user_satisfaction.png")
    
    # Enhanced analysis charts
    if conversation_flow_counts:
        bar_save(list(conversation_flow_counts.most_common()), "Conversation Flows", "flow", "conversation_flows.png")
    if escalation_trigger_counts:
        bar_save(list(escalation_trigger_counts.most_common()), "Escalation Triggers", "trigger", "escalation_triggers.png")
    if error_pattern_counts:
        bar_save(list(error_pattern_counts.most_common()), "Error Patterns", "error", "error_patterns.png")
    if user_emotion_counts:
        bar_save(list(user_emotion_counts.most_common()), "User Emotions", "emotion", "user_emotions.png")
    if conversation_complexity_counts:
        bar_save(list(conversation_complexity_counts.most_common()), "Conversation Complexity", "complexity", "conversation_complexity.png")
    if feature_priority_counts:
        bar_save(list(feature_priority_counts.most_common()), "Feature Priorities", "priority", "feature_priorities.png")
    if improvement_effort_counts:
        bar_save(list(improvement_effort_counts.most_common()), "Improvement Efforts", "effort", "improvement_efforts.png")

    # Markdown report
    solved_total = sum(1 for r in per_chat if r.get("solved", False))
    unsolved_total = len(per_chat) - solved_total
    
    report = []
    report.append(f"# NewsBreak Ad Assistant Chatbot Analysis\n")
    report.append(f"- Files analyzed: **{len(per_chat)}**  \n- Solved conversations: **{solved_total}**  \n- Unsolved conversations: **{unsolved_total}**  \n- Solve rate: **{(solved_total/max(1,len(per_chat))):.1%}**  \n")
    
    report.append("## 📊 Analysis Results\n")
    report.append("### Top Topics\nSee `topic_stats.csv` and `topics.png`.\n")
    
    report.append("### Failure Analysis\n")
    report.append("#### Failure Categories\n")
    for category, count in failure_category_counts.most_common():
        percentage = (count / len(per_chat)) * 100
        report.append(f"- **{category}**: {count} conversations ({percentage:.1f}%)\n")
    
    report.append("\n#### Top Failure Reasons\n")
    for reason, count in reason_counts.most_common(5):
        report.append(f"- {reason}: {count} occurrences\n")
    
    report.append("\n### 🚀 Improvement Priorities\n")
    report.append("#### Most Needed Improvements\n")
    for improvement, count in improvement_needed_counts.most_common(5):
        report.append(f"- **{improvement}**: {count} conversations need this\n")
    
    report.append("\n### 🔧 Missing Features Analysis\n")
    if missing_feature_counts:
        report.append("#### Top Missing Features\n")
        for feature, count in missing_feature_counts.most_common(5):
            report.append(f"- **{feature}**: {count} conversations need this feature\n")
        
        report.append("\n#### Feature Categories by Priority\n")
        for category, count in feature_category_counts.most_common():
            percentage = (count / len(per_chat)) * 100
            report.append(f"- **{category}**: {count} conversations ({percentage:.1f}%)\n")
    else:
        report.append("No missing features identified in this sample.\n")
    
    report.append("\n### ✅ Success Analysis\n")
    if solved_total > 0:
        report.append(f"#### What the Bot Does Well ({solved_total} successful conversations)\n")
        
        if success_pattern_counts:
            report.append("**Top Success Patterns:**\n")
            for pattern, count in success_pattern_counts.most_common(5):
                percentage = (count / solved_total) * 100
                report.append(f"- **{pattern}**: {count} conversations ({percentage:.1f}% of successes)\n")
        
        if demonstrated_skills_counts:
            report.append("\n**Demonstrated Skills:**\n")
            for skill, count in demonstrated_skills_counts.most_common(5):
                percentage = (count / solved_total) * 100
                report.append(f"- **{skill}**: {count} conversations ({percentage:.1f}% of successes)\n")
        
        if user_satisfaction_counts:
            report.append("\n**User Satisfaction Indicators:**\n")
            for indicator, count in user_satisfaction_counts.most_common(5):
                percentage = (count / solved_total) * 100
                report.append(f"- **{indicator}**: {count} conversations ({percentage:.1f}% of successes)\n")
    else:
        report.append("No successful conversations in this sample.\n")
    
    report.append("\n### 🔍 Enhanced Analysis\n")
    
    if conversation_flow_counts:
        report.append("#### Conversation Flow Patterns\n")
        for flow, count in conversation_flow_counts.most_common(5):
            percentage = (count / len(per_chat)) * 100
            report.append(f"- **{flow}**: {count} conversations ({percentage:.1f}%)\n")
    
    if escalation_trigger_counts:
        report.append("\n#### Escalation Triggers\n")
        for trigger, count in escalation_trigger_counts.most_common(5):
            percentage = (count / len(per_chat)) * 100
            report.append(f"- **{trigger}**: {count} conversations ({percentage:.1f}%)\n")
    
    if error_pattern_counts:
        report.append("\n#### Error Patterns\n")
        for error, count in error_pattern_counts.most_common(5):
            percentage = (count / len(per_chat)) * 100
            report.append(f"- **{error}**: {count} conversations ({percentage:.1f}%)\n")
    
    if user_emotion_counts:
        report.append("\n#### User Emotional State\n")
        for emotion, count in user_emotion_counts.most_common():
            percentage = (count / len(per_chat)) * 100
            report.append(f"- **{emotion}**: {count} conversations ({percentage:.1f}%)\n")
    
    if conversation_complexity_counts:
        report.append("\n#### Conversation Complexity\n")
        for complexity, count in conversation_complexity_counts.most_common():
            percentage = (count / len(per_chat)) * 100
            report.append(f"- **{complexity}**: {count} conversations ({percentage:.1f}%)\n")
    
    if feature_priority_counts:
        report.append("\n#### Feature Priority Distribution\n")
        for priority, count in feature_priority_counts.most_common():
            percentage = (count / len(per_chat)) * 100
            report.append(f"- **Priority {priority}**: {count} conversations ({percentage:.1f}%)\n")
    
    if improvement_effort_counts:
        report.append("\n#### Improvement Effort Distribution\n")
        for effort, count in improvement_effort_counts.most_common():
            percentage = (count / len(per_chat)) * 100
            report.append(f"- **{effort} effort**: {count} conversations ({percentage:.1f}%)\n")
    
    report.append("\n## 📁 Output Files\n")
    report.append("- `summary.csv` - Detailed analysis of each conversation\n")
    report.append("- `topic_stats.csv` - Topic breakdown with solve rates\n")
    report.append("- `failure_categories.csv` - Categorized failure analysis\n")
    report.append("- `improvement_needs.csv` - Prioritized improvement list\n")
    report.append("- `missing_features.csv` - Specific missing features\n")
    report.append("- `feature_categories.csv` - Feature categories breakdown\n")
    report.append("- `reasons.csv` - Specific failure reasons\n")
    report.append("- `success_patterns.csv` - Success patterns analysis\n")
    report.append("- `demonstrated_skills.csv` - Bot skills analysis\n")
    report.append("- `user_satisfaction.csv` - User satisfaction analysis\n")
    report.append("- `conversation_flows.csv` - Conversation flow patterns\n")
    report.append("- `escalation_triggers.csv` - Escalation trigger analysis\n")
    report.append("- `error_patterns.csv` - Error pattern analysis\n")
    report.append("- `user_emotions.csv` - User emotional state analysis\n")
    report.append("- `conversation_complexity.csv` - Conversation complexity analysis\n")
    report.append("- `feature_priorities.csv` - Feature priority scoring\n")
    report.append("- `improvement_efforts.csv` - Improvement effort analysis\n")
    report.append("- `topics.png`, `failure_categories.png`, `improvement_needs.png`, `missing_features.png` - Visual charts\n")
    report.append("- `success_patterns.png`, `demonstrated_skills.png`, `user_satisfaction.png` - Success analysis charts\n")
    report.append("- `conversation_flows.png`, `escalation_triggers.png`, `error_patterns.png` - Enhanced analysis charts\n")
    report.append("- `user_emotions.png`, `conversation_complexity.png`, `feature_priorities.png`, `improvement_efforts.png` - Advanced analysis charts\n")
    
    report.append("\n## 📋 Generated Reports\n")
    report.append("- `report.md` - Detailed analysis report (this file)\n")
    report.append("- `summary_report.md` - Summary analysis report\n")
    report.append("- `executive_report.md` - Executive summary for presentations\n")
    
    report.append("\n## 🎯 Action Plan\n")
    report.append("1. **High Priority**: Focus on missing features needed by 3+ conversations\n")
    report.append("2. **Medium Priority**: Address failure categories affecting 10%+ of conversations\n")
    report.append("3. **Low Priority**: Handle edge cases and rare failures\n")
    report.append("4. **Feature Development**: Prioritize by feature category impact\n")
    
    with open(os.path.join(outdir, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(report))

    # Generate executive reports
    if not no_executive_report:
        print(f"\n📊 Generating executive reports...")
        try:
            from generate_executive_report import generate_executive_report, generate_concise_report
            
            # Generate detailed report
            executive_report_path = os.path.join(outdir, "executive_report.md")
            generate_executive_report(outdir, executive_report_path)
            print(f"  ✅ Detailed executive report complete: {executive_report_path}")
            
            # Generate concise report
            concise_report_path = os.path.join(outdir, "executive_report_concise.html")
            generate_concise_report(outdir, concise_report_path)
            print(f"  ✅ Concise HTML executive report complete: {concise_report_path}")
            
        except ImportError:
            print(f"  ⚠️  Executive report module not found, skipping executive report generation")
            print(f"  💡 Run 'python generate_executive_report.py --analysis_dir {outdir} --output executive_report.md' separately")
        except Exception as e:
            print(f"  ❌ Executive report generation failed: {e}")
            print(f"  💡 Run 'python generate_executive_report.py --analysis_dir {outdir} --output executive_report.md' separately")
    else:
        print(f"\n⏭️  Skipping executive report generation (--no_executive_report flag used)")
        print(f"  💡 Run 'python generate_executive_report.py --analysis_dir {outdir} --output executive_report.md' separately if needed")

    print(f"\n🎯 Analysis Complete!")
    print(f"📁 Raw data: {raw_path}")
    print(f"📊 Summary: {os.path.join(outdir,'summary.csv')}")
    print(f"🏷️  Topics: {os.path.join(outdir,'topic_stats.csv')}")
    print(f"❌ Reasons: {os.path.join(outdir,'reasons.csv')}")
    print(f"📋 Report: {os.path.join(outdir,'report.md')}")
    if not no_executive_report:
        print(f"📋 Detailed Executive Report: {os.path.join(outdir,'executive_report.md')}")
        print(f"📋 Concise HTML Executive Report: {os.path.join(outdir,'executive_report_concise.html')}")
    print(f"📈 Charts: {os.path.join(outdir,'topics.png')} & {os.path.join(outdir,'reasons.png')}")
    
    if errs > 0:
        print(f"\n⚠️  Warning: {errs} files had errors during processing")
    else:
        print(f"\n✅ All files processed successfully!")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input_glob", default="Bot_714b4955-90a2-4693-9380-a28dffee2e3a_Year_2025_4a86f154be3a4925a510e33bdda399b3 (3)/*.csv", help="e.g., data/*.csv")
    ap.add_argument("--outdir", default="analysis_out")
    ap.add_argument("--sample_limit", type=int, default=None, help="limit number of files")
    ap.add_argument("--dry_run", action="store_true", help="skip API calls (for quick test)")
    ap.add_argument("--workers", type=int, default=10, help="number of parallel workers (default: 10)")
    ap.add_argument("--no_executive_report", action="store_true", help="skip executive report generation")
    args = ap.parse_args()
    
    # Update MAX_WORKERS
    MAX_WORKERS = args.workers
    
    main(args.input_glob, args.outdir, args.sample_limit, args.dry_run, args.no_executive_report)
