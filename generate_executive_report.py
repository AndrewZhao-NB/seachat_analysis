#!/usr/bin/env python3
"""
Executive Report Generator for Chatbot Analysis
Generates a comprehensive, presentation-ready report with key insights and actionable recommendations.
"""

import os
import json
import pandas as pd
from collections import Counter
import argparse

def load_analysis_data(analysis_dir):
    """Load all analysis data from the output directory."""
    data = {}
    
    # Load per-chat detailed data
    per_chat_path = os.path.join(analysis_dir, "per_chat.jsonl")
    if os.path.exists(per_chat_path):
        results = []
        with open(per_chat_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    results.append(json.loads(line))
        data['per_chat'] = results
    
    # Load summary CSV
    summary_path = os.path.join(analysis_dir, "summary.csv")
    if os.path.exists(summary_path):
        data['summary'] = pd.read_csv(summary_path)
    
    # Load categorized data
    csv_files = [
        'failure_categories.csv', 'categorized_failures.csv', 'categorized_tasks.csv',
        'missing_features.csv', 'improvement_needs.csv', 'feature_categories.csv',
        'success_patterns.csv', 'capabilities.csv', 'successful_topics.csv',
        'conversation_flows.csv', 'escalation_triggers.csv', 'error_patterns.csv',
        'user_emotions.csv', 'conversation_complexity.csv', 'feature_priorities.csv',
        'improvement_efforts.csv'
    ]
    
    for csv_file in csv_files:
        file_path = os.path.join(analysis_dir, csv_file)
        if os.path.exists(file_path):
            key = csv_file.replace('.csv', '')
            data[key] = pd.read_csv(file_path)
    
    return data

def generate_executive_summary(data):
    """Generate high-level executive summary."""
    if 'per_chat' not in data:
        return "No analysis data found."
    
    total_conversations = len(data['per_chat'])
    solved_conversations = sum(1 for r in data['per_chat'] if r.get('solved', False))
    solve_rate = (solved_conversations / total_conversations) * 100 if total_conversations > 0 else 0
    
    # Calculate key metrics
    needs_human = sum(1 for r in data['per_chat'] if r.get('needs_human', False))
    human_rate = (needs_human / total_conversations) * 100 if total_conversations > 0 else 0
    
    # User emotion analysis
    emotions = [r.get('user_emotion', 'neutral') for r in data['per_chat']]
    emotion_counts = Counter(emotions)
    
    # Conversation complexity
    complexities = [r.get('conversation_complexity', 'simple') for r in data['per_chat']]
    complexity_counts = Counter(complexities)
    
    summary = f"""
# 🤖 Chatbot Performance Executive Summary

## 📊 Overall Performance Metrics
- **Total Conversations Analyzed**: {total_conversations:,}
- **Success Rate**: {solve_rate:.1f}% ({solved_conversations:,} conversations)
- **Human Escalation Rate**: {human_rate:.1f}% ({needs_human:,} conversations)
- **Failure Rate**: {100-solve_rate:.1f}% ({total_conversations-solved_conversations:,} conversations)

## 😊 User Experience Insights
- **Satisfied Users**: {emotion_counts.get('satisfied', 0):,} ({emotion_counts.get('satisfied', 0)/total_conversations*100:.1f}%)
- **Frustrated Users**: {emotion_counts.get('frustrated', 0):,} ({emotion_counts.get('frustrated', 0)/total_conversations*100:.1f}%)
- **Neutral Users**: {emotion_counts.get('neutral', 0):,} ({emotion_counts.get('neutral', 0)/total_conversations*100:.1f}%)

## 🔍 Conversation Complexity Distribution
- **Simple Conversations**: {complexity_counts.get('simple', 0):,} ({complexity_counts.get('simple', 0)/total_conversations*100:.1f}%)
- **Moderate Complexity**: {complexity_counts.get('moderate', 0):,} ({complexity_counts.get('moderate', 0)/total_conversations*100:.1f}%)
- **Complex Conversations**: {complexity_counts.get('complex', 0):,} ({complexity_counts.get('complex', 0)/total_conversations*100:.1f}%)
"""
    return summary

def generate_problem_analysis(data):
    """Generate detailed problem analysis with statistics."""
    if 'per_chat' not in data:
        return "No analysis data found."
    
    results = data['per_chat']
    total = len(results)
    
    # Failure categories
    failure_categories = [r.get('failure_category', 'unknown') for r in results]
    failure_counts = Counter(failure_categories)
    
    # Missing features with priority
    missing_features = []
    for r in results:
        if r.get('failure_category') == 'feature-not-supported':
            feature = r.get('missing_feature', 'unknown')
            priority = r.get('feature_priority_score', 1)
            missing_features.append((feature, priority))
    
    # Improvement needs with effort (ONLY actionable improvements, exclude "no improvement needed" responses)
    improvement_needs = []
    for r in results:
        improvement = r.get('specific_improvement_needed', 'none')
        effort = r.get('improvement_effort', 'low')
        # Filter out non-actionable responses
        if (improvement and 
            improvement != 'none' and 
            not any(phrase in improvement.lower() for phrase in [
                'no-improvement-needed', 'bot-handled-perfectly', 'user-request-fulfilled', 
                'conversation-successful', 'bot-solved-problem', 'user-satisfied',
                'conversation-completed-successfully', 'system-functioning-perfectly',
                'all-requests-successful', 'no-technical-issues'
            ])):
            improvement_needs.append((improvement, effort))
    
    # Escalation triggers (ONLY actual triggers, exclude "no escalation needed" responses)
    escalation_triggers = []
    for r in results:
        triggers = r.get('escalation_triggers', [])
        for trigger in triggers:
            if trigger and not any(phrase in trigger.lower() for phrase in [
                'none', 'no-escalation-needed', 'bot-solved-problem', 'user-satisfied',
                'conversation-completed-successfully', 'user-abandoned-conversation',
                'no-escalation-needed'
            ]):
                escalation_triggers.append(trigger)
    
    # Error patterns (ONLY actual errors, exclude "no errors detected" responses)
    error_patterns = []
    for r in results:
        errors = r.get('error_patterns', [])
        for error in errors:
            if error and not any(phrase in error.lower() for phrase in [
                'none', 'no-errors-detected', 'system-functioning-perfectly',
                'all-requests-successful', 'no-technical-issues', 'conversation-abandoned'
            ]):
                error_patterns.append(error)
    
    problem_report = f"""
## 🚨 Critical Problems & Issues

### 1. Failure Categories (What's Breaking)
"""
    
    for category, count in failure_counts.most_common():
        percentage = (count / total) * 100
        problem_report += f"- **{category}**: {count:,} conversations ({percentage:.1f}%)\n"
    
    problem_report += f"""

### 2. Missing Features (What We Need to Build)
"""
    
    if missing_features:
        feature_counts = Counter(missing_features)
        for (feature, priority), count in feature_counts.most_common(10):
            problem_report += f"- **Priority {priority}**: {feature} - {count:,} conversations need this\n"
    
    problem_report += f"""

### 3. Top Improvement Needs (What to Fix First)
"""
    
    if improvement_needs:
        improvement_counts = Counter(improvement_needs)
        for (improvement, effort), count in improvement_counts.most_common(10):
            problem_report += f"- **{effort.upper()} effort**: {improvement} - {count:,} conversations affected\n"
    
    problem_report += f"""

### 4. Escalation Triggers (Why Users Give Up)
"""
    
    if escalation_triggers:
        trigger_counts = Counter(escalation_triggers)
        for trigger, count in trigger_counts.most_common(10):
            problem_report += f"- **{trigger}**: {count:,} conversations escalated\n"
    
    problem_report += f"""

### 5. Error Patterns (Technical Issues)
"""
    
    if error_patterns:
        error_counts = Counter(error_patterns)
        for error, count in error_counts.most_common(10):
            problem_report += f"- **{error}**: {count:,} conversations affected\n"
    
    # Add summary of what was filtered out
    filtered_improvements = sum(1 for r in results if any(phrase in r.get('specific_improvement_needed', '').lower() for phrase in [
        'no-improvement-needed', 'bot-handled-perfectly', 'user-request-fulfilled', 
        'conversation-successful', 'bot-solved-problem', 'user-satisfied',
        'conversation-completed-successfully', 'system-functioning-perfectly',
        'all-requests-successful', 'no-technical-issues'
    ]))
    
    filtered_escalations = sum(1 for r in results if any(phrase in str(r.get('escalation_triggers', [])).lower() for phrase in [
        'none', 'no-escalation-needed', 'bot-solved-problem', 'user-satisfied',
        'conversation-completed-successfully', 'user-abandoned-conversation'
    ]))
    
    filtered_errors = sum(1 for r in results if any(phrase in str(r.get('error_patterns', [])).lower() for phrase in [
        'none', 'no-errors-detected', 'system-functioning-perfectly',
        'all-requests-successful', 'no-technical-issues', 'conversation-abandoned'
    ]))
    
    problem_report += f"""

### 6. Summary of Non-Actionable Responses (Filtered Out)
- **No Improvement Needed**: {filtered_improvements:,} conversations (bot handled perfectly)
- **No Escalation Needed**: {filtered_escalations:,} conversations (bot solved without escalation)
- **No Errors Detected**: {filtered_errors:,} conversations (system working perfectly)

*Note: These represent successful conversations and don't require action.*
"""
    
    return problem_report

def generate_success_analysis(data):
    """Generate success analysis with what's working well."""
    if 'per_chat' not in data:
        return "No analysis data found."
    
    results = data['per_chat']
    solved_results = [r for r in results if r.get('solved', False)]
    solved_total = len(solved_results)
    
    if solved_total == 0:
        return "## ✅ Success Analysis\nNo successful conversations found in this sample."
    
    # Success patterns
    success_patterns = []
    for r in solved_results:
        patterns = r.get('success_patterns', [])
        for pattern in patterns:
            if pattern:
                success_patterns.append(pattern)
    
    # Demonstrated capabilities
    capabilities = []
    for r in solved_results:
        caps = r.get('capabilities', [])
        for cap in caps:
            if cap:
                capabilities.append(cap)
    
    # Successful topics
    successful_topics = []
    for r in solved_results:
        topics = r.get('topics', [])
        for topic in topics:
            if topic and topic != 'unknown':
                successful_topics.append(topic)
    
    # User satisfaction indicators
    satisfaction_indicators = []
    for r in solved_results:
        indicators = r.get('user_satisfaction_indicators', [])
        for indicator in indicators:
            if indicator:
                satisfaction_indicators.append(indicator)
    
    success_report = f"""
## ✅ Success Analysis - What's Working Well

### Overview
- **Successful Conversations**: {solved_total:,} out of {len(results):,} ({solved_total/len(results)*100:.1f}%)
- **These represent our chatbot's strengths** and should be maintained/expanded

### 1. Top Success Patterns
"""
    
    if success_patterns:
        pattern_counts = Counter(success_patterns)
        for pattern, count in pattern_counts.most_common(10):
            percentage = (count / solved_total) * 100
            success_report += f"- **{topic}**: {count:,} conversations ({percentage:.1f}% of successes)\n"
    
    success_report += f"""

### 2. Demonstrated Capabilities
"""
    
    if capabilities:
        capability_counts = Counter(capabilities)
        for capability, count in capability_counts.most_common(10):
            percentage = (count / solved_total) * 100
            success_report += f"- **{capability}**: {count:,} conversations ({percentage:.1f}% of successes)\n"
    
    success_report += f"""

### 3. Successful Topics
"""
    
    if successful_topics:
        topic_counts = Counter(successful_topics)
        for topic, count in topic_counts.most_common(10):
            percentage = (count / solved_total) * 100
            success_report += f"- **{topic}**: {count:,} conversations ({percentage:.1f}% of successes)\n"
    
    success_report += f"""

### 4. User Satisfaction Indicators
"""
    
    if satisfaction_indicators:
        satisfaction_counts = Counter(satisfaction_indicators)
        for indicator, count in satisfaction_counts.most_common(10):
            percentage = (count / solved_total) * 100
            success_report += f"- **{indicator}**: {count:,} conversations ({percentage:.1f}% of successes)\n"
    
    return success_report

def generate_improvement_roadmap(data):
    """Generate prioritized improvement roadmap with statistics."""
    if 'per_chat' not in data:
        return "No analysis data found."
    
    results = data['per_chat']
    total = len(results)
    
    # Collect improvement data (ONLY actionable improvements)
    improvements = []
    for r in results:
        improvement = r.get('specific_improvement_needed', 'none')
        effort = r.get('improvement_effort', 'low')
        priority = r.get('feature_priority_score', 1)
        # Filter out non-actionable responses
        if (improvement and 
            improvement != 'none' and 
            not any(phrase in improvement.lower() for phrase in [
                'no-improvement-needed', 'bot-handled-perfectly', 'user-request-fulfilled', 
                'conversation-successful', 'bot-solved-problem', 'user-satisfied',
                'conversation-completed-successfully', 'system-functioning-perfectly',
                'all-requests-successful', 'no-technical-issues'
            ])):
            improvements.append({
                'improvement': improvement,
                'effort': effort,
                'priority': priority,
                'failure_category': r.get('failure_category', 'unknown')
            })
    
    if not improvements:
        # Count what was filtered out
        filtered_count = sum(1 for r in results if any(phrase in r.get('specific_improvement_needed', '').lower() for phrase in [
            'no-improvement-needed', 'bot-handled-perfectly', 'user-request-fulfilled', 
            'conversation-successful', 'bot-solved-problem', 'user-satisfied',
            'conversation-completed-successfully', 'system-functioning-perfectly',
            'all-requests-successful', 'no-technical-issues'
        ]))
        
        return f"""## 🚀 Improvement Roadmap

### 🎉 Great News - No Actionable Improvements Needed!
- **{filtered_count:,} conversations** were handled perfectly by the bot
- **No critical issues** requiring immediate attention
- **Focus on expanding** successful capabilities to more use cases

### What This Means
- Your chatbot is working well for the analyzed conversations
- Consider expanding to new domains or use cases
- Monitor for new failure patterns as usage grows
"""
    
    # Create improvement dataframe
    df = pd.DataFrame(improvements)
    
    # Group by improvement and calculate stats
    improvement_stats = df.groupby('improvement').agg({
        'effort': lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else 'unknown',
        'priority': 'mean',
        'failure_category': lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else 'unknown'
    }).reset_index()
    
    # Count occurrences
    improvement_counts = df['improvement'].value_counts()
    improvement_stats['count'] = improvement_stats['improvement'].map(improvement_counts)
    improvement_stats['percentage'] = (improvement_stats['count'] / total) * 100
    
    # Sort by count (impact) and priority
    improvement_stats = improvement_stats.sort_values(['count', 'priority'], ascending=[False, False])
    
    roadmap = f"""
## 🚀 Prioritized Improvement Roadmap

### Impact vs. Effort Matrix
**Impact**: Number of conversations affected
**Effort**: Low (UI changes), Medium (API integration), High (new systems)

### High-Impact Improvements (Affect 10+ conversations)
"""
    
    high_impact = improvement_stats[improvement_stats['count'] >= 10]
    for _, row in high_impact.iterrows():
        roadmap += f"""
**{row['improvement']}**
- **Impact**: {row['count']:,} conversations ({row['percentage']:.1f}%)
- **Effort**: {row['effort'].upper()}
- **Priority Score**: {row['priority']:.1f}/5
- **Failure Category**: {row['failure_category']}
"""
    
    roadmap += f"""

### Medium-Impact Improvements (Affect 5-9 conversations)
"""
    
    medium_impact = improvement_stats[(improvement_stats['count'] >= 5) & (improvement_stats['count'] < 10)]
    for _, row in medium_impact.iterrows():
        roadmap += f"""
**{row['improvement']}**
- **Impact**: {row['count']:,} conversations ({row['percentage']:.1f}%)
- **Effort**: {row['effort'].upper()}
- **Priority Score**: {row['priority']:.1f}/5
"""
    
    roadmap += f"""

### Low-Impact Improvements (Affect 2-4 conversations)
"""
    
    low_impact = improvement_stats[(improvement_stats['count'] >= 2) & (improvement_stats['count'] < 5)]
    for _, row in low_impact.iterrows():
        roadmap += f"""
**{row['improvement']}**
- **Impact**: {row['count']:,} conversations ({row['percentage']:.1f}%)
- **Effort**: {row['effort'].upper()}
- **Priority Score**: {row['priority']:.1f}/5
"""
    
    # Add summary of what was filtered out
    filtered_count = sum(1 for r in results if any(phrase in r.get('specific_improvement_needed', '').lower() for phrase in [
        'no-improvement-needed', 'bot-handled-perfectly', 'user-request-fulfilled', 
        'conversation-successful', 'bot-solved-problem', 'user-satisfied',
        'conversation-completed-successfully', 'system-functioning-perfectly',
        'all-requests-successful', 'no-technical-issues'
    ]))
    
    roadmap += f"""

### 📊 Summary
- **Actionable Improvements**: {len(improvements):,} unique items identified
- **Conversations Handled Perfectly**: {filtered_count:,} (no action needed)
- **Total Conversations Analyzed**: {total:,}

*Note: Only actionable improvements that require development work are shown above.*
"""
    
    return roadmap

def generate_action_plan(data):
    """Generate actionable next steps."""
    if 'per_chat' not in data:
        return "No analysis data found."
    
    results = data['per_chat']
    total = len(results)
    
    # Calculate key metrics for recommendations
    solve_rate = (sum(1 for r in results if r.get('solved', False)) / total) * 100
    human_rate = (sum(1 for r in results if r.get('needs_human', False)) / total) * 100
    
    # Top failure categories
    failure_categories = [r.get('failure_category', 'unknown') for r in results]
    top_failure = Counter(failure_categories).most_common(1)[0] if failure_categories else ('unknown', 0)
    
    # Top missing features
    missing_features = []
    for r in results:
        if r.get('failure_category') == 'feature-not-supported':
            feature = r.get('missing_feature', 'unknown')
            priority = r.get('feature_priority_score', 1)
            missing_features.append((feature, priority))
    
    top_missing_feature = Counter(missing_features).most_common(1)[0] if missing_features else (('none', 1), 0)
    
    action_plan = f"""
## 🎯 Action Plan & Next Steps

### Current State Assessment
- **Success Rate**: {solve_rate:.1f}% - **Needs improvement**
- **Human Escalation Rate**: {human_rate:.1f}% - **Too high**
- **Top Failure**: {top_failure[0]} ({top_failure[1]:,} conversations)
- **Top Missing Feature**: {top_missing_feature[0][0]} (Priority {top_missing_feature[0][1]})

### Immediate Actions (Next 30 Days)

#### 1. 🚨 Critical Fixes (Week 1-2)
- **Address top failure category**: {top_failure[0]}
- **Implement missing feature**: {top_missing_feature[0][0]}
- **Reduce human escalation rate** from {human_rate:.1f}% to target 20%

#### 2. 🔧 High-Impact Improvements (Week 3-4)
- **Focus on improvements affecting 10+ conversations**
- **Prioritize by effort level** (Low → Medium → High)
- **Target success rate improvement** from {solve_rate:.1f}% to 60%+

### Medium-Term Goals (Next 3 Months)

#### 1. Feature Development
- **Build missing features** identified in analysis
- **Integrate with external systems** for account management
- **Improve error handling** and user guidance

#### 2. Process Optimization
- **Reduce conversation complexity** where possible
- **Improve escalation workflows** for better handoffs
- **Enhance user onboarding** and help content

### Long-Term Vision (Next 6-12 Months)

#### 1. Success Rate Targets
- **Q2**: Achieve 60% success rate
- **Q3**: Achieve 75% success rate  
- **Q4**: Achieve 85% success rate

#### 2. User Experience Goals
- **Reduce frustration rate** from current level to <20%
- **Increase satisfaction rate** to >50%
- **Minimize human escalation** to <15%

### Success Metrics to Track
- **Daily/Weekly success rate** trends
- **User emotion distribution** changes
- **Escalation rate** reduction
- **Feature adoption** for new capabilities
- **User satisfaction** improvements

### Resource Requirements
- **Development Team**: Focus on high-priority missing features
- **UX/UI Team**: Improve conversation flows and user guidance
- **Product Team**: Prioritize feature roadmap based on impact
- **Support Team**: Better escalation workflows and training
"""
    
    return action_plan

def generate_executive_report(analysis_dir, output_file):
    """Generate the complete executive report."""
    print(f"📊 Loading analysis data from {analysis_dir}...")
    data = load_analysis_data(analysis_dir)
    
    if not data:
        print("❌ No analysis data found!")
        return
    
    print("📝 Generating executive report...")
    
    # Generate all sections
    executive_summary = generate_executive_summary(data)
    problem_analysis = generate_problem_analysis(data)
    success_analysis = generate_success_analysis(data)
    improvement_roadmap = generate_improvement_roadmap(data)
    action_plan = generate_action_plan(data)
    
    # Combine into full report with clear separation
    full_report = f"""{executive_summary}

---

## 🚨 FAILURE ANALYSIS - What Needs to Be Fixed

{problem_analysis}

{improvement_roadmap}

{action_plan}

---

## ✅ SUCCESS ANALYSIS - What's Working Well

{success_analysis}

---

## 📊 SUCCESS STATISTICS - High-Level Overview
*Note: These are basic stats for reporting. For detailed failure analysis, see sections above.*

### Success Metrics Summary
- **Total Successful Conversations**: {sum(1 for r in data.get('per_chat', []) if r.get('solved', False)):,}
- **Success Rate**: {data.get('per_chat', []) and (sum(1 for r in data['per_chat'] if r.get('solved', False)) / len(data['per_chat']) * 100) or 0:.1f}%
- **User Satisfaction Rate**: {data.get('per_chat', []) and (sum(1 for r in data['per_chat'] if r.get('user_emotion') == 'satisfied') / len(data['per_chat']) * 100) or 0:.1f}%

### What This Means
- **Success cases** are documented for reporting and understanding strengths
- **Failure cases** are analyzed in detail for actionable improvements
- **Focus should be on the failure analysis sections above** for development priorities

---

## 📁 Data Sources
This report is based on analysis of {len(data.get('per_chat', [])):,} chatbot conversations.
Generated on: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}

## 📊 Key Insights Summary
1. **Success Rate**: {data.get('per_chat', []) and (sum(1 for r in data['per_chat'] if r.get('solved', False)) / len(data['per_chat']) * 100) or 0:.1f}%
2. **Top Problem**: {data.get('per_chat', []) and Counter([r.get('failure_category', 'unknown') for r in data['per_chat']]).most_common(1)[0][0] or 'Unknown'}
3. **User Satisfaction**: {data.get('per_chat', []) and (sum(1 for r in data['per_chat'] if r.get('user_emotion') == 'satisfied') / len(data['per_chat']) * 100) or 0:.1f}%
4. **Improvement Priority**: Focus on features affecting 10+ conversations first
"""
    
    # Write report
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(full_report)
    
    print(f"✅ Executive report generated: {output_file}")
    print(f"📊 Report structure:")
    print(f"   📈 Executive summary with key metrics")
    print(f"   🚨 FAILURE ANALYSIS - What needs to be fixed")
    print(f"   🚀 Prioritized improvement roadmap")
    print(f"   🎯 Actionable next steps")
    print(f"   ✅ SUCCESS ANALYSIS - What's working well (for reporting)")
    print(f"   📊 Success statistics overview")
    print(f"\n💡 Focus on FAILURE ANALYSIS sections for development priorities!")

def generate_concise_report(analysis_dir, output_file):
    """Generate a concise executive report for quick reviews."""
    print(f"📊 Loading analysis data from {analysis_dir}...")
    data = load_analysis_data(analysis_dir)
    
    if not data:
        print("❌ No analysis data found!")
        return
    
    print("📝 Generating concise executive report...")
    
    results = data['per_chat']
    total = len(results)
    solved = sum(1 for r in results if r.get('solved', False))
    needs_human = sum(1 for r in results if r.get('needs_human', False))
    
    # Get actionable improvements only
    actionable_improvements = []
    for r in results:
        improvement = r.get('specific_improvement_needed', 'none')
        effort = r.get('improvement_effort', 'low')
        if (improvement and 
            improvement != 'none' and 
            not any(phrase in improvement.lower() for phrase in [
                'no-improvement-needed', 'bot-handled-perfectly', 'user-request-fulfilled', 
                'conversation-successful', 'bot-solved-problem', 'user-satisfied',
                'conversation-completed-successfully', 'system-functioning-perfectly',
                'all-requests-successful', 'no-technical-issues'
            ])):
            actionable_improvements.append((improvement, effort))
    
    # Get top failure categories
    failure_categories = [r.get('failure_category', 'unknown') for r in results]
    failure_counts = Counter(failure_categories)
    
    # Get top missing features
    missing_features = []
    for r in results:
        if r.get('failure_category') == 'feature-not-supported':
            feature = r.get('missing_feature', 'unknown')
            priority = r.get('feature_priority_score', 1)
            missing_features.append((feature, priority))
    
    # Get human escalation reasons
    human_escalation_reasons = []
    for r in results:
        if r.get('needs_human', False):
            reason = r.get('why_unsolved', ['unknown'])[0] if isinstance(r.get('why_unsolved'), list) else r.get('why_unsolved', 'unknown')
            human_escalation_reasons.append(reason)
    
    # Get user tasks that need human help
    human_tasks = []
    for r in results:
        if r.get('needs_human', False):
            tasks = r.get('user_tasks_attempted', ['unknown'])
            if isinstance(tasks, list):
                for task in tasks:
                    human_tasks.append(task)
            else:
                human_tasks.append(tasks)
    
    # Generate concise report
    concise_report = f"""# 🤖 Chatbot Performance - Executive Summary

## 📊 Key Metrics
- **Total Conversations**: {total:,}
- **Success Rate**: {solved/total*100:.1f}% ({solved:,} solved)
- **Human Escalation Rate**: {needs_human/total*100:.1f}% ({needs_human:,} escalated)

## 📋 Quick Impact Summary
| Category | Count | % of Total | Priority |
|----------|-------|------------|----------|
| **Human Escalations** | {needs_human:,} | {needs_human/total*100:.1f}% | 🔴 Critical |
| **Missing Features** | {len(missing_features):,} | {len(missing_features)/total*100:.1f}% | 🟡 High |
| **Actionable Issues** | {len(actionable_improvements):,} | {len(actionable_improvements)/total*100:.1f}% | 🟠 Medium |

---

## 🚨 Critical Issues (Top 3)

### 1. Top Failure Categories
"""
    
    for category, count in failure_counts.most_common(3):
        percentage = (count / total) * 100
        concise_report += f"- **{category}**: {count:,} conversations ({percentage:.1f}%)\n"
    
    concise_report += f"""

### 2. Top Missing Features
"""
    
    if missing_features:
        feature_counts = Counter(missing_features)
        for (feature, priority), count in feature_counts.most_common(3):
            concise_report += f"- **Priority {priority}**: {feature} - {count:,} conversations need this\n"
    else:
        concise_report += "- No critical missing features identified\n"
    
    concise_report += f"""

### 3. Top Actionable Improvements
"""
    
    if actionable_improvements:
        improvement_counts = Counter(actionable_improvements)
        for (improvement, effort), count in improvement_counts.most_common(3):
            concise_report += f"- **{effort.upper()} effort**: {improvement} - {count:,} conversations affected\n"
    else:
        concise_report += "- No actionable improvements needed\n"
    
    concise_report += f"""

---

## 🔍 Detailed Breakdown by Impact

### What Users Need Human Help For (Top 10)
"""
    
    # Combine both reasons and tasks for a complete picture
    combined_issues = []
    for r in results:
        if r.get('needs_human', False):
            # Get the main reason
            reason = r.get('why_unsolved', ['unknown'])[0] if isinstance(r.get('why_unsolved'), list) else r.get('why_unsolved', 'unknown')
            # Get the task they were trying to do
            tasks = r.get('user_tasks_attempted', ['unknown'])
            if isinstance(tasks, list):
                task = tasks[0] if tasks else 'unknown'
            else:
                task = tasks
            
            # Combine them for context
            if reason != 'unknown' and task != 'unknown':
                combined_issues.append(f"{task} - {reason}")
            elif reason != 'unknown':
                combined_issues.append(reason)
            elif task != 'unknown':
                combined_issues.append(task)
            else:
                combined_issues.append('unknown issue')
    
    if combined_issues:
        issue_counts = Counter(combined_issues)
        # Only show issues affecting 2+ conversations
        significant_issues = [(issue, count) for issue, count in issue_counts.most_common(10) if count >= 2]
        if significant_issues:
            for issue, count in significant_issues:
                percentage = (count / needs_human) * 100 if needs_human > 0 else 0
                concise_report += f"- **{issue}**: {count:,} conversations ({percentage:.1f}% of escalations)\n"
        else:
            concise_report += "- No significant issues (all issues affect <2 conversations)\n"
    else:
        concise_report += "- No human escalations recorded\n"
    
    concise_report += f"""

### Missing Features by Impact
"""
    
    if missing_features:
        # Just count features without priority grouping
        feature_counts = Counter([feature for feature, _ in missing_features])
        # Only show features needed by 2+ conversations
        significant_features = [(feature, count) for feature, count in feature_counts.most_common(10) if count >= 2]
        if significant_features:
            for feature, count in significant_features:
                concise_report += f"- **{feature}**: {count:,} conversations need this\n"
        else:
            concise_report += "- No significant features (all affect <2 conversations)\n"
    else:
        concise_report += "- No missing features identified\n"
    
    concise_report += f"""

---

## 📊 Summary
- **Total Conversations**: {total:,}
- **Success Rate**: {solved/total*100:.1f}% ({solved:,} solved)
- **Human Escalation Rate**: {needs_human/total*100:.1f}% ({needs_human:,} escalated)
- **Significant Issues**: {len([(issue, count) for issue, count in Counter(combined_issues).items() if count >= 2])} issues affecting 2+ conversations
"""
    
    # Write concise report
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(concise_report)
    
    print(f"✅ Concise executive report generated: {output_file}")
    print(f"📊 Concise report includes:")
    print(f"   📈 Key metrics and success rates")
    print(f"   🚨 Top 3 critical issues")
    print(f"   🎯 Immediate action items")
    print(f"   📋 Quick reference for stakeholders")

def main():
    parser = argparse.ArgumentParser(description='Generate executive report from chatbot analysis')
    parser.add_argument('--analysis_dir', default='analysis_out', help='Directory containing analysis results')
    parser.add_argument('--output', default='executive_report.md', help='Output file for the report')
    parser.add_argument('--short', action='store_true', help='Generate concise version (default: detailed)')
    
    args = parser.parse_args()
    
    if args.short:
        generate_concise_report(args.analysis_dir, args.output)
    else:
        generate_executive_report(args.analysis_dir, args.output)

if __name__ == "__main__":
    main()
