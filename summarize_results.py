#!/usr/bin/env python3
import os
import json
import pandas as pd
import re
from collections import Counter, defaultdict
import argparse

def load_analysis_results(analysis_dir):
    """Load all analysis results from the analysis directory."""
    results = {}
    
    # Load per_chat.jsonl
    per_chat_path = os.path.join(analysis_dir, "per_chat.jsonl")
    if os.path.exists(per_chat_path):
        with open(per_chat_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    results[data['file']] = data
    
    # Load summary.csv as backup
    summary_path = os.path.join(analysis_dir, "summary.csv")
    if os.path.exists(summary_path) and not results:
        df = pd.read_csv(summary_path)
        for _, row in df.iterrows():
            results[row['file']] = {
                'file': row['file'],
                'topics': row['topics'].split(',') if pd.notna(row['topics']) else [],
                'user_tasks': row['user_tasks'].split('; ') if pd.notna(row['user_tasks']) else [],
                'solved': row['solved'],
                'needs_human': row['needs_human'],
                'failure_category': row['failure_category'],
                'missing_feature': row['missing_feature'],
                'feature_category': row['feature_category'],
                'why_unsolved': row['why_unsolved'].split('; ') if pd.notna(row['why_unsolved']) else [],
                'improvement_needed': row['improvement_needed'],
                'capabilities': row['capabilities'].split('; ') if pd.notna(row['capabilities']) else [],
                'limitations': row['limitations'].split('; ') if pd.notna(row['limitations']) else []
            }
    
    return results

def categorize_failure_reasons(reasons):
    """Group similar failure reasons into meaningful categories."""
    if not reasons:
        return []
    
    # Define failure reason categories with MUCH broader patterns
    categories = {
        'missing-user-info': [
            'missing-user-info', 'missing user info', 'user did not provide', 'user never provided',
            'missing information', 'incomplete information', 'insufficient details', 'user did not',
            'user never', 'missing', 'incomplete', 'insufficient', 'not provided', 'not given',
            'need', 'require', 'want', 'looking for', 'seeking', 'ask for', 'request'
        ],
        'requires-human-intervention': [
            'requires-human', 'requires human', 'needs human', 'human intervention',
            'agent intervention', 'live agent', 'human support', 'escalation needed',
            'contact support', 'support team', 'human agent', 'live person', 'escalate',
            'human', 'agent', 'support', 'escalate', 'escalation', 'intervention'
        ],
        'feature-not-available': [
            'feature-not-supported', 'not supported', 'cannot do', 'lacks capability',
            'feature unavailable', 'not implemented', 'no such feature', 'cannot',
            'unable to', 'not possible', 'does not support', 'lack of', 'missing feature',
            'can\'t', 'cant', 'unable', 'impossible', 'not available', 'no feature'
        ],
        'technical-limitations': [
            'technical issue', 'system limitation', 'api limitation', 'database access',
            'permission denied', 'access restricted', 'system error', 'technical',
            'system', 'api', 'database', 'permission', 'access', 'error', 'exception',
            'bug', 'crash', 'fail', 'failure', 'broken', 'down', 'issue', 'problem'
        ],
        'policy-restrictions': [
            'policy violation', 'not allowed', 'restricted', 'forbidden',
            'compliance issue', 'regulatory requirement', 'policy', 'violation',
            'not allowed', 'restricted', 'forbidden', 'compliance', 'regulatory',
            'rule', 'guideline', 'standard', 'requirement', 'must', 'should'
        ],
        'user-abandoned': [
            'user left', 'user abandoned', 'conversation ended', 'user stopped',
            'no response', 'user disappeared', 'abandoned', 'left', 'stopped',
            'no response', 'disappeared', 'ended', 'bye', 'goodbye', 'exit'
        ],
        'bot-error': [
            'bot error', 'parse error', 'processing error', 'exception',
            'bot mistake', 'wrong information', 'error', 'parse', 'processing',
            'exception', 'mistake', 'wrong', 'incorrect', 'false', 'invalid'
        ],
        'form-submission': [
            'form', 'submission', 'submit', 'form completion', 'form filled',
            'fill', 'complete', 'input', 'enter', 'provide', 'give'
        ],
        'information-provided': [
            'information provided', 'details given', 'user provided', 'completed form',
            'submitted', 'filled out', 'provided info', 'gave', 'shared', 'told'
        ],
        'account-issues': [
            'account', 'login', 'password', 'username', 'email', 'profile',
            'sign in', 'sign up', 'register', 'authentication', 'verify'
        ],
        'billing-issues': [
            'billing', 'payment', 'charge', 'cost', 'price', 'fee', 'invoice',
            'refund', 'money', 'credit', 'debit', 'subscription', 'plan'
        ],
        'campaign-issues': [
            'campaign', 'ad', 'advertisement', 'targeting', 'audience', 'budget',
            'performance', 'metrics', 'analytics', 'report', 'data'
        ],
        'incomplete-conversation': [
            'incomplete-conversation', 'no user input', 'no user request', 'no user response',
            'user never responded', 'user never made request', 'conversation abandoned',
            'no conversation', 'empty conversation', 'bot only', 'no user interaction',
            'incomplete', 'abandoned', 'no response', 'no request', 'no input',
            'user-abandoned-conversation', 'no-escalation-needed', 'conversation-abandoned'
        ],
        'successful-no-improvement': [
            'bot-handled-perfectly', 'user-request-fulfilled', 'conversation-successful',
            'bot-solved-problem', 'user-satisfied', 'conversation-completed-successfully',
            'system-functioning-perfectly', 'all-requests-successful', 'no-technical-issues',
            'no-improvement-needed-user-abandoned'
        ],
        'no-improvement-needed': [
            'no-improvement-needed-empty-transcript', 'no-improvement-needed-incomplete-conversation',
            'no-improvement-needed-dry-run', 'no-improvement-needed-parse-error',
            'no-improvement-needed-processing-error', 'no-improvement-needed'
        ],
        'no-missing-feature': [
            'no-missing-feature-empty-transcript', 'no-missing-feature-incomplete-conversation',
            'no-missing-feature-dry-run', 'no-missing-feature-parse-error',
            'no-missing-feature-processing-error', 'no-missing-feature'
        ],
        'no-feature-category': [
            'no-feature-category-empty-transcript', 'no-feature-category-incomplete-conversation',
            'no-feature-category-dry-run', 'no-feature-category-parse-error',
            'no-feature-category-processing-error', 'no-feature-category'
        ]
    }
    
    categorized = []
    for reason in reasons:
        reason_lower = reason.lower().strip()
        categorized_reason = 'other'
        
        for category, patterns in categories.items():
            if any(pattern in reason_lower for pattern in patterns):
                categorized_reason = category
                break
        
        categorized.append(categorized_reason)
    
    return categorized

def analyze_other_category(results):
    """Analyze what's actually in the 'other' category to break it down."""
    other_failures = []
    other_tasks = []
    
    # Handle both dict and list formats
    if isinstance(results, dict):
        results_list = list(results.values())
    else:
        results_list = results
    
    for result in results_list:
        # Analyze failure categories marked as "other"
        if result.get('failure_category') == 'other':
            why_unsolved = result.get('why_unsolved', [])
            for reason in why_unsolved:
                if reason and reason != 'none':
                    other_failures.append(reason.lower())
        
        # Analyze user tasks marked as "other"
        user_tasks = result.get('user_tasks_attempted', [])
        for task in user_tasks:
            if task and task != 'none':
                other_tasks.append(task.lower())
    
    # Count and categorize the "other" items
    failure_counts = Counter(other_failures)
    task_counts = Counter(other_tasks)
    
    return failure_counts, task_counts

def identify_success_patterns(file_data):
    """Identify patterns in successful conversations."""
    patterns = []
    
    # Check for form completion success
    if 'form-submission' in file_data.get('topics', []):
        patterns.append('form-completion')
    
    # Check for information gathering success
    if 'information-provided' in file_data.get('why_unsolved', []):
        patterns.append('information-gathering')
    
    # Check for policy explanation success
    if 'policy' in file_data.get('topics', []) or 'ad-policy' in file_data.get('topics', []):
        patterns.append('policy-explanation')
    
    # Check for how-to guidance success
    if 'how-to' in file_data.get('topics', []) or 'guidance' in file_data.get('capabilities', []):
        patterns.append('how-to-guidance')
    
    # Check for account support success
    if 'account' in file_data.get('topics', []) or 'account-management' in file_data.get('topics', []):
        patterns.append('account-support')
    
    # Check for billing support success
    if 'billing' in file_data.get('topics', []) or 'payment' in file_data.get('topics', []):
        patterns.append('billing-support')
    
    # Check for technical guidance success
    if 'technical' in file_data.get('topics', []) or 'support' in file_data.get('capabilities', []):
        patterns.append('technical-guidance')
    
    return patterns

def categorize_user_tasks(tasks):
    """Group user tasks into meaningful categories."""
    if not tasks:
        return []
    
    task_categories = {
        'account-management': [
            'password reset', 'account access', 'login', 'profile change',
            'account verification', 'account setup', 'account recovery',
            'account', 'login', 'password', 'username', 'email', 'profile',
            'sign in', 'sign up', 'register', 'authentication', 'verify',
            'access', 'permission', 'role', 'admin', 'user'
        ],
        'billing-support': [
            'refund', 'payment', 'billing', 'invoice', 'charge',
            'subscription', 'cost', 'pricing', 'money', 'credit', 'debit',
            'plan', 'fee', 'charge', 'cost', 'price', 'bill', 'invoice'
        ],
        'campaign-management': [
            'campaign', 'ad creation', 'targeting', 'budget', 'performance',
            'optimization', 'ad set', 'creative', 'advertisement', 'ad',
            'audience', 'target', 'budget', 'spend', 'performance', 'metrics',
            'analytics', 'report', 'data', 'roi', 'conversion'
        ],
        'technical-support': [
            'bug', 'error', 'issue', 'problem', 'not working',
            'broken', 'fix', 'troubleshoot', 'technical', 'system',
            'crash', 'fail', 'failure', 'down', 'slow', 'lag', 'glitch'
        ],
        'policy-inquiry': [
            'policy', 'guidelines', 'rules', 'allowed', 'permitted',
            'compliance', 'requirements', 'rule', 'guideline', 'standard',
            'must', 'should', 'can i', 'am i allowed', 'is it ok'
        ],
        'feature-request': [
            'can you', 'is it possible', 'add feature', 'new capability',
            'enhancement', 'improvement', 'feature', 'capability', 'function',
            'tool', 'option', 'setting', 'preference', 'customization'
        ],
        'general-inquiry': [
            'how to', 'what is', 'when', 'where', 'why',
            'information', 'help', 'question', 'help', 'guide', 'tutorial',
            'explain', 'tell me', 'show me', 'demonstrate'
        ],
        'form-completion': [
            'form', 'fill', 'complete', 'submit', 'input', 'enter',
            'provide', 'give', 'upload', 'attach', 'document'
        ],
        'status-check': [
            'status', 'check', 'verify', 'confirm', 'look up', 'find',
            'search', 'locate', 'track', 'monitor', 'progress'
        ]
    }
    
    categorized = []
    for task in tasks:
        task_lower = task.lower().strip()
        categorized_task = 'other'
        
        for category, patterns in task_categories.items():
            if any(pattern in task_lower for pattern in patterns):
                categorized_task = category
                break
        
        categorized.append(categorized_task)
    
    return categorized

def generate_summary_report(results, output_dir):
    """Generate comprehensive summary reports."""
    if not results:
        print("❌ No results to summarize!")
        return
    
    print(f"📊 Summarizing {len(results)} conversation results...")
    
    # Initialize counters
    summary_stats = {
        'total_conversations': len(results),
        'solved_conversations': 0,
        'needs_human': 0,
        'failure_categories': Counter(),
        'feature_categories': Counter(),
        'topics': Counter(),
        'categorized_failures': Counter(),
        'categorized_tasks': Counter(),
        'improvement_needs': Counter(),
        'escalation_triggers': Counter(),
        'error_patterns': Counter(),
        'successful_topics': Counter(),
        'successful_tasks': Counter(),
        'capabilities': Counter(),
        'success_patterns': Counter()
    }
    
    # Process each result
    for file_data in results.values():
        # Basic stats
        if file_data.get('solved', False):
            summary_stats['solved_conversations'] += 1
        
        if file_data.get('needs_human', False):
            summary_stats['needs_human'] += 1
        
        # Count topics
        for topic in file_data.get('topics', []):
            if topic and topic != 'unknown':
                summary_stats['topics'][topic] += 1
        
        # Count failure categories
        failure_cat = file_data.get('failure_category', 'unknown')
        if failure_cat and failure_cat != 'unknown':
            summary_stats['failure_categories'][failure_cat] += 1
        
        # Count feature categories
        feature_cat = file_data.get('feature_category', 'none')
        if feature_cat and feature_cat != 'none':
            summary_stats['feature_categories'][feature_cat] += 1
        
        # Count escalation triggers (avoid generic "none" responses)
        escalation_triggers = file_data.get('escalation_triggers', [])
        if escalation_triggers:
            for trigger in escalation_triggers:
                if trigger and trigger != 'none':
                    if any(phrase in trigger.lower() for phrase in ['no-escalation', 'bot-solved', 'user-satisfied', 'conversation-completed']):
                        summary_stats['escalation_triggers']['no-escalation-needed-successful'] += 1
                    elif any(phrase in trigger.lower() for phrase in ['user-abandoned', 'conversation-abandoned']):
                        summary_stats['escalation_triggers']['no-escalation-needed-abandoned'] += 1
                    else:
                        summary_stats['escalation_triggers'][trigger] += 1
        else:
            # Handle cases where escalation_triggers is empty
            summary_stats['escalation_triggers']['no-escalation-triggers-provided'] += 1
        
        # Count error patterns (avoid generic "none" responses)
        error_patterns = file_data.get('error_patterns', [])
        if error_patterns:
            for error in error_patterns:
                if error and error != 'none':
                    if any(phrase in error.lower() for phrase in ['no-errors', 'system-functioning', 'all-requests-successful', 'no-technical']):
                        summary_stats['error_patterns']['no-errors-detected-successful'] += 1
                    elif any(phrase in error.lower() for phrase in ['conversation-abandoned', 'user-abandoned']):
                        summary_stats['error_patterns']['no-errors-detected-abandoned'] += 1
                    else:
                        summary_stats['error_patterns'][error] += 1
        else:
            # Handle cases where error_patterns is empty
            summary_stats['error_patterns']['no-error-patterns-provided'] += 1
        
        # Categorize failure reasons
        failure_reasons = file_data.get('why_unsolved', [])
        categorized_failures = categorize_failure_reasons(failure_reasons)
        for failure in categorized_failures:
            summary_stats['categorized_failures'][failure] += 1
        
        # Categorize user tasks
        user_tasks = file_data.get('user_tasks_attempted', [])
        categorized_tasks = categorize_user_tasks(user_tasks)
        for task in categorized_tasks:
            summary_stats['categorized_tasks'][task] += 1
        
        # Count improvement needs
        improvement = file_data.get('improvement_needed', 'no-improvement-needed')
        if improvement and improvement != 'no-improvement-needed':
            # Categorize improvement needs to avoid generic responses
            if any(phrase in improvement.lower() for phrase in ['no-improvement', 'bot-handled', 'user-request-fulfilled', 'conversation-successful']):
                summary_stats['improvement_needs']['no-improvement-needed-successful'] += 1
            elif any(phrase in improvement.lower() for phrase in ['user-abandoned', 'conversation-abandoned']):
                summary_stats['improvement_needs']['no-improvement-needed-abandoned'] += 1
            else:
                summary_stats['improvement_needs'][improvement] += 1
        else:
            # Handle cases where improvement is marked as no-improvement-needed
            summary_stats['improvement_needs']['no-improvement-needed'] += 1
        
        # Analyze successful conversations
        if file_data.get('solved', False):
            # What topics were successfully handled
            for topic in file_data.get('topics', []):
                if topic and topic != 'unknown':
                    summary_stats['successful_topics'][topic] += 1
            
            # What tasks were successfully completed
            for task in user_tasks:
                if task:
                    summary_stats['successful_tasks'][task] += 1
            
            # What capabilities were demonstrated
            for capability in file_data.get('capabilities', []):
                if capability:
                    summary_stats['capabilities'][capability] += 1
            
            # Look for success patterns in the conversation
            success_patterns = identify_success_patterns(file_data)
            for pattern in success_patterns:
                summary_stats['success_patterns'][pattern] += 1
    
    # Calculate percentages
    total = summary_stats['total_conversations']
    solve_rate = (summary_stats['solved_conversations'] / total) * 100 if total > 0 else 0
    human_rate = (summary_stats['needs_human'] / total) * 100 if total > 0 else 0
    
    # Generate summary CSV
    summary_data = {
        'metric': [
            'Total Conversations',
            'Solved Conversations', 
            'Solve Rate (%)',
            'Needs Human (%)',
            'Top Failure Category',
            'Top Feature Category',
            'Top Topic',
            'Top Categorized Failure',
            'Top Categorized Task'
        ],
        'value': [
            total,
            summary_stats['solved_conversations'],
            f"{solve_rate:.1f}%",
            f"{human_rate:.1f}%",
            summary_stats['failure_categories'].most_common(1)[0][0] if summary_stats['failure_categories'] else 'N/A',
            summary_stats['feature_categories'].most_common(1)[0][0] if summary_stats['feature_categories'] else 'N/A',
            summary_stats['topics'].most_common(1)[0][0] if summary_stats['topics'] else 'N/A',
            summary_stats['categorized_failures'].most_common(1)[0][0] if summary_stats['categorized_failures'] else 'N/A',
            summary_stats['categorized_tasks'].most_common(1)[0][0] if summary_stats['categorized_tasks'] else 'N/A'
        ]
    }
    
    summary_df = pd.DataFrame(summary_data)
    summary_csv_path = os.path.join(output_dir, "summary_report.csv")
    summary_df.to_csv(summary_csv_path, index=False)
    print(f"  ✅ Created summary report: {summary_csv_path}")
    
    # Generate categorized failures CSV
    if summary_stats['categorized_failures']:
        failures_df = pd.DataFrame([
            {'failure_category': k, 'count': v, 'percentage': (v/total)*100}
            for k, v in summary_stats['categorized_failures'].most_common()
        ])
        failures_csv_path = os.path.join(output_dir, "categorized_failures.csv")
        failures_df.to_csv(failures_csv_path, index=False)
        print(f"  ✅ Created categorized failures: {failures_csv_path}")
    
    # Generate categorized tasks CSV
    if summary_stats['categorized_tasks']:
        tasks_df = pd.DataFrame([
            {'task_category': k, 'count': v, 'percentage': (v/total)*100}
            for k, v in summary_stats['categorized_tasks'].most_common()
        ])
        tasks_csv_path = os.path.join(output_dir, "categorized_tasks.csv")
        tasks_df.to_csv(tasks_csv_path, index=False)
        print(f"  ✅ Created categorized tasks: {tasks_csv_path}")
    
    # Generate improvement priorities CSV
    if summary_stats['improvement_needs']:
        improvements_df = pd.DataFrame([
            {'improvement': k, 'count': v, 'priority': 'High' if v >= 3 else 'Medium' if v >= 2 else 'Low'}
            for k, v in summary_stats['improvement_needs'].most_common()
        ])
        improvements_csv_path = os.path.join(output_dir, "improvement_priorities.csv")
        improvements_df.to_csv(improvements_csv_path, index=False)
        print(f"  ✅ Created improvement priorities: {improvements_csv_path}")
    
    # Generate success analysis CSV
    if summary_stats['successful_topics']:
        success_topics_df = pd.DataFrame([
            {'successful_topic': k, 'count': v, 'percentage': (v/summary_stats['solved_conversations'])*100}
            for k, v in summary_stats['successful_topics'].most_common()
        ])
        success_topics_csv_path = os.path.join(output_dir, "successful_topics.csv")
        success_topics_df.to_csv(success_topics_csv_path, index=False)
        print(f"  ✅ Created successful topics: {success_topics_csv_path}")
    
    # Generate capabilities CSV
    if summary_stats['capabilities']:
        capabilities_df = pd.DataFrame([
            {'capability': k, 'count': v, 'percentage': (v/summary_stats['solved_conversations'])*100}
            for k, v in summary_stats['capabilities'].most_common()
        ])
        capabilities_csv_path = os.path.join(output_dir, "capabilities.csv")
        capabilities_df.to_csv(capabilities_csv_path, index=False)
        print(f"  ✅ Created capabilities: {capabilities_csv_path}")
    
    # Generate success patterns CSV
    if summary_stats['success_patterns']:
        patterns_df = pd.DataFrame([
            {'success_pattern': k, 'count': v, 'percentage': (v/summary_stats['solved_conversations'])*100}
            for k, v in summary_stats['success_patterns'].most_common()
        ])
        patterns_csv_path = os.path.join(output_dir, "success_patterns.csv")
        patterns_df.to_csv(patterns_csv_path, index=False)
        print(f"  ✅ Created success patterns: {patterns_csv_path}")
    
    # Analyze what's in the "other" category
    other_failure_counts, other_task_counts = analyze_other_category(results)
    
    # Generate "other" breakdown CSVs
    if other_failure_counts:
        other_failures_df = pd.DataFrame([
            {'other_failure_reason': k, 'count': v}
            for k, v in other_failure_counts.most_common(20)
        ])
        other_failures_csv_path = os.path.join(output_dir, "other_failures_breakdown.csv")
        other_failures_df.to_csv(other_failures_csv_path, index=False)
        print(f"  ✅ Created other failures breakdown: {other_failures_csv_path}")
    
    if other_task_counts:
        other_tasks_df = pd.DataFrame([
            {'other_user_task': k, 'count': v}
            for k, v in other_task_counts.most_common(20)
        ])
        other_tasks_csv_path = os.path.join(output_dir, "other_tasks_breakdown.csv")
        other_tasks_df.to_csv(other_tasks_csv_path, index=False)
        print(f"  ✅ Created other tasks breakdown: {other_tasks_csv_path}")
    
    # Generate markdown summary
    markdown_content = f"""# Chatbot Analysis Summary Report

## 📊 Overall Statistics
- **Total Conversations**: {total}
- **Solved Conversations**: {summary_stats['solved_conversations']} ({solve_rate:.1f}%)
- **Needs Human**: {summary_stats['needs_human']} ({human_rate:.1f}%)

## 🚨 Top Failure Categories
"""
    
    for category, count in summary_stats['failure_categories'].most_common(5):
        percentage = (count / total) * 100
        markdown_content += f"- **{category}**: {count} conversations ({percentage:.1f}%)\n"
    
    markdown_content += "\n## 🔧 Top Feature Categories\n"
    for category, count in summary_stats['feature_categories'].most_common(5):
        percentage = (count / total) * 100
        markdown_content += f"- **{category}**: {count} conversations ({percentage:.1f}%)\n"
    
    markdown_content += "\n## 🏷️ Top Topics\n"
    for topic, count in summary_stats['topics'].most_common(5):
        percentage = (count / total) * 100
        markdown_content += f"- **{topic}**: {count} conversations ({percentage:.1f}%)\n"
    
    markdown_content += "\n## ❌ Categorized Failure Reasons\n"
    for failure, count in summary_stats['categorized_failures'].most_common():
        percentage = (count / total) * 100
        markdown_content += f"- **{failure}**: {count} conversations ({percentage:.1f}%)\n"
    
    markdown_content += "\n## 🎯 Categorized User Tasks\n"
    for task, count in summary_stats['categorized_tasks'].most_common():
        percentage = (count / total) * 100
        markdown_content += f"- **{task}**: {count} conversations ({percentage:.1f}%)\n"
    
    markdown_content += "\n## 🚀 Improvement Priorities\n"
    for improvement, count in summary_stats['improvement_needs'].most_common(5):
        priority = "High" if count >= 3 else "Medium" if count >= 2 else "Low"
        markdown_content += f"- **{priority} Priority**: {improvement} ({count} conversations need this)\n"
    
    # Add "other" category breakdown
    if other_failure_counts:
        markdown_content += "\n### 🔍 Breaking Down the 'Other' Category\n"
        markdown_content += "**Top 'Other' Failure Reasons (need better categorization):**\n"
        for reason, count in other_failure_counts.most_common(10):
            markdown_content += f"- **{reason}**: {count} occurrences\n"
        
        markdown_content += "\n**Recommendation**: These patterns should be added to the categorization system.\n"
    
    if other_task_counts:
        markdown_content += "\n**Top 'Other' User Tasks (need better categorization):**\n"
        for task, count in other_task_counts.most_common(10):
            markdown_content += f"- **{task}**: {count} occurrences\n"
        
        markdown_content += "\n**Recommendation**: These task types should be added to the task categorization system.\n"
    
    markdown_content += "\n## ✅ Success Analysis\n"
    markdown_content += f"### What the Chatbot Does Well ({summary_stats['solved_conversations']} successful conversations)\n"
    
    if summary_stats['successful_topics']:
        markdown_content += "\n#### Top Successful Topics\n"
        for topic, count in summary_stats['successful_topics'].most_common(5):
            percentage = (count / summary_stats['solved_conversations']) * 100
            markdown_content += f"- **{topic}**: {count} conversations ({percentage:.1f}% of successes)\n"
    
    if summary_stats['capabilities']:
        markdown_content += "\n#### Demonstrated Capabilities\n"
        for capability, count in summary_stats['capabilities'].most_common(5):
            percentage = (count / summary_stats['solved_conversations']) * 100
            markdown_content += f"- **{capability}**: {count} conversations ({percentage:.1f}% of successes)\n"
    
    if summary_stats['success_patterns']:
        markdown_content += "\n#### Success Patterns\n"
        for pattern, count in summary_stats['success_patterns'].most_common():
            percentage = (count / summary_stats['solved_conversations']) * 100
            markdown_content += f"- **{pattern}**: {count} conversations ({percentage:.1f}% of successes)\n"
    
    markdown_content += f"""

## 📁 Generated Files
- `summary_report.csv` - High-level summary statistics
- `categorized_failures.csv` - Grouped failure reasons
- `categorized_tasks.csv` - Grouped user task types  
- `improvement_priorities.csv` - Prioritized improvement list
- `successful_topics.csv` - What the bot does well
- `capabilities.csv` - Demonstrated bot capabilities
- `success_patterns.csv` - Patterns in successful conversations
- `other_failures_breakdown.csv` - Breakdown of "other" failure reasons
- `other_tasks_breakdown.csv` - Breakdown of "other" user tasks

## 💡 Key Insights
1. **Most Common Issue**: {summary_stats['categorized_failures'].most_common(1)[0][0] if summary_stats['categorized_failures'] else 'N/A'}
2. **Top User Need**: {summary_stats['categorized_tasks'].most_common(1)[0][0] if summary_stats['categorized_tasks'] else 'N/A'}
3. **Priority Improvement**: {summary_stats['improvement_needs'].most_common(1)[0][0] if summary_stats['improvement_needs'] else 'N/A'}
"""
    
    markdown_path = os.path.join(output_dir, "summary_report.md")
    with open(markdown_path, 'w', encoding='utf-8') as f:
        f.write(markdown_content)
    print(f"  ✅ Created summary markdown: {markdown_path}")
    
    print(f"\n🎯 Summary complete! Check {output_dir} for all summary files.")
    return summary_stats

def main():
    parser = argparse.ArgumentParser(description='Summarize chatbot analysis results')
    parser.add_argument('--analysis_dir', default='analysis_out', help='Directory containing analysis results')
    parser.add_argument('--output_dir', default='analysis_out', help='Directory to save summary files')
    args = parser.parse_args()
    
    # Load results
    results = load_analysis_results(args.analysis_dir)
    
    if not results:
        print(f"❌ No analysis results found in {args.analysis_dir}")
        return
    
    # Generate summary
    generate_summary_report(results, args.output_dir)

if __name__ == "__main__":
    main()
