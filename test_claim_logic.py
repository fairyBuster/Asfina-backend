import os
import django
from datetime import datetime, timedelta
from decimal import Decimal

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.utils import timezone
from products.models import Investment, Product
from django.conf import settings

# Mock classes to avoid DB operations
class MockProduct:
    def __init__(self, reset_hours=0):
        self.claim_reset_hours = reset_hours
        self.name = "Test Product"

class MockInvestment:
    def __init__(self, created_at, reset_mode='at_custom', reset_hours=0):
        self.created_at = created_at
        self.last_claim_time = None
        self.next_claim_time = None
        self.claim_reset_mode = reset_mode
        self.product = MockProduct(reset_hours)
        self.status = 'ACTIVE'
        self.claims_count = 0
        self.duration_days = 30
        self.remaining_days = 30
        self.profit_method = 'manual'
        
        # Initialize next_claim_time like in views.py
        self.next_claim_time = self.calculate_next_claim_time()

    def calculate_next_claim_time(self):
        # Copy-paste logic from models.py
        if self.claim_reset_mode == 'at_custom':
            base_time = self.last_claim_time if self.last_claim_time else self.created_at
            local_base = timezone.localtime(base_time)
            
            target_hour = 0
            if self.product.claim_reset_hours is not None:
                target_hour = int(self.product.claim_reset_hours) % 24
            
            target_dt = local_base.replace(hour=target_hour, minute=0, second=0, microsecond=0)
            
            if target_dt <= local_base:
                target_dt = target_dt + timedelta(days=1)
                
            return target_dt
        return None

    def can_claim_today(self, current_time):
        # Copy-paste logic from models.py (adjusted for current_time arg)
        if self.status != 'ACTIVE':
            return False, "Not Active"
            
        if self.claims_count >= self.duration_days:
            return False, "Max Claims Reached"
            
        if self.remaining_days <= 0:
            return False, "Expired"

        # Check if already claimed today (for manual claims)
        if self.last_claim_time:
            if self.claim_reset_mode == 'at_00':
                today = timezone.localdate(current_time)
                last_claim_date = timezone.localtime(self.last_claim_time).date()
                if not (today > last_claim_date):
                    return False, "Already claimed today (at_00)"
            else:
                if self.next_claim_time and current_time < self.next_claim_time:
                    return False, f"Too early. Next claim: {self.next_claim_time}"
        
        return True, "OK"

    def claim(self, claim_time):
        can, msg = self.can_claim_today(claim_time)
        if not can:
            print(f"[-] Claim FAILED at {timezone.localtime(claim_time)}: {msg}")
            return False
        
        print(f"[+] Claim SUCCESS at {timezone.localtime(claim_time)}")
        self.last_claim_time = claim_time
        self.next_claim_time = self.calculate_next_claim_time()
        self.claims_count += 1
        return True

class MockInvestmentFixed(MockInvestment):
    def can_claim_today(self, current_time):
        if self.status != 'ACTIVE':
            return False, "Not Active"
        if self.claims_count >= self.duration_days:
            return False, "Max Claims Reached"
        if self.remaining_days <= 0:
            return False, "Expired"

        # PROPOSED FIX: Enforce next_claim_time check for at_custom even if last_claim_time is None
        if self.claim_reset_mode == 'at_custom':
             if self.next_claim_time and current_time < self.next_claim_time:
                 return False, f"Too early (Fixed). Next claim: {timezone.localtime(self.next_claim_time)}"
        
        # Existing logic for others (or fallback)
        if self.last_claim_time:
            if self.claim_reset_mode == 'at_00':
                today = timezone.localdate(current_time)
                last_claim_date = timezone.localtime(self.last_claim_time).date()
                if not (today > last_claim_date):
                    return False, "Already claimed today (at_00)"
            else:
                # This covers at_custom (if not handled above) and others
                if self.next_claim_time and current_time < self.next_claim_time:
                    return False, f"Too early. Next claim: {self.next_claim_time}"
        
        return True, "OK"

def run_simulation():
    jakarta_tz = timezone.get_current_timezone() # Asia/Jakarta
    reset_hour = 14
    
    # Scenario 1: Buy BEFORE reset time (e.g., 10:00 WIB)
    print("\nScenario 1: Buy at 10:00 WIB, Reset at 14:00 WIB")
    
    # Create aware datetime for TODAY 10:00 WIB
    now = timezone.now()
    local_now = timezone.localtime(now)
    start_time = local_now.replace(hour=10, minute=0, second=0, microsecond=0)
    
    # Ensure start_time is in the past or present relative to now for realism, but for mock it doesn't matter much
    # except that 'check_time' vs 'start_time' logic.
    
    inv = MockInvestment(start_time, reset_hours=reset_hour)
    print(f"Created at: {timezone.localtime(inv.created_at)}")
    print(f"Initial Next Claim: {timezone.localtime(inv.next_claim_time)}")
    
    # Try claim immediately at 10:05 WIB
    check_time = start_time + timedelta(minutes=5)
    inv.claim(check_time)
    print(f"Next Claim after 1st claim: {timezone.localtime(inv.next_claim_time)}")
    
    # Try claim again at 13:59 WIB (Same day) - Should fail?
    # Wait, if I claimed at 10:05. Next claim is 14:00 Today? Or Tomorrow?
    # Let's see the output.
    check_time = start_time.replace(hour=13, minute=59)
    inv.claim(check_time)
    
    # Try claim at 14:01 WIB (Same day)
    check_time = start_time.replace(hour=14, minute=1)
    inv.claim(check_time)
    print(f"Next Claim after 2nd claim: {timezone.localtime(inv.next_claim_time)}")

    # Scenario 2: Buy AFTER reset time (e.g., 15:00 WIB)
    print("\nScenario 2: Buy at 15:00 WIB, Reset at 14:00 WIB")
    start_time = local_now.replace(hour=15, minute=0, second=0, microsecond=0)
    inv = MockInvestment(start_time, reset_hours=reset_hour)
    print(f"Created at: {timezone.localtime(inv.created_at)}")
    print(f"Initial Next Claim: {timezone.localtime(inv.next_claim_time)}")
    
    # Try claim immediately at 15:05 WIB
    check_time = start_time + timedelta(minutes=5)
    inv.claim(check_time)
    print(f"Next Claim after 1st claim: {timezone.localtime(inv.next_claim_time)}")
    
    # Try claim next day at 13:59 WIB (Should fail)
    check_time = start_time + timedelta(days=1)
    check_time = check_time.replace(hour=13, minute=59)
    inv.claim(check_time)
    
    # Try claim next day at 14:01 WIB (Should succeed)
    check_time = start_time + timedelta(days=1)
    check_time = check_time.replace(hour=14, minute=1)
    inv.claim(check_time)
    print(f"Next Claim after 2nd claim: {timezone.localtime(inv.next_claim_time)}")

    # PROPOSED FIX DEMO
    print("\n=== DEMO FIX: Buy at 10:00, Reset at 14:00 (Using Fixed Logic) ===")
    start_time = local_now.replace(hour=10, minute=0, second=0, microsecond=0)
    inv = MockInvestmentFixed(start_time, reset_hours=reset_hour)
    print(f"Created at: {timezone.localtime(inv.created_at)}")
    print(f"Initial Next Claim: {timezone.localtime(inv.next_claim_time)}")
    
    # Try claim immediately at 10:05 WIB (Should FAIL with fix)
    check_time = start_time + timedelta(minutes=5)
    inv.claim(check_time)
    
    # Try claim at 14:01 WIB (Should succeed)
    check_time = start_time.replace(hour=14, minute=1)
    inv.claim(check_time)
    print(f"Next Claim after 1st claim (Fixed): {timezone.localtime(inv.next_claim_time)}")

if __name__ == "__main__":
    run_simulation()
