from rest_framework import serializers
from .models import News


class NewsSerializer(serializers.ModelSerializer):
    class Meta:
        model = News
        fields = ['id', 'title', 'slug', 'body', 'image', 'is_published', 'published_at', 'updated_at']
        read_only_fields = ['id', 'published_at', 'updated_at']