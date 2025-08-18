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
        'improvement_efforts.csv', 'technical_requirements.csv', 'api_integration_needs.csv',
        'ui_workflow_needs.csv', 'documentation_gaps.csv'
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
    technical_analysis = generate_technical_analysis(data)
    success_analysis = generate_success_analysis(data)
    improvement_roadmap = generate_improvement_roadmap(data)
    action_plan = generate_action_plan(data)
    
    # Combine into full report with clear separation
    full_report = f"""{executive_summary}

---

## 🚨 FAILURE ANALYSIS - What Needs to Be Fixed

{problem_analysis}

---

## 🔧 TECHNICAL IMPLEMENTATION ANALYSIS - Specific Technical Requirements

{technical_analysis}

---

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
    
    # Get top missing features (consolidated)
    missing_features = []
    feature_consolidation = {}
    
    for r in results:
        if r.get('failure_category') == 'feature-not-supported':
            feature = r.get('missing_feature', 'unknown')
            if feature and feature != 'unknown':
                # Consolidate similar features
                consolidated_feature = consolidate_similar_features(feature)
                if consolidated_feature not in feature_consolidation:
                    feature_consolidation[consolidated_feature] = {'count': 0, 'examples': []}
                feature_consolidation[consolidated_feature]['count'] += 1
                feature_consolidation[consolidated_feature]['examples'].append(feature)
    
    # Convert to list format for display
    for consolidated_feature, data in feature_consolidation.items():
        missing_features.append((consolidated_feature, data['count'], data['examples']))
    
    # Sort by count
    missing_features.sort(key=lambda x: x[1], reverse=True)
    
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
                human_tasks.append(task)
    
    # Generate HTML report
    html_report = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Customer Service Chatbot Report</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            background: #f5f5f7;
            color: #1d1d1f;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 {
            margin: 0;
            font-size: 2.5em;
            font-weight: 700;
        }
        .header p {
            margin: 10px 0 0 0;
            opacity: 0.9;
            font-size: 1.2em;
        }
        .content {
            padding: 30px;
        }
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .metric-card {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            border-left: 4px solid #667eea;
        }
        .metric-number {
            font-size: 2em;
            font-weight: 700;
            color: #667eea;
            margin-bottom: 5px;
        }
        .metric-label {
            color: #6c757d;
            font-size: 0.9em;
        }
        .section {
            margin-bottom: 40px;
        }
        .section h2 {
            color: #495057;
            border-bottom: 2px solid #e9ecef;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }
        .section h3 {
            color: #6c757d;
            margin-top: 25px;
        }
        .issue-list {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 20px;
        }
        .issue-item {
            background: white;
            margin: 10px 0;
            padding: 15px;
            border-radius: 6px;
            border-left: 4px solid #dc3545;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        .issue-count {
            background: #dc3545;
            color: white;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 0.8em;
            font-weight: 600;
            float: right;
        }
        .feature-item {
            background: white;
            margin: 10px 0;
            padding: 15px;
            border-radius: 6px;
            border-left: 4px solid #ffc107;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        .feature-count {
            background: #ffc107;
            color: #212529;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 0.8em;
            font-weight: 600;
            float: right;
        }
        .summary-box {
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
            color: white;
            padding: 25px;
            border-radius: 8px;
            text-align: center;
        }
        .summary-box h3 {
            margin-top: 0;
            color: white;
        }
        .summary-stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }
        .summary-stat {
            background: rgba(255,255,255,0.2);
            padding: 15px;
            border-radius: 6px;
        }
        .summary-number {
            font-size: 1.5em;
            font-weight: 700;
            margin-bottom: 5px;
        }
        .clickable-item {
            cursor: pointer;
            transition: all 0.2s ease;
        }
        .clickable-item:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.5);
        }
        .modal-content {
            background-color: white;
            margin: 5% auto;
            padding: 20px;
            border-radius: 12px;
            width: 90%;
            max-width: 800px;
            max-height: 80vh;
            overflow-y: auto;
            position: relative;
        }
        .close {
            color: #aaa;
            float: right;
            font-size: 28px;
            font-weight: bold;
            cursor: pointer;
            position: absolute;
            right: 20px;
            top: 15px;
        }
        .close:hover {
            color: #000;
        }
        .conversation-example {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 15px;
            margin: 10px 0;
            border-left: 4px solid #667eea;
        }
        .conversation-header {
            font-weight: 600;
            color: #495057;
            margin-bottom: 10px;
        }
        .conversation-text {
            font-family: monospace;
            background: white;
            padding: 10px;
            border-radius: 4px;
            border: 1px solid #e9ecef;
            white-space: pre-wrap;
            font-size: 0.9em;
            max-height: 200px;
            overflow-y: auto;
        }
        .search-box {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            margin-bottom: 15px;
            font-size: 14px;
        }
        @media (max-width: 768px) {
            .metrics-grid {
                grid-template-columns: 1fr;
            }
            .summary-stats {
                grid-template-columns: 1fr;
            }
            .modal-content {
                width: 95%;
                margin: 10% auto;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Customer Service Chatbot Report</h1>
            <p>Executive Summary - """ + pd.Timestamp.now().strftime('%B %d, %Y') + """</p>
        </div>
        
        <div class="content">
            <div class="section">
                <h2>📊 Key Metrics</h2>
                <div class="metrics-grid">
                    <div class="metric-card">
                        <div class="metric-number">""" + f"{total:,}" + """</div>
                        <div class="metric-label">Total Conversations</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-number">""" + f"{solved/total*100:.1f}%" + """</div>
                        <div class="metric-label">Success Rate</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-number">""" + f"{needs_human/total*100:.1f}%" + """</div>
                        <div class="metric-label">Human Escalation Rate</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-number">""" + f"{len(missing_features):,}" + """</div>
                        <div class="metric-label">Missing Features</div>
                    </div>
                </div>
            </div>

            <div class="section">
                <h2>🚨 PROBLEMS THE CHATBOT CANNOT SOLVE</h2>
                
                <h3>1. Missing Functions & Features</h3>
                <div class="issue-list">"""
    
    if missing_features:
        for feature, count, examples in missing_features[:8]:  # Top 8 missing features
            html_report += """
                    <div class="feature-item">
                        <span class="feature-count">""" + f"{count:,}" + """</span>
                        <strong>""" + feature + """</strong>
                    </div>"""
    else:
        html_report += """
                    <div class="feature-item">
                        <span class="feature-count">0</span>
                        <strong>No missing features identified</strong>
                    </div>"""
    
    html_report += """
                </div>

                <h3>2. API & System Access Needed</h3>
                <div class="issue-list">"""
    
    # Show API and system access problems
    api_problems = []
    for r in results:
        if r.get('failure_category') == 'feature-not-supported':
            feature = r.get('missing_feature', '')
            if feature and any(term in feature.lower() for term in ['api', 'access', 'schema', 'system', 'database']):
                api_problems.append(feature)
    
    if api_problems:
        problem_counts = Counter(api_problems)
        for problem, count in problem_counts.most_common(5):
            html_report += f"""
                    <div class="feature-item">
                        <span class="feature-count">{count}</span>
                        <strong>{problem}</strong>
                    </div>"""
    else:
        html_report += """
                    <div class="feature-item">
                        <span class="feature-count">0</span>
                        <strong>No API access problems identified</strong>
                    </div>"""
    
    html_report += """
                </div>

                <h3>3. UI & Workflow Improvements Needed</h3>
                <div class="issue-list">"""
    
    # Show UI and workflow problems
    ui_problems = []
    for r in results:
        if r.get('failure_category') == 'feature-not-supported':
            feature = r.get('missing_feature', '')
            if feature and any(term in feature.lower() for term in ['ui', 'interface', 'workflow', 'form', 'button', 'desktop']):
                ui_problems.append(feature)
    
    if ui_problems:
        problem_counts = Counter(ui_problems)
        for problem, count in problem_counts.most_common(5):
            html_report += f"""
                    <div class="feature-item">
                        <span class="feature-count">{count}</span>
                        <strong>{problem}</strong>
                    </div>"""
    else:
        html_report += """
                    <div class="feature-item">
                        <span class="feature-count">0</span>
                        <strong>No UI improvements needed</strong>
                    </div>"""
    
    html_report += """
                </div>

                <h3>4. Integration & Third-Party Support Needed</h3>
                <div class="issue-list">"""
    
    # Show integration problems
    integration_problems = []
    for r in results:
        if r.get('failure_category') == 'feature-not-supported':
            feature = r.get('missing_feature', '')
            if feature and any(term in feature.lower() for term in ['integration', 'clickmagick', 'weebly', 'wix', 'everflow']):
                integration_problems.append(feature)
    
    if integration_problems:
        problem_counts = Counter(integration_problems)
        for problem, count in problem_counts.most_common(5):
            html_report += f"""
                    <div class="feature-item">
                        <span class="feature-count">{count}</span>
                        <strong>{problem}</strong>
                    </div>"""
    else:
        html_report += """
                    <div class="feature-item">
                        <span class="feature-count">0</span>
                        <strong>No integration problems identified</strong>
                    </div>"""
    
    html_report += """
                </div>
            </div>

            <div class="section">
                <h2>✅ PROBLEMS THE CHATBOT CAN SOLVE WELL</h2>
                
                <h3>Successful Capabilities</h3>
                <div class="issue-list">"""
    
    # Show what the bot does well
    successful_capabilities = []
    for r in results:
        if r.get('solved', False):
            caps = r.get('capabilities', [])
            if isinstance(caps, list):
                for cap in caps:
                    if cap and cap != 'unknown':
                        successful_capabilities.append(cap)
    
    if successful_capabilities:
        cap_counts = Counter(successful_capabilities)
        for capability, count in cap_counts.most_common(5):
            html_report += f"""
                    <div class="feature-item">
                        <span class="feature-count">{count}</span>
                        <strong>{capability}</strong>
                    </div>"""
    else:
        html_report += """
                    <div class="feature-item">
                        <span class="feature-count">0</span>
                        <strong>No successful capabilities identified</strong>
                    </div>"""
    
    html_report += """
                </div>
            </div>

            <div class="summary-box">
                <h3>📊 Summary</h3>
                <div class="summary-stats">
                    <div class="summary-stat">
                        <div class="summary-number">""" + f"{total:,}" + """</div>
                        <div>Total Conversations</div>
                    </div>
                    <div class="summary-stat">
                        <div class="summary-number">""" + f"{solved/total*100:.1f}%" + """</div>
                        <div>Success Rate</div>
                    </div>
                    <div class="summary-stat">
                        <div class="summary-number">""" + f"{needs_human/total*100:.1f}%" + """</div>
                        <div>Human Escalation Rate</div>
                    </div>
                    <div class="summary-stat">
                        <div class="summary-number">""" + f"{len(missing_features)}" + """</div>
                        <div>Missing Features</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>"""
    
    # Write HTML report
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_report)
    
    print(f"✅ HTML executive report generated: {output_file}")
    print(f"📊 HTML report includes:")
    print(f"   📈 Key metrics and success rates")
    print(f"   🚨 Top 3 critical issues")
    print(f"   🔍 Detailed breakdown by impact")
    print(f"   📋 Summary statistics")
    print(f"   🌐 Open in any web browser on Mac")

def generate_technical_analysis(data):
    """Generate detailed technical analysis with specific implementation details."""
    if 'technical_requirements' not in data or 'api_integration_needs' not in data:
        return "No technical analysis data found."
    
    technical_analysis = []
    technical_analysis.append("## 🔧 Technical Implementation Analysis")
    technical_analysis.append("")
    
    # API Integration needs
    if 'api_integration_needs' in data:
        api_df = data['api_integration_needs']
        if not api_df.empty:
            technical_analysis.append("### 🔌 API Integration Requirements")
            technical_analysis.append("")
            for _, row in api_df.head(5).iterrows():
                requirement = row['api_integration']
                count = row['count']
                technical_analysis.append(f"- **{requirement}** - {count} conversations need this")
                # Extract specific technical details
                if 'api' in requirement.lower():
                    technical_analysis.append(f"  - **Technical Need**: REST API endpoint development")
                if 'integrate' in requirement.lower():
                    technical_analysis.append(f"  - **Technical Need**: System integration layer")
                if 'database' in requirement.lower():
                    technical_analysis.append(f"  - **Technical Need**: Database access layer")
                technical_analysis.append("")
    
    # UI/Workflow needs
    if 'ui_workflow_needs' in data:
        ui_df = data['ui_workflow_needs']
        if not ui_df.empty:
            technical_analysis.append("### 🎨 UI/Workflow Requirements")
            technical_analysis.append("")
            for _, row in ui_df.head(5).iterrows():
                requirement = row['ui_workflow']
                count = row['count']
                technical_analysis.append(f"- **{requirement}** - {count} conversations need this")
                # Extract specific UI details
                if 'workflow' in requirement.lower():
                    technical_analysis.append(f"  - **UI Need**: Multi-step form workflow")
                if 'button' in requirement.lower():
                    technical_analysis.append(f"  - **UI Need**: Interactive button elements")
                if 'form' in requirement.lower():
                    technical_analysis.append(f"  - **UI Need**: Form validation and submission")
                technical_analysis.append("")
    
    # Documentation gaps
    if 'documentation_gaps' in data:
        doc_df = data['documentation_gaps']
        if not doc_df.empty:
            technical_analysis.append("### 📚 Documentation & Knowledge Gaps")
            technical_analysis.append("")
            for _, row in doc_df.head(5).iterrows():
                gap = row['documentation_gap']
                count = row['count']
                technical_analysis.append(f"- **{gap}** - {count} conversations need this")
                # Extract specific documentation needs
                if 'guide' in gap.lower():
                    technical_analysis.append(f"  - **Content Need**: Step-by-step user guide")
                if 'instruction' in gap.lower():
                    technical_analysis.append(f"  - **Content Need**: Clear instruction manual")
                if 'knowledge' in gap.lower():
                    technical_analysis.append(f"  - **Content Need**: Knowledge base article")
                technical_analysis.append("")
    
    return "\n".join(technical_analysis)

def main():
    parser = argparse.ArgumentParser(description='Generate executive report from chatbot analysis')
    parser.add_argument('--analysis_dir', default='analysis_out', help='Directory containing analysis results')
    parser.add_argument('--output', default='executive_report.md', help='Output file for the report')
    parser.add_argument('--short', action='store_true', help='Generate concise HTML version (default: detailed markdown)')
    
    args = parser.parse_args()
    
    if args.short:
        generate_concise_report(args.analysis_dir, args.output)
    else:
        generate_executive_report(args.analysis_dir, args.output)

if __name__ == "__main__":
    main()
