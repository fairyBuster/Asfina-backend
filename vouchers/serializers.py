from rest_framework import serializers
from .models import Voucher, VoucherUsage


class VoucherSerializer(serializers.ModelSerializer):
    class Meta:
        model = Voucher
        fields = ['id', 'code', 'type', 'amount', 'min_amount', 'max_amount', 'rank_rewards', 'balance_type', 'usage_limit', 'used_count', 'is_active', 'expires_at', 'created_at', 'updated_at']


class ClaimVoucherSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=50)


class VoucherListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    results = VoucherSerializer(many=True)


class ClaimVoucherResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    voucher_code = serializers.CharField()
    amount = serializers.CharField()
    wallet_type = serializers.CharField()
    transaction_id = serializers.CharField()
    balance = serializers.CharField()