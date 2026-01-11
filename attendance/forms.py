from django import forms
from decimal import Decimal
from .models import AttendanceSettings


class AttendanceSettingsAdminForm(forms.ModelForm):
    rank_1 = forms.DecimalField(label='Rank 1 amount', required=False, min_value=0)
    rank_2 = forms.DecimalField(label='Rank 2 amount', required=False, min_value=0)
    rank_3 = forms.DecimalField(label='Rank 3 amount', required=False, min_value=0)
    rank_4 = forms.DecimalField(label='Rank 4 amount', required=False, min_value=0)
    rank_5 = forms.DecimalField(label='Rank 5 amount', required=False, min_value=0)
    rank_6 = forms.DecimalField(label='Rank 6 amount', required=False, min_value=0)

    # Daily sequence fields
    day_1 = forms.DecimalField(label='Day 1 Reward', required=False, min_value=0)
    day_2 = forms.DecimalField(label='Day 2 Reward', required=False, min_value=0)
    day_3 = forms.DecimalField(label='Day 3 Reward', required=False, min_value=0)
    day_4 = forms.DecimalField(label='Day 4 Reward', required=False, min_value=0)
    day_5 = forms.DecimalField(label='Day 5 Reward', required=False, min_value=0)
    day_6 = forms.DecimalField(label='Day 6 Reward', required=False, min_value=0)
    day_7 = forms.DecimalField(label='Day 7 Reward', required=False, min_value=0)

    class Meta:
        model = AttendanceSettings
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        rr = self.instance.rank_rewards or {}
        for i in range(1, 7):
            key = str(i)
            if key in rr:
                try:
                    self.fields[f'rank_{i}'].initial = Decimal(str(rr[key]))
                except Exception:
                    self.fields[f'rank_{i}'].initial = rr[key]
        
        dr = self.instance.daily_rewards or {}
        for i in range(1, 8):
            key = str(i)
            if key in dr and f'day_{i}' in self.fields:
                try:
                    self.fields[f'day_{i}'].initial = Decimal(str(dr[key]))
                except Exception:
                    self.fields[f'day_{i}'].initial = dr[key]

    def save(self, commit=True):
        instance = super().save(commit=False)
        rr = {}
        for i in range(1, 7):
            val = self.cleaned_data.get(f'rank_{i}')
            if val is not None:
                # Store as float to keep JSON simple
                rr[str(i)] = float(val)
        instance.rank_rewards = rr
        
        dr = {}
        for i in range(1, 8):
            val = self.cleaned_data.get(f'day_{i}')
            if val is not None:
                dr[str(i)] = float(val)
        instance.daily_rewards = dr
        
        if commit:
            instance.save()
        return instance