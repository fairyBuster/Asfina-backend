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
        
        # Setup time: Start at Day 1
        now = timezone.now()
        local_now = timezone.localtime(now)
        self.current_time = local_now.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        self.created_at = self.current_time
        
        # Initial next claim calculation
        self.next_claim_time = self._calculate_next(self.created_at)

    def _calculate_next(self, base_time):
        local_base = timezone.localtime(base_time)
        target_dt = local_base.replace(hour=self.reset_hour, minute=0, second=0, microsecond=0)
        
        # Logic from views.py: if target <= base, move to tomorrow
        if target_dt <= local_base:
            target_dt += timedelta(days=1)
        return target_dt

    def try_claim(self):
        can_claim = False
        reason = ""
        
        # Simulation Logic matching codebase
        if self.last_claim_time is None:
             can_claim = True
             reason = "First claim (Allowed)"
        elif self.current_time >= self.next_claim_time:
            can_claim = True
            reason = "Time passed"
        else:
            reason = "Too early"

        if can_claim:
            self.claims_count += 1
            self.last_claim_time = self.current_time
            # Update next claim time based on THIS claim time
            self.next_claim_time = self._calculate_next(self.current_time)
            self.history.append(f"Day {self.current_time.day} {self.current_time.strftime('%H:%M')} : Claimed ({reason}) -> Next: {self.next_claim_time.strftime('%d %H:%M')}")
            return True
        else:
            self.history.append(f"Day {self.current_time.day} {self.current_time.strftime('%H:%M')} : FAILED ({reason}) -> Wait until: {self.next_claim_time.strftime('%d %H:%M')}")
            return False

    def forward_days(self, days):
        self.current_time += timedelta(days=days)
    
    def set_hour(self, hour, minute=0):
        self.current_time = self.current_time.replace(hour=hour, minute=minute)

def simulate_subsequent_days():
    print("=== Skenario Hari-Hari Berikutnya (Reset Jam 07:00) ===")
    
    # Skenario: User sudah klaim hari pertama jam 08:00
    # Kita lihat apa yang terjadi di hari ke-2 dan ke-3
    
    print("\n--- Start: Hari 1, Klaim Jam 08:00 ---")
    sim = MockInvestmentScenario(start_hour=8, reset_hour=7)
    
    # Hari 1: Klaim jam 08:00
    sim.try_claim()
    
    # Maju ke Hari 2
    sim.forward_days(1) 
    
    print("\n[Hari 2]")
    # Coba klaim jam 06:00 (Sebelum reset jam 7)
    sim.set_hour(6, 0)
    sim.try_claim()
    
    # Coba klaim jam 07:05 (Setelah reset jam 7)
    sim.set_hour(7, 5)
    sim.try_claim()
    
    # Coba klaim lagi jam 23:00 (Malam hari yang sama)
    sim.set_hour(23, 0)
    sim.try_claim()
    
    print("\n[Hari 3]")
    sim.forward_days(1)
    # Coba klaim jam 07:05
    sim.set_hour(7, 5)
    sim.try_claim()

    print("\n--- History Log ---")
    for h in sim.history:
        print(h)

if __name__ == "__main__":
    simulate_subsequent_days()
