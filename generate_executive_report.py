#!/usr/bin/env python3
"""
Executive Report Generator for Chatbot Analysis
Generates a comprehensive, presentation-ready report with key insights and actionable recommendations.
"""

import os
import json
import urllib.parse
import pandas as pd
from collections import Counter
import argparse
import glob

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
    

    
    # Load problem-to-conversation mapping
    mapping_path = os.path.join(analysis_dir, "problem_conversation_mapping.json")
    if os.path.exists(mapping_path):
        with open(mapping_path, 'r', encoding='utf-8') as f:
            raw_mapping = json.load(f)
        
        # Create consolidated mapping for HTML report
        data['problem_mapping'] = create_consolidated_mapping(raw_mapping)
        
        print(f"  ✅  Loaded problem mapping: {mapping_path}")
        print(f"  ✅  Created consolidated mapping in memory")
        
        # Validate the mapping structure
        validate_mapping_structure(data['problem_mapping'])
        
        # Debug: Show what's in the consolidated mapping
        print(f"  🔍  CONSOLIDATED MAPPING DEBUG:")
        print(f"     - Problems keys: {list(data['problem_mapping'].get('problems', {}).keys())[:5]}")
        print(f"     - Successful capabilities keys: {list(data['problem_mapping'].get('successful_capabilities', {}).keys())[:5]}")
        
        # Debug: Show actual data structure
        print(f"  🔍  DATA STRUCTURE DEBUG:")
        print(f"     - data['problem_mapping'] type: {type(data['problem_mapping'])}")
        print(f"     - data['problem_mapping'] keys: {list(data['problem_mapping'].get('problems', {}).keys())[:5]}")
        print(f"     - Sample problems: {list(data['problem_mapping'].get('problems', {}).items())[:2]}")
    else:
        print(f"  ⚠️  Problem mapping not found: {mapping_path}")
        data['problem_mapping'] = {}
    
    # Load weekly data for week filtering
    weekly_data_path = os.path.join(analysis_dir, "weekly_data.json")
    if os.path.exists(weekly_data_path):
        with open(weekly_data_path, 'r', encoding='utf-8') as f:
            weekly_data = json.load(f)
        data['weekly_data'] = weekly_data
        print(f"  ✅  Loaded weekly data: {weekly_data_path}")
        print(f"  📅  Found {len(weekly_data)} weeks of data")
    else:
        print(f"  ⚠️  Weekly data not found: {weekly_data_path}")
        data['weekly_data'] = {}
    
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
    
    # User emotion analysis (only from high-value conversations)
    emotions = [r.get('user_emotion', 'neutral') for r in high_value_results]
    emotion_counts = Counter(emotions)
    
    # Conversation complexity (only from high-value conversations)
    complexities = [r.get('conversation_complexity', 'simple') for r in high_value_results]
    complexity_counts = Counter(complexities)
    
    summary = f"""
# 🤖 Chatbot Performance Executive Summary

## 📊 Overall Performance Metrics
- **Total Conversations Analyzed**: {total_conversations:,}
- **High-Value Conversations**: {high_value:,} ({high_value/total_conversations*100:.1f}%)
- **Low-Value Conversations Filtered**: {low_value:,} ({low_value/total_conversations*100:.1f}%)
- **Error Conversations**: {error_conversations:,} ({error_conversations/total_conversations*100:.1f}%)

## 🎯 High-Value Conversation Analysis
- **Success Rate**: {solve_rate:.1f}% ({solved_conversations:,} conversations)
- **Human Escalation Rate**: {human_rate:.1f}% ({needs_human:,} conversations)
- **Failure Rate**: {100-solve_rate:.1f}% ({high_value-solved_conversations:,} conversations)

## 🚫 Filtered Out Conversations
- **Low-Value Conversations**: {low_value:,} conversations
  - **≤2 user messages** (hard threshold)
  - Greetings only (no actual request)
  - Just cancellations ("Cancel", "No", "Stop")
  - Form submissions without context
- **Incomplete Conversations**: {sum(1 for r in results if r.get('filtered_reason') == 'incomplete-conversation-no-user-input'):,} conversations
  - No user input at all
- **Error Conversations**: {error_conversations:,} conversations
  - Processing errors, file errors

## 😊 User Experience Insights (High-Value Conversations Only)
- **Satisfied Users**: {emotion_counts.get('satisfied', 0):,} ({emotion_counts.get('satisfied', 0)/high_value*100:.1f}% of high-value conversations)
- **Frustrated Users**: {emotion_counts.get('frustrated', 0):,} ({emotion_counts.get('frustrated', 0)/high_value*100:.1f}% of high-value conversations)
- **Neutral Users**: {emotion_counts.get('neutral', 0):,} ({emotion_counts.get('neutral', 0)/high_value*100:.1f}% of high-value conversations)

## 🔍 Conversation Complexity Distribution (High-Value Conversations Only)
- **Simple Conversations**: {complexity_counts.get('simple', 0):,} ({complexity_counts.get('simple', 0)/high_value*100:.1f}% of high-value conversations)
- **Moderate Complexity**: {complexity_counts.get('moderate', 0):,} ({complexity_counts.get('moderate', 0)/high_value*100:.1f}% of high-value conversations)
- **Complex Conversations**: {complexity_counts.get('complex', 0):,} ({complexity_counts.get('complex', 0)/high_value*100:.1f}% of high-value conversations)
"""
    return summary

def generate_problem_analysis(data):
    """Generate detailed problem analysis with statistics."""
    if 'per_chat' not in data:
        return "No analysis data found."
    
    results = data['per_chat']
    total = len(results)
    
    # Failure categories (only from high-value conversations)
    failure_categories = [r.get('failure_category', 'unknown') for r in high_value_results]
    failure_counts = Counter(failure_categories)
    
    # Missing features with priority (only from high-value conversations)
    missing_features = []
    for r in high_value_results:  # Only look at high-value conversations
        if r.get('failure_category') == 'feature-not-supported':
            feature = r.get('missing_feature', 'unknown')
            priority = r.get('feature_priority_score', 1)
            missing_features.append((feature, priority))
    
    # Improvement needs with effort (ONLY actionable improvements, exclude "no improvement needed" responses)
    improvement_needs = []
    for r in high_value_results:  # Only look at high-value conversations
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
    for r in high_value_results:  # Only look at high-value conversations
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
    for r in high_value_results:  # Only look at high-value conversations
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
    """Consolidate similar features into actionable problem categories."""
    feature_lower = feature_name.lower()
    
    # Account and verification issues (broad category)
    if any(term in feature_lower for term in ['account', 'verification', 'permission', 'access', 'login', 'password', 'security']):
        return 'account-access-verification'
    
    # Ad management and campaign issues (broad category)
    if any(term in feature_lower for term in ['ad', 'campaign', 'event', 'approval', 'rejection', 'scheduling', 'pixel', 'tracking']):
        return 'ad-campaign-management'
    
    # API and system integration issues (broad category)
    if any(term in feature_lower for term in ['api', 'system', 'integration', 'clickmagick', 'weebly', 'wix', 'everflow', 'third-party']):
        return 'api-system-integration'
    
    # Live support and human assistance (broad category)
    if any(term in feature_lower for term in ['live', 'agent', 'human', 'support', 'escalation', 'assistance']):
        return 'live-support-escalation'
    
    # UI/UX and workflow improvements (broad category)
    if any(term in feature_lower for term in ['ui', 'interface', 'workflow', 'form', 'desktop', 'navigation', 'user-experience']):
        return 'ui-ux-workflow-improvements'
    
    # Document and billing system issues (broad category)
    if any(term in feature_lower for term in ['invoice', 'billing', 'document', 'ticket', 'payment', 'refund', 'credit']):
        return 'document-billing-payment'
    
    # Technical troubleshooting and complex issues (broad category)
    if any(term in feature_lower for term in ['technical', 'troubleshooting', 'complex', 'debug', 'error', 'issue', 'problem']):
        return 'technical-troubleshooting'
    
    # Information and guidance requests (broad category)
    if any(term in feature_lower for term in ['information', 'guidance', 'instruction', 'help', 'how-to', 'explanation', 'clarification']):
        return 'information-guidance-requests'
    
    # Policy and compliance questions (broad category)
    if any(term in feature_lower for term in ['policy', 'compliance', 'terms', 'rules', 'guidelines', 'requirements']):
        return 'policy-compliance-questions'
    
    # Performance and optimization (broad category)
    if any(term in feature_lower for term in ['performance', 'optimization', 'speed', 'efficiency', 'improvement', 'enhancement']):
        return 'performance-optimization'
    
    # Data and analytics (broad category)
    if any(term in feature_lower for term in ['data', 'analytics', 'reporting', 'metrics', 'statistics', 'insights']):
        return 'data-analytics-reporting'
    
    # Customer service and support (broad category)
    if any(term in feature_lower for term in ['customer', 'service', 'support', 'help', 'assistance', 'contact']):
        return 'customer-service-support'
    
    # Platform and infrastructure (broad category)
    if any(term in feature_lower for term in ['platform', 'infrastructure', 'server', 'hosting', 'deployment', 'scalability']):
        return 'platform-infrastructure'
    
    # Security and privacy (broad category)
    if any(term in feature_lower for term in ['security', 'privacy', 'authentication', 'authorization', 'encryption', 'compliance']):
        return 'security-privacy-compliance'
    
    # Mobile and accessibility (broad category)
    if any(term in feature_lower for term in ['mobile', 'app', 'accessibility', 'responsive', 'device', 'tablet']):
        return 'mobile-accessibility'
    
    # Content and media management (broad category)
    if any(term in feature_lower for term in ['content', 'media', 'image', 'video', 'file', 'upload', 'download']):
        return 'content-media-management'
    
    # Communication and notifications (broad category)
    if any(term in feature_lower for term in ['communication', 'notification', 'email', 'message', 'alert', 'reminder']):
        return 'communication-notifications'
    
    # Search and discovery (broad category)
    if any(term in feature_lower for term in ['search', 'discovery', 'find', 'locate', 'browse', 'explore']):
        return 'search-discovery-navigation'
    
    # Default fallback for very specific features
    return 'other-specific-features'

def create_consolidated_mapping(raw_mapping):
    """Create a consolidated mapping from raw feature names to consolidated names with broader groupings."""
    consolidated_mapping = {
        'problems': {},  # All problems consolidated
        'successful_capabilities': {}
    }
    
    # Track which CSV has been assigned to which problem to avoid duplicates
    csv_assignment = {}  # csv_filename -> (problem_name, sub_problem_name)
    
    # Process problems category
    if 'problems' in raw_mapping:
        print(f"  🔍  Processing {len(raw_mapping['problems'])} raw problems...")
        
        # First pass: collect all problems and their conversations
        problem_candidates = []
        for raw_problem, conversations in raw_mapping['problems'].items():
            consolidated_problem = consolidate_similar_features(raw_problem)
            problem_candidates.append((consolidated_problem, raw_problem, conversations))
        
        # Sort by problem name to ensure consistent ordering
        problem_candidates.sort(key=lambda x: x[0])
        
        # Second pass: assign CSVs to problems, ensuring no duplicates
        for consolidated_problem, raw_problem, conversations in problem_candidates:
            if consolidated_problem not in consolidated_mapping['problems']:
                consolidated_mapping['problems'][consolidated_problem] = {
                    'conversations': [],
                    'sub_problems': {}
                }
            
            # Initialize sub-problem
            if raw_problem not in consolidated_mapping['problems'][consolidated_problem]['sub_problems']:
                consolidated_mapping['problems'][consolidated_problem]['sub_problems'][raw_problem] = []
            
            # Assign conversations to this problem/sub-problem, avoiding duplicates
            for conv in conversations:
                if conv not in csv_assignment:
                    # This CSV hasn't been assigned yet - assign it here
                    csv_assignment[conv] = (consolidated_problem, raw_problem)
                    
                    # Add to main conversations list (avoid duplicates)
                    if conv not in consolidated_mapping['problems'][consolidated_problem]['conversations']:
                        consolidated_mapping['problems'][consolidated_problem]['conversations'].append(conv)
                    
                    # Add to sub-problem
                    if conv not in consolidated_mapping['problems'][consolidated_problem]['sub_problems'][raw_problem]:
                        consolidated_mapping['problems'][consolidated_problem]['sub_problems'][raw_problem].append(conv)
                    
                    print(f"     - Assigned '{conv}' to '{consolidated_problem}' → '{raw_problem}'")
                else:
                    # This CSV was already assigned - check if it should be moved here instead
                    current_problem, current_sub = csv_assignment[conv]
                    if consolidated_problem < current_problem:  # Alphabetical priority
                        # Move CSV to this problem (earlier alphabetically)
                        print(f"     - MOVING '{conv}' from '{current_problem}' to '{consolidated_problem}' (alphabetical priority)")
                        
                        # Remove from old location
                        if conv in consolidated_mapping['problems'][current_problem]['conversations']:
                            consolidated_mapping['problems'][current_problem]['conversations'].remove(conv)
                        if conv in consolidated_mapping['problems'][current_problem]['sub_problems'][current_sub]:
                            consolidated_mapping['problems'][current_problem]['sub_problems'][current_sub].remove(conv)
                        
                        # Add to new location
                        if conv not in consolidated_mapping['problems'][consolidated_problem]['conversations']:
                            consolidated_mapping['problems'][consolidated_problem]['conversations'].append(conv)
                        if conv not in consolidated_mapping['problems'][consolidated_problem]['sub_problems'][raw_problem]:
                            consolidated_mapping['problems'][consolidated_problem]['sub_problems'][raw_problem].append(conv)
                        
                        # Update assignment
                        csv_assignment[conv] = (consolidated_problem, raw_problem)
                    else:
                        print(f"     - SKIPPING '{conv}' (already assigned to '{current_problem}' with higher priority)")
        
        # Third pass: further consolidate sub-problems to create broader groupings
        print(f"\n  🔄  Further consolidating sub-problems for broader groupings...")
        for problem_name, problem_data in list(consolidated_mapping['problems'].items()):
            if len(problem_data['sub_problems']) > 1:
                # Create broader sub-problem groupings
                consolidated_sub_problems = {}
                
                # Group similar sub-problems together
                for sub_name, sub_convs in problem_data['sub_problems'].items():
                    # Create a broader category based on the sub-problem name
                    broad_category = create_broad_sub_category(sub_name)
                    
                    if broad_category not in consolidated_sub_problems:
                        consolidated_sub_problems[broad_category] = []
                    
                    consolidated_sub_problems[broad_category].extend(sub_convs)
                
                # Replace the detailed sub-problems with broader ones
                problem_data['sub_problems'] = consolidated_sub_problems
                
                print(f"  ✅  '{problem_name}': Consolidated {len(problem_data['sub_problems'])} sub-problems into broader groups")
        
        # Clean up empty problems and sub-problems
        problems_to_remove = []
        for problem_name, problem_data in list(consolidated_mapping['problems'].items()):
            if not problem_data['conversations']:
                problems_to_remove.append(problem_name)
                print(f"  🗑️  Removing empty problem: '{problem_name}'")
            else:
                # Clean up empty sub-problems
                sub_problems_to_remove = []
                for sub_name, sub_convs in list(problem_data['sub_problems'].items()):
                    if not sub_convs:
                        sub_problems_to_remove.append(sub_name)
                        print(f"    🗑️  Removing empty sub-problem: '{sub_name}' from '{problem_name}'")
                
                for sub_name in sub_problems_to_remove:
                    del problem_data['sub_problems'][sub_name]
        
        for problem_name in problems_to_remove:
            del consolidated_mapping['problems'][problem_name]
        
        # Verify counts match and no duplicates
        print(f"\n  🔍  FINAL VALIDATION:")
        for consolidated_problem, problem_data in consolidated_mapping['problems'].items():
            total_convs = len(problem_data['conversations'])
            sub_problem_counts = sum(len(convs) for convs in problem_data['sub_problems'].values())
            print(f"  ✅  '{consolidated_problem}': {total_convs} total conversations, {sub_problem_counts} in sub-problems")
            if total_convs != sub_problem_counts:
                print(f"  ⚠️  COUNT MISMATCH: {total_convs} vs {sub_problem_counts}")
            
            # Check for duplicates
            all_convs = []
            for sub_convs in problem_data['sub_problems'].values():
                all_convs.extend(sub_convs)
            unique_convs = set(all_convs)
            if len(all_convs) != len(unique_convs):
                print(f"  ⚠️  DUPLICATES FOUND: {len(all_convs)} total, {len(unique_convs)} unique")
    
    # Process successful capabilities (also ensure no duplicates with problems)
    if 'successful_capabilities' in raw_mapping:
        consolidated_mapping['successful_capabilities'] = {}
        for capability, conversations in raw_mapping['successful_capabilities'].items():
            # Only include CSVs that haven't been assigned to problems
            unassigned_convs = [conv for conv in conversations if conv not in csv_assignment]
            if unassigned_convs:
                consolidated_mapping['successful_capabilities'][capability] = unassigned_convs
                print(f"  ✅  Capability '{capability}': {len(unassigned_convs)} conversations (no overlap with problems)")
            else:
                print(f"  ⚠️  Capability '{capability}': All conversations already assigned to problems")
    
    return consolidated_mapping

def create_broad_sub_category(sub_problem_name):
    """Create actionable sub-categories that clearly indicate what needs to be built or fixed."""
    sub_lower = sub_problem_name.lower()
    
    # API and system access needs
    if any(term in sub_lower for term in ['api', 'system', 'integration', 'access', 'endpoint', 'service', 'backend']):
        return 'need-api-system-access'
    
    # Information and knowledge needs
    if any(term in sub_lower for term in ['information', 'knowledge', 'guide', 'instruction', 'help', 'how-to', 'explanation', 'documentation']):
        return 'need-information-knowledge'
    
    # Permission and access control needs
    if any(term in sub_lower for term in ['permission', 'access', 'authorization', 'role', 'privilege', 'security', 'authentication']):
        return 'need-permission-access-control'
    
    # UI and user experience needs
    if any(term in sub_lower for term in ['ui', 'interface', 'button', 'form', 'workflow', 'navigation', 'user-experience', 'design']):
        return 'need-ui-ux-improvements'
    
    # Data and analytics needs
    if any(term in sub_lower for term in ['data', 'analytics', 'reporting', 'metrics', 'statistics', 'insights', 'dashboard']):
        return 'need-data-analytics'
    
    # Feature and functionality needs
    if any(term in sub_lower for term in ['feature', 'function', 'capability', 'tool', 'option', 'setting', 'configuration']):
        return 'need-feature-functionality'
    
    # Integration and third-party needs
    if any(term in sub_lower for term in ['integration', 'third-party', 'external', 'connect', 'sync', 'import', 'export']):
        return 'need-integration-support'
    
    # Workflow and process needs
    if any(term in sub_lower for term in ['workflow', 'process', 'automation', 'approval', 'review', 'step', 'sequence']):
        return 'need-workflow-automation'
    
    # Support and assistance needs
    if any(term in sub_lower for term in ['support', 'assistance', 'help', 'live', 'agent', 'human', 'escalation']):
        return 'need-human-support'
    
    # Performance and optimization needs
    if any(term in sub_lower for term in ['performance', 'speed', 'efficiency', 'optimization', 'scalability', 'resource']):
        return 'need-performance-optimization'
    
    # Security and compliance needs
    if any(term in sub_lower for term in ['security', 'compliance', 'privacy', 'encryption', 'audit', 'certification']):
        return 'need-security-compliance'
    
    # Mobile and accessibility needs
    if any(term in sub_lower for term in ['mobile', 'app', 'accessibility', 'responsive', 'device', 'tablet', 'mobile-friendly']):
        return 'need-mobile-accessibility'
    
    # Content and media needs
    if any(term in sub_lower for term in ['content', 'media', 'image', 'video', 'file', 'upload', 'download', 'storage']):
        return 'need-content-media-support'
    
    # Communication and notification needs
    if any(term in sub_lower for term in ['communication', 'notification', 'email', 'message', 'alert', 'reminder', 'update']):
        return 'need-communication-notifications'
    
    # Search and discovery needs
    if any(term in sub_lower for term in ['search', 'discovery', 'find', 'locate', 'browse', 'explore', 'filter']):
        return 'need-search-discovery'
    
    # Billing and payment needs
    if any(term in sub_lower for term in ['billing', 'payment', 'invoice', 'refund', 'credit', 'charge', 'subscription']):
        return 'need-billing-payment-system'
    
    # Default fallback for very specific needs
    return 'need-other-specific-features'

def validate_mapping_structure(consolidated_mapping):
    """Validate that the consolidated mapping structure is correct and consistent."""
    print(f"\n🔍  VALIDATING MAPPING STRUCTURE:")
    
    if 'problems' not in consolidated_mapping:
        print("  ❌ No 'problems' category found!")
        return False
    
    all_valid = True
    
    # Check for CSV uniqueness across ALL problems (critical for one-CSV-per-problem rule)
    all_csvs = set()
    csv_locations = {}  # csv -> [problem_names]
    
    for problem_name, problem_data in consolidated_mapping['problems'].items():
        for conv in problem_data['conversations']:
            all_csvs.add(conv)
            if conv not in csv_locations:
                csv_locations[conv] = []
            csv_locations[conv].append(problem_name)
    
    # Check for duplicates across problems
    duplicate_csvs = {csv: problems for csv, problems in csv_locations.items() if len(problems) > 1}
    if duplicate_csvs:
        print(f"  ❌ CRITICAL: Found CSVs assigned to multiple problems:")
        for csv, problems in duplicate_csvs.items():
            print(f"    - '{csv}' appears in: {problems}")
        all_valid = False
    else:
        print(f"  ✅ All CSVs appear in exactly one problem (one-CSV-per-problem rule enforced)")
    
    # Check each problem individually
    for problem_name, problem_data in consolidated_mapping['problems'].items():
        print(f"\n  📊 Problem: '{problem_name}'")
        
        # Check main structure
        if 'conversations' not in problem_data or 'sub_problems' not in problem_data:
            print(f"    ❌ Missing required keys: {list(problem_data.keys())}")
            all_valid = False
            continue
        
        total_conversations = len(problem_data['conversations'])
        sub_problems = problem_data['sub_problems']
        
        print(f"    📁 Total conversations: {total_conversations}")
        print(f"    📂 Sub-problems: {len(sub_problems)}")
        
        # Check each sub-problem
        sub_problem_total = 0
        for sub_problem_name, sub_conversations in sub_problems.items():
            sub_count = len(sub_conversations)
            sub_problem_total += sub_count
            print(f"      - '{sub_problem_name}': {sub_count} conversations")
            
            # Verify no duplicates in sub-problem
            unique_convs = set(sub_conversations)
            if len(unique_convs) != sub_count:
                print(f"        ⚠️  DUPLICATES: {sub_count} total, {len(unique_convs)} unique")
                all_valid = False
        
        # Verify total matches
        if total_conversations != sub_problem_total:
            print(f"    ❌ COUNT MISMATCH: {total_conversations} total vs {sub_problem_total} in sub-problems")
            all_valid = False
        else:
            print(f"    ✅ Counts match perfectly!")
        
        # Verify all conversations in sub-problems are also in main conversations list
        all_sub_convs = set()
        for sub_convs in sub_problems.values():
            all_sub_convs.update(sub_convs)
        
        main_convs = set(problem_data['conversations'])
        if all_sub_convs != main_convs:
            print(f"    ❌ CONVERSATION MISMATCH: Sub-problems contain conversations not in main list")
            all_valid = False
        else:
            print(f"    ✅ All conversations properly accounted for!")
    
    # Check successful capabilities for overlap with problems
    if 'successful_capabilities' in consolidated_mapping:
        print(f"\n  📊 Successful Capabilities:")
        for capability, conversations in consolidated_mapping['successful_capabilities'].items():
            overlap = [conv for conv in conversations if conv in all_csvs]
            if overlap:
                print(f"    ⚠️  '{capability}': {len(overlap)} conversations overlap with problems")
                all_valid = False
            else:
                print(f"    ✅ '{capability}': {len(conversations)} conversations (no overlap with problems)")
    
    if all_valid:
        print(f"\n  🎉 All validation checks passed! Mapping structure is correct.")
    else:
        print(f"\n  ⚠️  Some validation issues found. Check the details above.")
    
    return all_valid

def generate_concise_report(analysis_dir, output_file):
    """Generate a concise executive report for quick reviews."""
    print(f"📊 Loading analysis data from {analysis_dir}...")
    data = load_analysis_data(analysis_dir)
    
    if not data:
        print("❌ No analysis data found!")
        return
    
    print("📝 Generating concise executive report...")
    
    # Count actual raw CSV files in the Bot directory
    bot_dir_pattern = "Bot_714b4955-90a2-4693-9380-a28dffee2e3a_Year_2025_4a86f154be3a4925a510e33bdda399b3 (3)"
    raw_csv_count = 0
    try:
        raw_csv_files = glob.glob(f"{bot_dir_pattern}/*.csv")
        raw_csv_count = len(raw_csv_files)
        print(f"  📁 Found {raw_csv_count} raw CSV files in {bot_dir_pattern}")
    except Exception as e:
        print(f"  ⚠️  Could not count raw CSV files: {e}")
        raw_csv_count = 0
    
    results = data['per_chat']
    analyzed_count = len(results)
    
    # Count conversation quality
    high_value = sum(1 for r in results if r.get('conversation_quality') == 'high-value')
    low_value = sum(1 for r in results if r.get('conversation_quality') == 'low-value')
    error_conversations = sum(1 for r in results if r.get('conversation_quality') == 'error')
    
    # Filter to only high-value conversations for analysis
    high_value_results = [r for r in results if r.get('conversation_quality') == 'high-value']
    
    solved = sum(1 for r in high_value_results if r.get('solved', False))
    needs_human = sum(1 for r in high_value_results if r.get('needs_human', False))
    
    # Calculate other issues (high-value conversations that weren't solved and don't need human)
    other_issues = high_value - solved - needs_human
    
    # Calculate filtered out (raw CSVs that weren't analyzed)
    filtered_out = raw_csv_count - analyzed_count if raw_csv_count > 0 else 0
    
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
        .week-tabs {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-bottom: 30px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 8px;
        }
        .week-tab {
            padding: 10px 20px;
            background: #e9ecef;
            border: 2px solid transparent;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.2s ease;
            font-weight: 500;
        }
        .week-tab:hover {
            background: #dee2e6;
            transform: translateY(-2px);
        }
        .week-tab.active {
            background: #667eea;
            color: white;
            border-color: #495057;
        }
        .week-tab.multi-select {
            background: #28a745;
            color: white;
        }
        .week-tab.multi-select:hover {
            background: #218838;
        }
        .week-selection-info {
            margin-bottom: 20px;
            padding: 15px;
            background: #e3f2fd;
            border-radius: 8px;
            border-left: 4px solid #2196f3;
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
        
        .conversation-preview {
            font-size: 0.8em;
            color: #6c757d;
            margin-top: 5px;
            font-style: italic;
        }
        
        .filtering-summary {
            display: flex;
            justify-content: space-around;
            gap: 20px;
            margin-top: 15px;
        }
        
        .filtering-item {
            text-align: center;
            flex: 1;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
            border: 1px solid #dee2e6;
        }
        
        .filtering-number {
            font-size: 1.8em;
            font-weight: bold;
            color: #28a745;
            margin-bottom: 8px;
        }
        
        .filtering-label {
            font-weight: bold;
            color: #495057;
            margin-bottom: 5px;
        }
        
        .filtering-description {
            font-size: 0.85em;
            color: #6c757d;
            line-height: 1.3;
        }
        
        .conversation-modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.5);
        }
        
        .conversation-modal-content {
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
        
        .conversation-modal-close {
            color: #aaa;
            float: right;
            font-size: 28px;
            font-weight: bold;
            cursor: pointer;
            position: absolute;
            right: 20px;
            top: 15px;
        }
        
        .conversation-modal-close:hover {
            color: #000;
        }
        
        .conversation-list {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 15px;
            margin: 15px 0;
            max-height: 400px;
            overflow-y: auto;
        }
        
        .conversation-item {
            background: white;
            padding: 10px;
            margin: 8px 0;
            border-radius: 6px;
            border-left: 4px solid #667eea;
            font-family: monospace;
            font-size: 0.9em;
        }
        
        .conversation-groups {
            max-height: 400px;
            overflow-y: auto;
        }
        
        .sub-problem-group {
            margin: 15px 0;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
            border: 1px solid #e9ecef;
        }
        
        .sub-problem-title {
            margin: 0 0 10px 0;
            color: #495057;
            font-size: 1.1em;
            font-weight: 600;
            border-bottom: 2px solid #dee2e6;
            padding-bottom: 5px;
        }
        
        .conversation-files {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        
        .conversation-file {
            padding: 8px 12px;
            background: white;
            border-radius: 6px;
            border: 1px solid #dee2e6;
            cursor: pointer;
            transition: all 0.2s ease;
            font-family: monospace;
            font-size: 0.9em;
        }
        
        .conversation-file:hover {
            background: #e3f2fd;
            border-color: #2196f3;
            transform: translateX(5px);
        }
        
        /* Conversation History Styles */
        .conversation-header-info {
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            border-left: 4px solid #667eea;
        }
        
        .conversation-header-info h3 {
            margin: 0 0 15px 0;
            color: #495057;
        }
        
        .conversation-header-info p {
            margin: 5px 0;
            color: #6c757d;
        }
        
        .conversation-messages {
            display: flex;
            flex-direction: column;
            gap: 15px;
        }
        
        .message {
            background: white;
            border-radius: 12px;
            padding: 8px 12px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            margin: 4px 0;
            max-width: 70%;
            word-wrap: break-word;
        }
        
        .message.user-message {
            background: linear-gradient(135deg, #007bff 0%, #0056b3 100%);
            color: white;
            margin-left: auto;
            margin-right: 0;
            border-bottom-right-radius: 4px;
        }
        
        .message.bot-message {
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            color: #212529;
            margin-left: 0;
            margin-right: auto;
            border-bottom-left-radius: 4px;
        }
        
        .message.system-message {
            background: linear-gradient(135deg, #6c757d 0%, #495057 100%);
            color: white;
            margin: 8px auto;
            text-align: center;
            max-width: 50%;
        }
        
        .message-header {
            display: flex;
            align-items: center;
            gap: 6px;
            margin-bottom: 4px;
            font-size: 0.75em;
        }
        
        .speaker-icon {
            font-size: 1em;
        }
        
        .speaker-name {
            font-weight: 600;
            opacity: 0.8;
        }
        
        .timestamp {
            opacity: 0.7;
            font-size: 0.75em;
            margin-left: auto;
        }
        
        .user-message .speaker-name,
        .user-message .timestamp {
            color: rgba(255, 255, 255, 0.9);
        }
        
        .bot-message .speaker-name,
        .bot-message .timestamp {
            color: #6c757d;
        }
        
        .message-content {
            color: #212529;
            line-height: 1.5;
            white-space: pre-wrap;
            word-wrap: break-word;
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
            <!-- Week Selection Tabs -->
            <div class="week-tabs" id="weekTabs">
                <!-- Week tabs will be populated by JavaScript -->
            </div>
            
            <div class="week-selection-info" id="weekSelectionInfo">
                <strong>📅 Week Selection:</strong> Click on week tabs above to filter data. You can select multiple weeks by holding Ctrl/Cmd while clicking.
            </div>
            
            <div class="section">
                <h2>📊 Key Metrics</h2>
                <div class="metrics-grid">
                    <div class="metric-card" data-metric="totalCount">
                        <div class="metric-number">""" + f"{raw_csv_count:,}" + """</div>
                        <div class="metric-label">Total conversations</div>
                    </div>
                    <div class="metric-card" data-metric="analyzedCount">
                        <div class="metric-number">""" + f"{analyzed_count:,}" + """</div>
                        <div class="metric-label">Analyzed</div>
                    </div>
                    <div class="metric-card" data-metric="solvedCount">
                        <div class="metric-number">""" + f"{solved:,}" + """</div>
                        <div class="metric-label">Chatbot successes</div>
                    </div>
                    <div class="metric-card" data-metric="needsHumanCount">
                        <div class="metric-number">""" + f"{needs_human:,}" + """</div>
                        <div class="metric-label">Need Human Assistance</div>
                    </div>
                    <div class="metric-card" data-metric="filteredCount">
                        <div class="metric-number">""" + f"{filtered_out:,}" + """</div>
                        <div class="metric-label">Filtered Out (Too Short/Greetings)</div>
                    </div>
                </div>
            </div>



            <div class="section">
                <h2>🚨 PROBLEMS THE CHATBOT CANNOT SOLVE</h2>
                
                <div class="issue-list">"""
    
    # Check if we have grouped problems from the analysis
    if 'grouped_problems' in data.get('problem_mapping', {}) and data['problem_mapping']['grouped_problems']:
        # Use pre-computed grouped problems from Python analysis
        grouped_problems = data['problem_mapping']['grouped_problems']
        
        # Sort categories by total conversations affected
        categories = sorted(grouped_problems.keys(), 
                          key=lambda cat: grouped_problems[cat]['total_conversations'], 
                          reverse=True)
        
        for category in categories:
            category_data = grouped_problems[category]
            
            # Create category header
            html_report += f"""
                <div class="category-header" style="background: #e9ecef; padding: 12px 15px; margin: 20px 0 10px 0; border-radius: 6px; border-left: 4px solid #6c757d; font-weight: bold; color: #495057; font-size: 1.1em;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span>{category}</span>
                        <span style="background: #6c757d; color: white; padding: 4px 8px; border-radius: 12px; font-size: 0.8em;">
                            {category_data['total_conversations']} conversations
                        </span>
                </div>
                    <div style="font-size: 0.9em; font-weight: normal; margin-top: 5px; color: #6c757d;">
                        {category_data['summary']}
                    </div>
                </div>"""
            
            # Display problems in this category
            problems = list(category_data['problems'].items())
            problems.sort(key=lambda x: len(x[1]), reverse=True)  # Sort by conversation count
            
            for problem, conversations in problems:
                count = len(conversations)
                problem_data = {'conversations': conversations}
                popup_json = json.dumps(problem_data, ensure_ascii=False)
                popup_data = urllib.parse.quote(popup_json)
                
                html_report += f"""
                <div class="feature-item clickable-item" data-problem="{problem}" data-popup="{popup_data}" data-count="{count}" style="margin-left: 20px;">
                    <span class="feature-count">{count:,}</span>
                    <strong>{problem}</strong>
                    <div class="conversation-preview">Click to see {count} conversations</div>
                    </div>"""
    
    else:
        # Fallback to old method if no grouped problems
        all_problems = []
        if 'problems' in data.get('problem_mapping', {}):
            for problem, problem_data in data['problem_mapping']['problems'].items():
                if isinstance(problem_data, dict) and 'conversations' in problem_data:
                    count = len(problem_data['conversations'])
                    all_problems.append((problem, count, problem_data))
        
        # Sort by count (most frequent problems first)
        all_problems.sort(key=lambda x: x[1], reverse=True)
        
        if all_problems:
            for problem, count, problem_data in all_problems[:15]:  # Top 15 problems
                # Verify count consistency
                sub_problem_total = sum(len(convs) for convs in problem_data.get('sub_problems', {}).values())
                if count != sub_problem_total:
                    print(f"  ⚠️  COUNT MISMATCH in HTML: '{problem}' shows {count} but sub-problems total {sub_problem_total}")
                
                # Encode JSON for safe embedding in data- attribute
                popup_json = json.dumps(problem_data, ensure_ascii=False)
                popup_data = urllib.parse.quote(popup_json)
                html_report += f"""
                    <div class="feature-item clickable-item" data-problem="{problem}" data-popup="{popup_data}" data-count="{count}">
                        <span class="feature-count">{count:,}</span>
                        <strong>{problem}</strong>
                        <div class="conversation-preview">Click to see {count} conversations grouped by sub-problems (total: {sub_problem_total})</div>
                    </div>"""
    
    html_report += """
                </div>
            </div>

            <div class="section">
                <h2>✅ KEY CHATBOT STRENGTHS</h2>
                
                <div class="issue-list">"""
    
    # Create a prioritized list of key capabilities (ranked by importance, not count)
    key_capabilities = []
    capability_priority = {
        'bot-handled-perfectly': 1,  # Most important - shows overall success
        'account-verification-guidance': 2,  # Core business function
        'campaign-activation-instructions': 3,  # Core business function  
        'policy-clarification': 4,  # Important for compliance
        'multi-step-instruction': 5,  # Shows complexity handling
        'problem-solving': 6,  # General capability
    }
    
    if 'successful_capabilities' in data['problem_mapping'] and data['problem_mapping']['successful_capabilities']:
        # Collect and prioritize capabilities
        for capability, conversations in data['problem_mapping']['successful_capabilities'].items():
            if capability and conversations:
                priority = capability_priority.get(capability, 99)  # Default low priority
                key_capabilities.append((priority, capability, conversations))
        
        # Sort by priority (lower number = higher priority)
        key_capabilities.sort(key=lambda x: x[0])
        
        # Show only top 5 most important capabilities
        for priority, capability, conversations in key_capabilities[:5]:
            # Create popup data similar to problems section
            popup_data = {
                'conversations': conversations,
                'sub_problems': {capability: conversations},
                'type': 'success'
            }
            popup_json = urllib.parse.quote(json.dumps(popup_data))
            
            # Create concise, meaningful display names
            display_names = {
                'bot-handled-perfectly': 'Perfect Problem Resolution',
                'account-verification-guidance': 'Account Verification Support',
                'campaign-activation-instructions': 'Campaign Setup Guidance',
                'policy-clarification': 'Policy & Rules Clarification',
                'multi-step-instruction': 'Complex Multi-Step Tasks',
                'problem-solving': 'General Problem Solving'
            }
            
            display_name = display_names.get(capability, capability.replace('-', ' ').title())
            
            html_report += f"""
                <div class="feature-item clickable-item" data-problem="{capability}" data-popup="{popup_json}" data-count="{len(conversations)}">
                    <span class="feature-count">✓</span>
                    <strong>{display_name}</strong>
                    <div class="conversation-preview">Proven capability - {len(conversations)} examples</div>
                    </div>"""
    
    # If no successes found
    if not key_capabilities:
            html_report += """
                    <div class="feature-item">
                    <span class="feature-count">⚠️</span>
                    <strong>Limited Success Data</strong>
                    <div class="conversation-preview">Few conversations were marked as successfully handled</div>
                    </div>"""
    
    html_report += """
                </div>
                </div>


        </div>
    </div>
    
    <!-- Conversation Modal -->
    <div id="conversationModal" class="conversation-modal">
        <div class="conversation-modal-content">
            <span class="conversation-modal-close" onclick="closeConversationModal()">&times;</span>
            <h2 id="modalTitle">Conversation Details</h2>
            <div id="modalContent">
                <div class="conversation-list" id="conversationList">
                    <!-- Conversations will be populated here -->
                </div>
            </div>
        </div>
    </div>
    
    <!-- Test button to verify JavaScript is working -->
    <div style="text-align: center; margin: 20px; padding: 20px; background: #f8f9fa; border-radius: 8px;">
        <button onclick="alert('JavaScript is working!')" style="padding: 10px 20px; background: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer;">
            Test JavaScript
        </button>
        <button onclick="testModal()" style="padding: 10px 20px; background: #28a745; color: white; border: none; border-radius: 5px; cursor: pointer; margin-left: 10px;">
            Test Modal
        </button>
        <p style="margin-top: 10px; font-size: 0.9em; color: #666;">Click these buttons to verify JavaScript and modal are working</p>
    </div>
    
    <!-- Embedded Weekly Data -->
    <script>
        window.embeddedWeeklyData = """ + json.dumps(data.get('weekly_data', {}), ensure_ascii=False) + """;
    </script>
    
    <script>
        console.log('JavaScript loaded successfully');
        
        // Week filtering functionality
        let weeklyData = {};
        let selectedWeeks = new Set();
        let allData = null;
        
        // Initialize week filtering when page loads
        document.addEventListener('DOMContentLoaded', function() {
            initializeWeekFiltering();
        });
        
        function initializeWeekFiltering() {
            // Weekly data is embedded in the HTML, no need to fetch
            if (window.embeddedWeeklyData) {
                weeklyData = window.embeddedWeeklyData;
                allData = window.embeddedWeeklyData;
                createWeekTabs();
                updateDisplay();
            } else {
                console.log('Weekly data not available, using combined data only');
                weeklyData = {};
                allData = null;
                createWeekTabs();
                updateDisplay();
            }
        }
        
        function createWeekTabs() {
            const tabsContainer = document.getElementById('weekTabs');
            if (!tabsContainer) return;
            
            // Clear existing tabs
            tabsContainer.innerHTML = '';
            
            // Add "All Weeks" tab
            const allWeeksTab = document.createElement('div');
            allWeeksTab.className = 'week-tab active';
            allWeeksTab.textContent = '📅 All Weeks';
            allWeeksTab.onclick = () => selectAllWeeks();
            tabsContainer.appendChild(allWeeksTab);
            
            // Add individual week tabs
            if (weeklyData && Object.keys(weeklyData).length > 0) {
                const sortedWeeks = Object.keys(weeklyData).sort();
                sortedWeeks.forEach(weekKey => {
                    if (weekKey === 'unknown') return; // Skip unknown week
                    
                    const weekInfo = weeklyData[weekKey].week_info;
                    const weekTab = document.createElement('div');
                    weekTab.className = 'week-tab';
                    weekTab.textContent = weekInfo.display_name;
                    weekTab.onclick = (e) => toggleWeekSelection(weekKey, e);
                    weekTab.setAttribute('data-week', weekKey);
                    tabsContainer.appendChild(weekTab);
                });
            }
        }
        
        function selectAllWeeks() {
            selectedWeeks.clear();
            document.querySelectorAll('.week-tab').forEach(tab => {
                tab.classList.remove('active', 'multi-select');
            });
            document.querySelector('.week-tab').classList.add('active');
            updateDisplay();
        }
        
        function toggleWeekSelection(weekKey, event) {
            const tab = event.target;
            const isCtrlPressed = event.ctrlKey || event.metaKey;
            
            if (isCtrlPressed) {
                // Multi-select mode
                if (selectedWeeks.has(weekKey)) {
                    selectedWeeks.delete(weekKey);
                    tab.classList.remove('multi-select');
                } else {
                    selectedWeeks.add(weekKey);
                    tab.classList.add('multi-select');
                }
                
                // Update "All Weeks" tab
                document.querySelector('.week-tab').classList.remove('active');
                
                // Update display
                updateDisplay();
            } else {
                // Single select mode
                selectedWeeks.clear();
                selectedWeeks.add(weekKey);
                
                // Update tab states
                document.querySelectorAll('.week-tab').forEach(t => {
                    t.classList.remove('active', 'multi-select');
                });
                tab.classList.add('active');
                
                updateDisplay();
            }
        }
        
        function updateDisplay() {
            const infoDiv = document.getElementById('weekSelectionInfo');
            if (!infoDiv) return;
            
            if (selectedWeeks.size === 0) {
                // Show all weeks
                infoDiv.innerHTML = '<strong>📅 Week Selection:</strong> Showing data from all weeks combined.';
                updateMetrics(allData);
            } else if (selectedWeeks.size === 1) {
                // Show single week
                const weekKey = Array.from(selectedWeeks)[0];
                const weekInfo = weeklyData[weekKey].week_info;
                infoDiv.innerHTML = `<strong>📅 Week Selection:</strong> Showing data from week: <strong>${weekInfo.display_name}</strong>`;
                
                // Create a data object with the week's conversations and rebuild problem mapping
                const weekData = {
                    per_chat: weeklyData[weekKey].per_chat || []
                };
                
                // Rebuild problem mapping for this specific week
                rebuildProblemMapping(weekData);
                
                updateMetrics(weekData);
            } else {
                // Show multiple weeks
                const weekNames = Array.from(selectedWeeks).map(key => weeklyData[key].week_info.display_name);
                infoDiv.innerHTML = `<strong>📅 Week Selection:</strong> Showing combined data from ${selectedWeeks.size} weeks: <strong>${weekNames.join(', ')}</strong>`;
                
                // Combine data from multiple weeks
                const combinedData = combineWeeklyData(Array.from(selectedWeeks));
                updateMetrics(combinedData);
            }
        }
        
        function combineWeeklyData(weekKeys) {
            const combined = {
                per_chat: []
            };
            
            weekKeys.forEach(weekKey => {
                if (weeklyData[weekKey] && weeklyData[weekKey].per_chat) {
                    combined.per_chat.push(...weeklyData[weekKey].per_chat);
                }
            });
            
            // Rebuild problem mapping for combined data
            rebuildProblemMapping(combined);
            
            return combined;
        }
        
        function rebuildProblemMapping(data) {
            console.log('Rebuilding problem mapping for filtered data...');
            
            if (!data || !data.per_chat) return;
            
            // Rebuild problem mapping from scratch based on filtered conversations
            const problems = {};
            const successful_capabilities = {};
            
            data.per_chat.forEach(conversation => {
                // Map problems
                const problems_found = [];
                
                // Check for missing features
                if (conversation.failure_category === "feature-not-supported") {
                    const missing_feature = conversation.missing_feature;
                    if (missing_feature && missing_feature !== "unknown-feature") {
                        problems_found.push(missing_feature);
                    }
                }
                
                // Check for improvement needs
                const improvement = conversation.specific_improvement_needed;
                if (improvement && improvement !== "no-improvement-needed") {
                    // Filter out success indicators
                    if (!improvement.includes('bot-handled-perfectly') && 
                        !improvement.includes('user-request-fulfilled') && 
                        !improvement.includes('conversation-successful') &&
                        !improvement.includes('bot-solved-problem') && 
                        !improvement.includes('user-satisfied') && 
                        !improvement.includes('conversation-completed-successfully')) {
                        problems_found.push(improvement);
                    }
                }
                
                // Check for escalation triggers
                const escalation_triggers = conversation.escalation_triggers || [];
                escalation_triggers.forEach(trigger => {
                    if (trigger && !trigger.includes('none') && 
                        !trigger.includes('no-escalation-needed') && 
                        !trigger.includes('bot-solved-problem') && 
                        !trigger.includes('user-satisfied') &&
                        !trigger.includes('conversation-completed-successfully') && 
                        !trigger.includes('user-abandoned-conversation')) {
                        problems_found.push(trigger);
                    }
                });
                
                // Check for error patterns
                const error_patterns = conversation.error_patterns || [];
                error_patterns.forEach(error => {
                    if (error && !error.includes('none') && 
                        !error.includes('no-errors-detected') && 
                        !error.includes('system-functioning-perfectly') &&
                        !error.includes('all-requests-successful') && 
                        !error.includes('no-technical-issues') && 
                        !error.includes('conversation-abandoned')) {
                        problems_found.push(error);
                    }
                });
                
                // Add problems to mapping
                problems_found.forEach(problem => {
                    if (!problems[problem]) {
                        problems[problem] = [];
                    }
                    problems[problem].push(conversation.file);
                });
                
                // Map successful capabilities
                if (conversation.solved) {
                    // Add demonstrated skills
                    const skills = conversation.demonstrated_skills || [];
                    skills.forEach(skill => {
                        if (skill) {
                            if (!successful_capabilities[skill]) {
                                successful_capabilities[skill] = [];
                            }
                            successful_capabilities[skill].push(conversation.file);
                        }
                    });
                    
                    // Add success indicators
                    const improvement = conversation.specific_improvement_needed || "";
                    if (improvement && (improvement.includes('bot-handled-perfectly') || 
                        improvement.includes('user-request-fulfilled') || 
                        improvement.includes('conversation-successful') ||
                        improvement.includes('bot-solved-problem') || 
                        improvement.includes('user-satisfied') || 
                        improvement.includes('conversation-completed-successfully'))) {
                        
                        const success_type = "bot-handled-perfectly";
                        if (!successful_capabilities[success_type]) {
                            successful_capabilities[success_type] = [];
                        }
                        successful_capabilities[success_type].push(conversation.file);
                    }
                }
            });
            
            // Update the data object with rebuilt mapping
            data.problem_mapping = {
                problems: problems,
                successful_capabilities: successful_capabilities
            };
            
            console.log('Problem mapping rebuilt:', {
                problems: Object.keys(problems).length,
                capabilities: Object.keys(successful_capabilities).length
            });
        }
        
        function updateMetrics(data) {
            if (!data || !data.per_chat) return;
            
            // Update metrics display based on filtered data
            const results = data.per_chat;
            const analyzed_count = results.length;
            const high_value = results.filter(r => r.conversation_quality === 'high-value').length;
            const solved = results.filter(r => r.solved).length;
            const needs_human = results.filter(r => r.needs_human).length;
            
            // Update metric cards
            updateMetricCard('analyzedCount', analyzed_count);
            updateMetricCard('solvedCount', solved);
            updateMetricCard('needsHumanCount', needs_human);
            
            // Note: totalCount and filteredCount are static and don't change with week selection
            // They represent the overall dataset size
            
            // Update problems and capabilities sections
            updateProblemsSection(data);
            updateCapabilitiesSection(data);
        }
        
        function updateMetricCard(id, value) {
            const card = document.querySelector(`[data-metric="${id}"]`);
            if (card) {
                const numberElement = card.querySelector('.metric-number');
                if (numberElement) {
                    numberElement.textContent = value.toLocaleString();
                }
            }
        }
        
        function updateProblemsSection(data) {
            console.log('Updating problems section with filtered data...');
            
            if (!data || !data.problem_mapping || !data.problem_mapping.problems) return;
            
            // Find the problems section by looking for the heading text
            const headings = document.querySelectorAll('.section h2');
            let problemsSection = null;
            for (const heading of headings) {
                if (heading.textContent.includes('PROBLEMS THE CHATBOT CANNOT SOLVE')) {
                    problemsSection = heading.closest('.section');
                    break;
                }
            }
            
            if (!problemsSection) return;
            
            const issueList = problemsSection.querySelector('.issue-list');
            if (!issueList) return;
            
            // Clear existing problems
            issueList.innerHTML = '';
            
            // Get all problems from the filtered data
            const allProblems = [];
            for (const [problem, conversations] of Object.entries(data.problem_mapping.problems)) {
                if (conversations && conversations.length > 0) {
                    allProblems.push([problem, conversations.length, { conversations: conversations }]);
                }
            }
            
            // Sort by count (most frequent problems first)
            allProblems.sort((a, b) => b[1] - a[1]);
            
            // Display top 15 problems
            allProblems.slice(0, 15).forEach(([problem, count, problemData]) => {
                const popup_json = JSON.stringify(problemData, null, 2);
                const popup_data = encodeURIComponent(popup_json);
                
                const problemDiv = document.createElement('div');
                problemDiv.className = 'feature-item clickable-item';
                problemDiv.setAttribute('data-problem', problem);
                problemDiv.setAttribute('data-popup', popup_data);
                problemDiv.setAttribute('data-count', count);
                problemDiv.onclick = () => showConversations(problem, popup_data, count);
                
                problemDiv.innerHTML = `
                    <span class="feature-count">${count.toLocaleString()}</span>
                    <strong>${problem}</strong>
                    <div class="conversation-preview">Click to see ${count} conversations</div>
                `;
                
                issueList.appendChild(problemDiv);
            });
            
            if (allProblems.length === 0) {
                issueList.innerHTML = `
                    <div class="feature-item">
                        <span class="feature-count">0</span>
                        <strong>No problems identified in selected week(s)</strong>
                    </div>
                `;
            }
        }
        
        function updateCapabilitiesSection(data) {
            console.log('Updating capabilities section with filtered data...');
            
            if (!data || !data.problem_mapping || !data.problem_mapping.successful_capabilities) return;
            
            // Find the capabilities section by looking for the heading text
            const headings = document.querySelectorAll('.section h2');
            let capabilitiesSection = null;
            for (const heading of headings) {
                if (heading.textContent.includes('KEY CHATBOT STRENGTHS')) {
                    capabilitiesSection = heading.closest('.section');
                    break;
                }
            }
            
            if (!capabilitiesSection) return;
            
            const issueList = capabilitiesSection.querySelector('.issue-list');
            if (!issueList) return;
            
            // Clear existing capabilities
            issueList.innerHTML = '';
            
            // Create a prioritized list of key capabilities
            const keyCapabilities = [];
            const capabilityPriority = {
                'bot-handled-perfectly': 1,
                'account-verification-guidance': 2,
                'campaign-activation-instructions': 3,
                'policy-clarification': 4,
                'multi-step-instruction': 5,
                'problem-solving': 6,
            };
            
            for (const [capability, conversations] of Object.entries(data.problem_mapping.successful_capabilities)) {
                if (capability && conversations && conversations.length > 0) {
                    const priority = capabilityPriority[capability] || 99;
                    keyCapabilities.push([priority, capability, conversations]);
                }
            }
            
            // Sort by priority (lower number = higher priority)
            keyCapabilities.sort((a, b) => a[0] - b[0]);
            
            // Show only top 5 most important capabilities
            keyCapabilities.slice(0, 5).forEach(([priority, capability, conversations]) => {
                const popupData = {
                    conversations: conversations,
                    sub_problems: { capability: conversations },
                    type: 'success'
                };
                const popup_json = encodeURIComponent(JSON.stringify(popupData));
                
                const displayNames = {
                    'bot-handled-perfectly': 'Perfect Problem Resolution',
                    'account-verification-guidance': 'Account Verification Support',
                    'campaign-activation-instructions': 'Campaign Setup Guidance',
                    'policy-clarification': 'Policy & Rules Clarification',
                    'multi-step-instruction': 'Complex Multi-Step Tasks',
                    'problem-solving': 'General Problem Solving'
                };
                
                const displayName = displayNames[capability] || capability.replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                
                const capabilityDiv = document.createElement('div');
                capabilityDiv.className = 'feature-item clickable-item';
                capabilityDiv.setAttribute('data-problem', capability);
                capabilityDiv.setAttribute('data-popup', popup_json);
                capabilityDiv.setAttribute('data-count', conversations.length);
                capabilityDiv.onclick = () => showConversations(capability, popup_json, conversations.length);
                
                capabilityDiv.innerHTML = `
                    <span class="feature-count">✓</span>
                    <strong>${displayName}</strong>
                    <div class="conversation-preview">Proven capability - ${conversations.length} examples</div>
                `;
                
                issueList.appendChild(capabilityDiv);
            });
            
            if (keyCapabilities.length === 0) {
                issueList.innerHTML = `
                    <div class="feature-item">
                        <span class="feature-count">⚠️</span>
                        <strong>Limited Success Data</strong>
                        <div class="conversation-preview">Few conversations were marked as successfully handled in selected week(s)</div>
                    </div>
                `;
            }
        }
        
        // Delegate click handling for all feature items
        document.addEventListener('click', function(e) {
            console.log('Click event detected on:', e.target);
            console.log('Target classes:', e.target.className);
            console.log('Closest feature-item:', e.target.closest('.feature-item.clickable-item'));
            
            const featureItem = e.target.closest('.feature-item.clickable-item');
            if (!featureItem) {
                console.log('No clickable feature item found');
                return;
            }
            
            console.log('Found clickable feature item:', featureItem);
            const problem = featureItem.getAttribute('data-problem');
            const encoded = featureItem.getAttribute('data-popup') || '';
            const countAttr = featureItem.getAttribute('data-count') || '0';
            
            console.log('Problem:', problem);
            console.log('Encoded popup data length:', encoded.length);
            console.log('Count:', countAttr);
            
            try {
                const popupData = decodeURIComponent(encoded);
                console.log('Decoded popup data length:', popupData.length);
                showConversations(problem || 'Unknown', popupData, parseInt(countAttr, 10) || 0);
            } catch (err) {
                console.error('Failed to decode popup data', err);
                alert('Unable to open conversations for this item.');
            }
        }, false);
        
        function showConversations(problem, popupData, count) {
            console.log('showConversations called with:', { problem, popupData, count });
            try {
                const data = JSON.parse(popupData);
                console.log('Parsed data:', data);
                
                const modal = document.getElementById('conversationModal');
                const modalTitle = document.getElementById('modalTitle');
                const conversationListDiv = document.getElementById('conversationList');
                
                // Set title
                modalTitle.textContent = `${problem} (${count} conversations)`;
                
                // Build HTML content with sub-problems grouped
                let html = '<div class="conversation-groups">';
                
                if (data.sub_problems) {
                    console.log('Using sub_problems structure');
                    // Group by sub-problems
                    for (const [subProblem, conversations] of Object.entries(data.sub_problems)) {
                        // Deduplicate conversations and limit to 10
                        const uniqueConversations = [...new Set(conversations)].slice(0, 10);
                        const totalCount = conversations.length;
                        
                        html += `<div class="sub-problem-group">
                            <h4 class="sub-problem-title">${subProblem} (${totalCount} conversations)</h4>
                            <div class="conversation-files">`;
                        
                        uniqueConversations.forEach(conv => {
                            html += `<div class="conversation-file" onclick="showConversationHistory('${conv}')">
                                📄 ${conv}
                            </div>`;
                        });
                        
                        if (totalCount > 10) {
                            html += `<div class="conversation-file-more" style="text-align: center; color: #6c757d; font-style: italic; padding: 8px;">
                                ... and ${totalCount - 10} more conversations
                            </div>`;
                        }
                        
                        html += `</div></div>`;
                    }
                } else if (data.conversations) {
                    console.log('Using conversations structure');
                    // Fallback to simple list - also deduplicate and limit
                    const uniqueConversations = [...new Set(data.conversations)].slice(0, 10);
                    const totalCount = data.conversations.length;
                    
                    uniqueConversations.forEach(conv => {
                        html += `<div class="conversation-file" onclick="showConversationHistory('${conv}')">
                            📄 ${conv}
                        </div>`;
                    });
                    
                    if (totalCount > 10) {
                        html += `<div class="conversation-file-more" style="text-align: center; color: #6c757d; font-style: italic; padding: 8px;">
                            ... and ${totalCount - 10} more conversations
                        </div>`;
                    }
                } else {
                    console.log('No valid data structure found');
                }
                
                html += '</div>';
                conversationListDiv.innerHTML = html;
                modal.style.display = 'block';
                
            } catch (error) {
                console.error('Error parsing popup data:', error);
                console.log('Raw popup data:', popupData);
                // Fallback to simple display
                conversationListDiv.innerHTML = popupData;
                modal.style.display = 'block';
            }
        }
        
        function showConversationHistory(filename) {
            // Create a new modal for conversation history
            const historyModal = document.createElement('div');
            historyModal.id = 'historyModal';
            historyModal.className = 'conversation-modal';
            historyModal.style.display = 'block';
            
            // Create modal content
            historyModal.innerHTML = `
                <div class="conversation-modal-content" style="max-width: 90%; max-height: 90%;">
                    <span class="conversation-modal-close" onclick="closeHistoryModal()">&times;</span>
                    <h2>📄 Conversation History: ${filename}</h2>
                    <div id="conversationContent" style="max-height: 70vh; overflow-y: auto; padding: 20px; background: #f8f9fa; border-radius: 8px; margin-top: 20px;">
                        <div style="text-align: center; color: #6c757d;">
                            <p>Loading conversation data...</p>
                            <p>Searching for CSV file...</p>
                </div>
            </div>
                </div>
            `;
            
            document.body.appendChild(historyModal);
            
            // Try to load CSV content from the analysis_out directory
            loadCSVContent(filename);
        }
        
        function loadCSVContent(filename) {
            // Try to find the CSV file in the Bot directory
            const csvPath = `Bot_714b4955-90a2-4693-9380-a28dffee2e3a_Year_2025_4a86f154be3a4925a510e33bdda399b3 (3)/${filename}`;
            
            fetch(csvPath)
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                    }
                    return response.text();
                })
                .then(csvText => {
                    displayConversationHistory(csvText, filename);
                })
                .catch(error => {
                    console.error('Error loading CSV:', error);
                    document.getElementById('conversationContent').innerHTML = `
                        <div style="text-align: center; color: #dc3545; padding: 20px;">
                            <h3>❌ Error Loading Conversation</h3>
                            <p><strong>File:</strong> ${filename}</p>
                            <p><strong>Error:</strong> ${error.message}</p>
                            <p style="font-size: 0.9em; margin-top: 15px;">
                                The CSV file may not be accessible from the browser.<br>
                                Try opening the HTML file from the same directory as the analysis_out folder.
                            </p>
                    </div>
                    `;
                });
        }
        
        function displayConversationHistory(csvText, filename) {
            try {
                // Parse CSV content
                const lines = csvText.split('\\n').filter(line => line.trim());
                if (lines.length === 0) {
                    throw new Error('Empty CSV file');
                }
                
                // Parse headers (assuming first line is headers)
                const headers = lines[0].split(',').map(h => h.trim().replace(/"/g, ''));
                
                // Parse data rows
                const conversations = [];
                for (let i = 1; i < lines.length; i++) {
                    const values = parseCSVLine(lines[i]);
                    if (values.length >= headers.length) {
                        const conversation = {};
                        headers.forEach((header, index) => {
                            conversation[header] = values[index] || '';
                        });
                        // Only add messages that have actual content
                        if (conversation['Message'] && conversation['Message'].trim()) {
                            conversations.push(conversation);
                        }
                    }
                }
                
                // Display conversation history beautifully
                const contentDiv = document.getElementById('conversationContent');
                contentDiv.innerHTML = `
                    <div class="conversation-header-info">
                        <h3>📊 Conversation Analysis</h3>
                        <p><strong>File:</strong> ${filename}</p>
                        <p><strong>Total Messages:</strong> ${conversations.length}</p>
                    </div>
                    <div class="conversation-messages">
                        ${conversations.map((msg, index) => {
                            const isUser = msg['Sender type'] && msg['Sender type'].toLowerCase().includes('web');
                            const isBot = msg['Sender type'] && msg['Sender type'].toLowerCase().includes('bot');
                            const speakerClass = isUser ? 'user-message' : isBot ? 'bot-message' : 'system-message';
                            const speakerIcon = isUser ? '👤' : isBot ? '🤖' : '⚙️';
                            
                            return `
                                <div class="message ${speakerClass}">
                                    <div class="message-header">
                                        <span class="speaker-icon">${speakerIcon}</span>
                                        <span class="speaker-name">${msg['Sender full name'] || msg['Sender name'] || 'Unknown'}</span>
                                        ${msg['Time in GMT'] ? `<span class="timestamp">${msg['Time in GMT']}</span>` : ''}
                    </div>
                                    <div class="message-content">
                                        ${msg['Message'] || 'No message content'}
                    </div>
                </div>
                            `;
                        }).join('')}
            </div>
                `;
                
            } catch (error) {
                console.error('Error parsing CSV:', error);
                document.getElementById('conversationContent').innerHTML = `
                    <div style="text-align: center; color: #dc3545; padding: 20px;">
                        <h3>❌ Error Parsing Conversation</h3>
                        <p><strong>File:</strong> ${filename}</p>
                        <p><strong>Error:</strong> ${error.message}</p>
                        <p style="font-size: 0.9em; margin-top: 15px;">
                            The CSV format may be different than expected.<br>
                            Raw content preview:
                        </p>
                        <div style="background: white; padding: 15px; border-radius: 8px; margin-top: 15px; text-align: left; font-family: monospace; font-size: 0.8em; max-height: 200px; overflow-y: auto;">
                            <pre>${csvText.substring(0, 1000)}${csvText.length > 1000 ? '...' : ''}</pre>
        </div>
    </div>
                `;
            }
        }
        
        function parseCSVLine(line) {
            const result = [];
            let current = '';
            let inQuotes = false;
            
            for (let i = 0; i < line.length; i++) {
                const char = line[i];
                if (char === '"') {
                    inQuotes = !inQuotes;
                } else if (char === ',' && !inQuotes) {
                    result.push(current.trim());
                    if (current.includes('"')) {
                        result[result.length - 1] = result[result.length - 1].replace(/^"|"$/g, '');
                    }
                    current = '';
                } else {
                    current += char;
                }
            }
            result.push(current.trim());
            if (current.includes('"')) {
                result[result.length - 1] = result[result.length - 1].replace(/^"|"$/g, '');
            }
            return result;
        }
        
        function closeHistoryModal() {
            const modal = document.getElementById('historyModal');
            if (modal) {
                modal.remove();
            }
        }
        
        function testModal() {
            console.log('Testing modal display...');
            const modal = document.getElementById('conversationModal');
            const modalTitle = document.getElementById('modalTitle');
            const conversationListDiv = document.getElementById('conversationList');
            
            if (modal && modalTitle && conversationListDiv) {
                modalTitle.textContent = 'Test Modal (Testing)';
                conversationListDiv.innerHTML = '<div style="padding: 20px; text-align: center;"><h3>Modal is working!</h3><p>This is a test to verify the modal can be displayed.</p></div>';
                modal.style.display = 'block';
                console.log('Modal displayed successfully');
            } else {
                console.error('Modal elements not found:', { modal, modalTitle, conversationListDiv });
                alert('Modal elements not found! Check console for details.');
            }
        }
        
        function closeConversationModal() {
            const modal = document.getElementById('conversationModal');
            modal.style.display = 'none';
        }
        
        // Close modal when clicking outside
        window.onclick = function(event) {
            const modal = document.getElementById('conversationModal');
            if (event.target === modal) {
                modal.style.display = 'none';
            }
        }
    </script>
</body>
</html>"""
    
    # Write HTML report for local testing (with Bot_* folder path)
    local_output = output_file.replace('.html', '_local.html')
    with open(local_output, 'w', encoding='utf-8') as f:
        f.write(html_report)
    
    # Write HTML report directly to Netlify deployment folder
    netlify_dir = './netlify-deploy'
    if not os.path.exists(netlify_dir):
        os.makedirs(netlify_dir)
        print(f"  📁 Created directory: {netlify_dir}")
    
    netlify_output = os.path.join(netlify_dir, 'index.html')
    netlify_html = html_report.replace(
        'const csvPath = `Bot_714b4955-90a2-4693-9380-a28dffee2e3a_Year_2025_4a86f154be3a4925a510e33bdda399b3 (3)/${filename}`;',
        'const csvPath = `./chat-data/${filename}`;'
    )
    with open(netlify_output, 'w', encoding='utf-8') as f:
        f.write(netlify_html)
    
    print(f"✅ Generated HTML reports:")
    print(f"   📁 Local testing: {local_output} (CSV path: ./Bot_*/)")
    print(f"   🌐 Netlify deployment: {netlify_output} (CSV path: ./chat-data/)")
    print(f"📊 HTML reports include:")
    print(f"   📈 Key metrics and success rates")
    print(f"   🚨 Top 3 critical issues")
    print(f"   🔍 Detailed breakdown by impact")
    print(f"   📋 Summary statistics")
    print(f"   🌐 Open in any web browser on Mac")
    print(f"\n💡 Use {local_output} for local testing with python -m http.server 8000")
    print(f"💡 Use {netlify_output} for Netlify deployment")

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
