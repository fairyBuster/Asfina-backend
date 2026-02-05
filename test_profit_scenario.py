import os
import django
from datetime import datetime, timedelta
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.utils import timezone

class MockInvestmentScenario:
    def __init__(self, start_hour, reset_hour=7):
        self.reset_hour = reset_hour
        self.claims_count = 0
        self.duration_days = 30
        self.last_claim_time = None
        self.history = []
        
        # Setup time
        now = timezone.now()
        local_now = timezone.localtime(now)
        self.current_time = local_now.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        self.created_at = self.current_time
        
        # Initial next claim calculation
        self.next_claim_time = self._calculate_next(self.created_at)

    def _calculate_next(self, base_time):
        local_base = timezone.localtime(base_time)
        target_dt = local_base.replace(hour=self.reset_hour, minute=0, second=0, microsecond=0)
        if target_dt <= local_base:
            target_dt += timedelta(days=1)
        return target_dt

    def try_claim(self):
        # Current Logic Simulation: Always allows first claim
        can_claim = False
        reason = ""
        
        if self.last_claim_time is None:
            can_claim = True # BUG: First claim always allowed
            reason = "First claim (Bug)"
        elif self.current_time >= self.next_claim_time:
            can_claim = True
            reason = "Time passed"
        else:
            reason = "Too early"

        if can_claim:
            self.claims_count += 1
            self.last_claim_time = self.current_time
            self.next_claim_time = self._calculate_next(self.current_time)
            self.history.append(f"Day {self.current_time.day}: Claimed at {self.current_time.strftime('%H:%M')} ({reason})")
            return True
        return False

    def forward_time(self, hours=1):
        self.current_time += timedelta(hours=hours)

def simulate_profit_impact():
    print("=== Skenario: Reset Jam 07:00 ===")
    
    # Skenario A: Beli Jam 06:00 (Sebelum Reset)
    print("\n--- User A: Beli Jam 06:00 ---")
    sim = MockInvestmentScenario(start_hour=6, reset_hour=7)
    
    # 06:05 - Coba Klaim
    sim.forward_time(0.1) # 06:06
    sim.try_claim()
    
    # 07:05 - Coba Klaim (Setelah Reset)
    sim.current_time = sim.current_time.replace(hour=7, minute=5)
    sim.try_claim()
    
    for h in sim.history:
        print(h)
    print(f"Total Claim Hari ke-1: {sim.claims_count}")
    
    if sim.claims_count > 1:
        print(">> KESIMPULAN: RUGI BANDAR (Double Claim)")
    else:
        print(">> KESIMPULAN: AMAN")

    # Skenario B: Beli Jam 08:00 (Setelah Reset)
    print("\n--- User B: Beli Jam 08:00 ---")
    sim = MockInvestmentScenario(start_hour=8, reset_hour=7)
    
    # 08:05 - Coba Klaim
    sim.forward_time(0.1)
    sim.try_claim()
    
    # Besok 07:05 - Coba Klaim
    sim.current_time += timedelta(days=1)
    sim.current_time = sim.current_time.replace(hour=7, minute=5)
    sim.try_claim()
    
    for h in sim.history:
        print(h)
    print(f"Total Claim Hari ke-1 (s/d besok pagi): {sim.claims_count}")

if __name__ == "__main__":
    simulate_profit_impact()
