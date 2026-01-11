from django import forms
from .models import Product

class ProductAdminForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = '__all__'
        widgets = {
            'image': forms.FileInput(attrs={'accept': 'image/*'}),
            'description': forms.Textarea(attrs={'rows': 4}),
            'specifications': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Clarify duration unit as days
        if 'duration' in self.fields:
            self.fields['duration'].label = 'Duration (days)'
            self.fields['duration'].help_text = 'Isi dalam hari. Contoh: 24 = 24 hari (klaim harian sebanyak 24x).'
        # Clarify claim reset hours usage
        if 'claim_reset_hours' in self.fields:
            self.fields['claim_reset_hours'].help_text = 'Interval jam untuk mode Reset after purchase (opsional).'
