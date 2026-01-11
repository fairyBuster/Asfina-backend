from django.contrib import admin
from .models import AttendanceSettings, AttendanceLog
from .forms import AttendanceSettingsAdminForm


@admin.register(AttendanceSettings)
class AttendanceSettingsAdmin(admin.ModelAdmin):
    form = AttendanceSettingsAdminForm
    list_display = (
        'id', 'balance_source', 'reward_type', 'fixed_amount', 'min_amount', 'max_amount',
        'consecutive_bonus_enabled', 'bonus_7_days', 'bonus_30_days', 'is_active', 'created_at'
    )

    def has_add_permission(self, request):
        # Cukup satu konfigurasi, kalau sudah ada maka tidak bisa tambah baru
        return not AttendanceSettings.objects.exists()
    list_filter = ('is_active', 'balance_source', 'reward_type', 'consecutive_bonus_enabled')
    search_fields = ('id',)
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        (None, {
            'fields': ('balance_source', 'reward_type', 'is_active')
        }),
        ('Base Reward', {
            'fields': ('fixed_amount', 'min_amount', 'max_amount')
        }),
        ('Rank Rewards (tanpa JSON)', {
            'fields': ('rank_1', 'rank_2', 'rank_3', 'rank_4', 'rank_5', 'rank_6'),
            'description': 'Isi nominal untuk rank 1–6. Tidak perlu JSON.'
        }),
        ('Daily Rewards (Cycle)', {
            'fields': ('daily_cycle_days', 'day_1', 'day_2', 'day_3', 'day_4', 'day_5', 'day_6', 'day_7'),
            'description': 'Isi nominal untuk setiap hari dalam siklus (misal 7 hari). Jika streak > 7, akan kembali ke hari 1 (jika cycle=7).'
        }),
        ('Bonus Beruntun', {
            'fields': ('consecutive_bonus_enabled', 'bonus_7_days', 'bonus_30_days')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(AttendanceLog)
class AttendanceLogAdmin(admin.ModelAdmin):
    list_display = ('user_phone', 'date', 'streak_count', 'amount', 'created_at')
    search_fields = ('user__phone',)
    list_filter = ('date',)
    readonly_fields = ('created_at',)

    def user_phone(self, obj):
        return obj.user.phone
    user_phone.short_description = 'Phone'
