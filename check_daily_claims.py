import os
import django
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import Investment

def check_daily_claims():
    print("Checking daily claims status...")
    
    today_start_local = timezone.localtime(timezone.now()).replace(hour=0, minute=0, second=0, microsecond=0)
    print(f"Today Start (Local): {today_start_local}")
    
    investments = Investment.objects.filter(
        status='ACTIVE',
        product__profit_method='auto'
    )
    
    total = investments.count()
    claimed_today = 0
    not_claimed = 0
    
    for inv in investments:
        last_claim = inv.last_claim_time
        if last_claim and timezone.localtime(last_claim) >= today_start_local:
            claimed_today += 1
        else:
            not_claimed += 1
            print(f"NOT CLAIMED: ID {inv.id} ({inv.user.phone}) - Last Claim: {timezone.localtime(last_claim) if last_claim else 'Never'}")
            print(f"   Next Claim: {timezone.localtime(inv.next_claim_time) if inv.next_claim_time else 'None'}")
            
    print(f"\nTotal Active Auto Investments: {total}")
    print(f"Claimed Today: {claimed_today}")
    print(f"Not Claimed Today: {not_claimed}")

if __name__ == "__main__":
    check_daily_claims()
