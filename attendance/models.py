from django.db import models
from django.conf import settings
from django.utils import timezone


class AttendanceSettings(models.Model):
    BALANCE_CHOICES = [
        ('balance', 'Balance'),
        ('balance_deposit', 'Balance Deposit'),
    ]

    REWARD_TYPE_CHOICES = [
        ('fixed', 'Fixed Amount'),
        ('random', 'Random Range'),
        ('rank', 'Rank Based'),
        ('daily', 'Daily Sequence'),
    ]

    balance_source = models.CharField(max_length=20, choices=BALANCE_CHOICES)
    reward_type = models.CharField(max_length=20, choices=REWARD_TYPE_CHOICES)

    # Base reward configuration
    fixed_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    min_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    max_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Rank-based reward mapping: keys '1'..'6' map to decimal amounts
    rank_rewards = models.JSONField(default=dict, blank=True, help_text='Mapping: {"1": 5000, "2": 6000, ...}')
    
    # Daily sequence rewards
    daily_rewards = models.JSONField(default=dict, blank=True, help_text='Mapping: {"1": 100, "2": 200, ...}')
    daily_cycle_days = models.IntegerField(default=7, help_text='Number of days in the cycle (e.g. 7). After this day, it loops back to day 1.')

    # Bonuses
    consecutive_bonus_enabled = models.BooleanField(default=False)
    bonus_7_days = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    bonus_30_days = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Status
    is_active = models.BooleanField(default=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"AttendanceSettings(id={self.id}, active={self.is_active})"

    class Meta:
        db_table = 'attendance_settings'
        ordering = ['-created_at']


class AttendanceLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date = models.DateField()
    streak_count = models.IntegerField(default=1)
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"AttendanceLog(user={self.user_id}, date={self.date}, amount={self.amount})"

    class Meta:
        db_table = 'attendance_logs'
        ordering = ['-date', '-created_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'date'], name='unique_user_date_attendance')
        ]