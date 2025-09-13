#!/usr/bin/env python3
"""
Cost comparison between transcription services with accurate pricing analysis.
Updated with OpenAI Whisper API integration and correct cost calculations.
"""
from transcription_config import TranscriptionConfig

def compare_transcription_costs():
    """Compare transcription costs using actual pricing from transcription config"""
    num_videos = 336
    avg_duration_minutes = 75
    total_minutes = num_videos * avg_duration_minutes
    total_hours = total_minutes / 60
    
    print('🔊 Transcription Service Cost Comparison')
    print(f'📹 Scope: {num_videos} videos × {avg_duration_minutes} min = {total_minutes:,} minutes ({total_hours:.0f} hours)')
    print('=' * 70)
    
    # Get cost analysis from TranscriptionConfig
    comparison = TranscriptionConfig.compare_service_costs(num_videos, avg_duration_minutes)
    
    openai_cost = comparison['openai_whisper']
    google_best = comparison['google_best']
    google_premium = comparison['google_premium']
    
    # Display service costs
    print(f'🤖 OpenAI Whisper API:')
    print(f'   • Model: {openai_cost["model_used"]}')
    print(f'   • Pricing: ${openai_cost["cost_per_unit"]:.3f}/{openai_cost["billing_unit"]}')
    print(f'   • Total Cost: ${openai_cost["total_cost_usd"]:.2f} 🥇')
    print(f'   • Per Video: ${openai_cost["cost_per_video"]:.3f}')
    
    print(f'\n☁️  Google Cloud Speech-to-Text (Best Value):')
    print(f'   • Model: {google_best["model_used"]}')
    print(f'   • Pricing: ${google_best["cost_per_unit"]:.3f}/{google_best["billing_unit"]}')
    print(f'   • Total Cost: ${google_best["total_cost_usd"]:.2f}')
    print(f'   • Per Video: ${google_best["cost_per_video"]:.3f}')
    
    print(f'\n☁️  Google Cloud Speech-to-Text (Premium):')
    print(f'   • Model: {google_premium["model_used"]}')
    print(f'   • Pricing: ${google_premium["cost_per_unit"]:.3f}/{google_premium["billing_unit"]}')
    print(f'   • Total Cost: ${google_premium["total_cost_usd"]:.2f}')
    print(f'   • Per Video: ${google_premium["cost_per_video"]:.3f}')
    
    # AWS Transcribe (manual calculation for comparison)
    aws_per_minute = 0.024
    aws_total = aws_per_minute * total_minutes
    print(f'\n🔶 AWS Transcribe:')
    print(f'   • Pricing: ${aws_per_minute:.3f}/minute')
    print(f'   • Total Cost: ${aws_total:.2f}')
    print(f'   • Per Video: ${aws_total/num_videos:.3f}')
    
    # Cost ranking
    print(f'\n📊 COST RANKING (cheapest to most expensive):')
    
    costs = [
        ('OpenAI Whisper', openai_cost["total_cost_usd"], '🤖'),
        ('Google latest_long', google_best["total_cost_usd"], '☁️'),
        ('AWS Transcribe', aws_total, '🔶'),
        ('Google chirp_2', google_premium["total_cost_usd"], '☁️')
    ]
    costs.sort(key=lambda x: x[1])
    
    for i, (service, cost, icon) in enumerate(costs, 1):
        savings = costs[-1][1] - cost
        percent_savings = (savings / costs[-1][1]) * 100 if cost != costs[-1][1] else 0
        rank_emoji = '🥇' if i == 1 else '🥈' if i == 2 else '🥉' if i == 3 else '💸'
        print(f'  {i}. {rank_emoji} {icon} {service:<18} ${cost:>8.2f} (saves ${savings:>7.2f}, {percent_savings:>5.1f}%)')
    
    # Savings analysis
    print(f'\n💰 SAVINGS ANALYSIS:')
    vs_google_best = comparison['savings']['vs_google_best']
    vs_google_premium = comparison['savings']['vs_google_premium']
    
    print(f'   OpenAI vs Google Best:    ${vs_google_best["amount_usd"]:.2f} savings ({vs_google_best["percentage"]:.1f}%)')
    print(f'   OpenAI vs Google Premium: ${vs_google_premium["amount_usd"]:.2f} savings ({vs_google_premium["percentage"]:.1f}%)')
    print(f'   OpenAI vs AWS Transcribe:  ${aws_total - openai_cost["total_cost_usd"]:.2f} savings ({((aws_total - openai_cost["total_cost_usd"])/aws_total)*100:.1f}%)')
    
    # Recommendation
    print(f'\n🎯 RECOMMENDATION:')
    recommended_service = comparison['recommendation']
    if recommended_service == 'openai':
        print(f'   ✅ Use OpenAI Whisper API: Massive cost savings (87.5% cheaper than Google)')
        print(f'   💡 Benefits: ${vs_google_best["amount_usd"]:.2f} saved, excellent accuracy, fast processing')
        print(f'   📝 Setup: Set OPENAI_API_KEY environment variable')
    else:
        print(f'   ✅ Use Google Speech-to-Text: Better accuracy for complex audio')
        print(f'   💰 Cost consideration: ${vs_google_best["amount_usd"]:.2f} more than OpenAI')
    
    # Implementation notes
    print(f'\n🔧 IMPLEMENTATION STATUS:')
    print(f'   • OpenAI Whisper: ✅ Integrated (Primary service)')
    print(f'   • Google Speech: ✅ Available (Fallback service)')  
    print(f'   • Service Selection: Automatic based on TRANSCRIPTION_SERVICE env var')
    print(f'   • Fallback Logic: ✅ Enabled (switches services on failure)')

def get_cost_for_duration(minutes, service='openai'):
    """Get cost estimate for specific duration"""
    if service == 'openai':
        return minutes * 0.006
    elif service == 'google_best':
        return (minutes / 60) * 2.16  # Convert to hours for Google pricing
    elif service == 'google_premium':
        return (minutes / 60) * 2.88
    elif service == 'aws':
        return minutes * 0.024
    else:
        return 0

def quick_cost_comparison(minutes):
    """Quick cost comparison for any duration"""
    print(f'\n⏱️  Quick Cost Calculator ({minutes} minutes):')
    print(f'   OpenAI Whisper:     ${get_cost_for_duration(minutes, "openai"):.2f}')
    print(f'   Google latest_long: ${get_cost_for_duration(minutes, "google_best"):.2f}')
    print(f'   Google chirp_2:     ${get_cost_for_duration(minutes, "google_premium"):.2f}')
    print(f'   AWS Transcribe:     ${get_cost_for_duration(minutes, "aws"):.2f}')

if __name__ == "__main__":
    compare_transcription_costs()
    
    # Example quick calculations
    print(f'\n' + '='*70)
    quick_cost_comparison(75)   # Single 75-minute video
    quick_cost_comparison(300)  # 5-hour content