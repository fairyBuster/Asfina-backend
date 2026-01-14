from django.db.models import Sum, Count, Q
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import authenticate
from .models import User, RankLevel, UserAddress
from products.models import Transaction, Investment
from deposits.models import Deposit
from django.core.exceptions import ValidationError

class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model - used for GET requests"""
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'full_name', 'phone', 'balance', 
                 'balance_deposit', 'banned_status', 'referral_by', 'referral_code', 
                 'rank', 'is_account_non_expired', 'is_account_non_locked', 
                 'is_credentials_non_expired', 'is_enabled', 'created_at', 'updated_at')
        read_only_fields = ('balance', 'balance_deposit', 'banned_status', 'referral_code', 
                          'rank', 'is_account_non_expired', 'is_account_non_locked', 
                          'is_credentials_non_expired', 'is_enabled', 'created_at', 'updated_at')

class RegisterSerializer(serializers.ModelSerializer):
    """Serializer for registering new users"""
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)
    referral_code = serializers.CharField(required=False, allow_blank=True, write_only=True)
    otp = serializers.CharField(required=False, allow_blank=True, write_only=True, help_text='OTP code (required if OTP is enabled)')

    class Meta:
        model = User
        fields = ('username', 'password', 'password2', 'email', 'full_name', 
                 'phone', 'referral_code', 'otp')

    def validate_phone(self, value):
        # Pass-through: jangan ubah nilai phone sama sekali
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        
        # Validate phone number uniqueness
        phone = attrs.get('phone')
        if User.objects.filter(phone=phone).exists():
            raise serializers.ValidationError({"phone": "This phone number is already in use."})
        
        # Validate referral code if provided
        referral_code = attrs.pop('referral_code', None)
        if referral_code:
            try:
                referrer = User.objects.get(referral_code=referral_code)
                attrs['referral_by'] = referrer
            except User.DoesNotExist:
                raise serializers.ValidationError({"referral_code": "Invalid referral code."})
        
        return attrs

    def create(self, validated_data):
        # Pastikan rank default = 1 jika tidak diset
        validated_data.setdefault('rank', 1)
        # Hapus field konfirmasi yang bukan kolom model sebelum create_user
        validated_data.pop('password2', None)
        validated_data.pop('otp', None)
        user = User.objects.create_user(**validated_data)
        return user

class ChangePasswordByPhoneSerializer(serializers.Serializer):
    """Serializer to change password using phone and current password"""
    phone = serializers.CharField(required=True)
    old_password = serializers.CharField(write_only=True, required=True)
    new_password = serializers.CharField(write_only=True, required=True, validators=[validate_password])

    def validate(self, attrs):
        phone = attrs.get('phone')
        old_password = attrs.get('old_password')

        try:
            user = User.objects.get(phone=phone)
        except User.DoesNotExist:
            raise serializers.ValidationError({"phone": "User with this phone does not exist."})

        if not user.check_password(old_password):
            raise serializers.ValidationError({"old_password": "Current password is incorrect."})

        attrs['user'] = user
        return attrs

    def save(self, **kwargs):
        user = self.validated_data['user']
        new_password = self.validated_data['new_password']
        user.set_password(new_password)
        user.save(update_fields=["password"])
        return user


class AccountInfoSerializer(serializers.ModelSerializer):
    """Serializer for user account information - returns safe user data"""
    referral_by_username = serializers.SerializerMethodField()
    referral_by_phone = serializers.SerializerMethodField()
    root_parent_username = serializers.SerializerMethodField()
    root_parent_phone = serializers.SerializerMethodField()
    ip_address = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'full_name', 'phone', 'balance', 
                 'balance_deposit', 'referral_by_username', 'referral_by_phone', 
                 'root_parent_username', 'root_parent_phone',
                 'referral_code', 'rank', 'created_at', 'updated_at', 'ip_address')
        read_only_fields = ('id', 'username', 'email', 'full_name', 'phone', 'balance', 
                           'balance_deposit', 'referral_by_username', 'referral_by_phone', 
                           'root_parent_username', 'root_parent_phone',
                           'referral_code', 'rank', 'created_at', 'updated_at')

    def get_ip_address(self, obj):
        request = self.context.get('request')
        if request:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0]
            else:
                ip = request.META.get('REMOTE_ADDR')
            return ip
        return None

    def get_referral_by_username(self, obj):
        """Get the username of the direct referrer"""
        if obj.referral_by:
            return obj.referral_by.username
        return None
    
    def get_referral_by_phone(self, obj):
        """Get the phone of the direct referrer"""
        if obj.referral_by:
            return obj.referral_by.phone
        return None
    
    def get_root_parent_username(self, obj):
        """Get the username of the root parent (top-level referrer)"""
        current_user = obj
        while current_user.referral_by:
            current_user = current_user.referral_by
        
        # If current_user is not the same as obj, then we found a root parent
        if current_user != obj:
            return current_user.username
        return None

    def get_root_parent_phone(self, obj):
        """Get the phone of the root parent (top-level referrer)"""
        current_user = obj
        while current_user.referral_by:
            current_user = current_user.referral_by

        # If current_user is not the same as obj, then we found a root parent
        if current_user != obj:
            return current_user.phone
        return None

class AccountStatsSerializer(serializers.ModelSerializer):
    """Serializer for summarizing user account statistics and transactions"""
    total_profit_commission = serializers.SerializerMethodField()
    total_purchase_commission = serializers.SerializerMethodField()
    total_earned_commission = serializers.SerializerMethodField()
    commission_count = serializers.SerializerMethodField()
    total_investments = serializers.SerializerMethodField()
    total_investment_amount = serializers.SerializerMethodField()
    active_investments = serializers.SerializerMethodField()
    total_deposits = serializers.SerializerMethodField()
    total_deposit_amount = serializers.SerializerMethodField()
    completed_deposits = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()
    transaction_history = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'phone', 'full_name', 'created_at', 
                 'total_profit_commission', 'total_purchase_commission', 'total_earned_commission', 'commission_count',
                 'total_investments', 'total_investment_amount', 'active_investments',
                 'total_deposits', 'total_deposit_amount', 'completed_deposits',
                 'is_active', 'transaction_history')

    def get_total_profit_commission(self, obj):
        # Sum of completed TRANSACTION type 'PROFIT' linked to user
        return Transaction.objects.filter(user=obj, type='PROFIT', status='COMPLETED').aggregate(total=Sum('amount'))['total'] or 0

    def get_total_purchase_commission(self, obj):
        # Sum of completed TRANSACTION type 'COMMISSIONS' linked to user
        return Transaction.objects.filter(user=obj, type='COMMISSIONS', status='COMPLETED').aggregate(total=Sum('amount'))['total'] or 0

    def get_total_earned_commission(self, obj):
        return self.get_total_profit_commission(obj) + self.get_total_purchase_commission(obj)

    def get_commission_count(self, obj):
        return Transaction.objects.filter(user=obj, type__in=['COMMISSIONS', 'PROFIT'], status='COMPLETED').count()

    def get_total_investments(self, obj):
        return Investment.objects.filter(user=obj).count()

    def get_total_investment_amount(self, obj):
        return Investment.objects.filter(user=obj).aggregate(total=Sum('amount'))['total'] or 0

    def get_active_investments(self, obj):
        return Investment.objects.filter(user=obj, status='ACTIVE').count()

    def get_total_deposits(self, obj):
        return Deposit.objects.filter(user=obj).count()

    def get_total_deposit_amount(self, obj):
        return Deposit.objects.filter(user=obj, status='COMPLETED').aggregate(total=Sum('amount'))['total'] or 0

    def get_completed_deposits(self, obj):
        return Deposit.objects.filter(user=obj, status='COMPLETED').count()

    def get_is_active(self, obj):
        return obj.is_enabled and obj.is_account_non_expired and obj.is_account_non_locked and obj.is_credentials_non_expired

    def get_transaction_history(self, obj):
        qs = Transaction.objects.filter(user=obj).order_by('-created_at')[:10]
        return [
            {
                'trx_id': t.trx_id,
                'type': t.type,
                'amount': str(t.amount),
                'status': t.status,
                'created_at': t.created_at,
            }
            for t in qs
        ]

class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile - only full_name and username"""
    
    class Meta:
        model = User
        fields = ('full_name', 'username')
    
    def validate_username(self, value):
        """Validate that username is unique (excluding current user)"""
        user = self.instance
        if User.objects.filter(username=value).exclude(id=user.id).exists():
            raise serializers.ValidationError("Username sudah digunakan oleh user lain.")
        return value

class WithdrawPinSerializer(serializers.Serializer):
    pin = serializers.CharField(write_only=True)
    current_pin = serializers.CharField(write_only=True, required=False, allow_blank=True)

    def validate(self, attrs):
        user = self.context['request'].user
        new_pin = (attrs.get('pin') or '').strip()
        current_pin = (attrs.get('current_pin') or '').strip()

        # Require exactly 6 digits
        if not (len(new_pin) == 6 and new_pin.isdigit()):
            raise serializers.ValidationError({'pin': 'PIN must be exactly 6 digits.'})

        # If PIN already set, require current_pin and verify
        if user.withdraw_pin:
            if not current_pin:
                raise serializers.ValidationError({'current_pin': 'Current PIN is required to update your PIN.'})
            if not (len(current_pin) == 6 and current_pin.isdigit()):
                raise serializers.ValidationError({'current_pin': 'Current PIN must be exactly 6 digits.'})
            if not user.check_withdraw_pin(current_pin):
                raise serializers.ValidationError({'current_pin': 'Current PIN is incorrect.'})

        attrs['user'] = user
        attrs['new_pin'] = new_pin
        return attrs

    def save(self, **kwargs):
        user = self.validated_data['user']
        new_pin = self.validated_data['new_pin']
        user.set_withdraw_pin(new_pin)
        return user

class DownlineStatsLevelSerializer(serializers.Serializer):
    level = serializers.IntegerField()
    members_total = serializers.IntegerField()
    members_active = serializers.IntegerField()
    members_inactive = serializers.IntegerField()
    deposits_total_count = serializers.IntegerField()
    deposits_total_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    withdrawals_completed_count = serializers.IntegerField()
    withdrawals_completed_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    profit_commission_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    purchase_commission_amount = serializers.DecimalField(max_digits=15, decimal_places=2)

class DownlineStatsResponseSerializer(serializers.Serializer):
    levels = DownlineStatsLevelSerializer(many=True)


class RankLevelSerializer(serializers.ModelSerializer):
    is_current_rank = serializers.SerializerMethodField()
    is_unlocked = serializers.SerializerMethodField()
    user_progress_val = serializers.SerializerMethodField()

    class Meta:
        model = RankLevel
        fields = ('rank', 'title', 'missions_required_total', 'is_current_rank', 'is_unlocked', 'user_progress_val')

    def get_is_current_rank(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated and request.user.rank is not None:
            return obj.rank == request.user.rank
        return False

    def get_is_unlocked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated and request.user.rank is not None:
            return obj.rank <= request.user.rank
        return False

    def get_user_progress_val(self, obj):
        return self.context.get('user_progress', 0)


class RankStatusResponseSerializer(serializers.Serializer):
    current_rank = serializers.IntegerField(allow_null=True)
    current_title = serializers.CharField(allow_null=True)
    completed_missions = serializers.IntegerField()
    next_rank = serializers.IntegerField(allow_null=True)
    next_title = serializers.CharField(allow_null=True)
    next_required_missions = serializers.IntegerField(allow_null=True)


class UserAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAddress
        fields = ['id', 'recipient_name', 'phone_number', 'address_details', 'house_number', 'is_primary', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class TransactionDetailSerializer(serializers.ModelSerializer):
    """Serializer for detailed transaction information"""
    product_name = serializers.CharField(source='product.name', read_only=True)
    upline_phone = serializers.CharField(source='upline_user.phone', read_only=True)
    
    class Meta:
        model = Transaction
        fields = (
            'trx_id', 'type', 'amount', 'description', 'status', 'wallet_type',
            'product_name', 'upline_phone', 'investment_quantity', 'commission_level', 'created_at'
        )

class DownlineMemberSerializer(serializers.Serializer):
    """Serializer for downline member details and aggregates"""
    username = serializers.CharField()
    phone = serializers.CharField()
    registration_date = serializers.DateTimeField(source='created_at', read_only=True)
    
    # Commission data
    total_profit_commission = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_purchase_commission = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_earned_commission = serializers.DecimalField(max_digits=15, decimal_places=2)
    commission_count = serializers.IntegerField()
    
    # Investment/Product data
    total_investments = serializers.IntegerField()
    total_investment_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    active_investments = serializers.IntegerField()
    
    # Deposit data
    total_deposits = serializers.IntegerField()
    total_deposit_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    completed_deposits = serializers.IntegerField()
    
    # Active status
    is_active = serializers.BooleanField()
    
    # Transaction history
    transaction_history = TransactionDetailSerializer(many=True, read_only=True)

class DownlineLevelSerializer(serializers.Serializer):
    """Serializer for downline level summary with investment and deposit totals"""
    level = serializers.IntegerField()
    member_count = serializers.IntegerField()
    total_profit_commission = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_purchase_commission = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_earned_commission = serializers.DecimalField(max_digits=15, decimal_places=2)
    
    # Investment totals for this level
    total_investments = serializers.IntegerField()
    total_investment_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    active_investments = serializers.IntegerField()
    
    # Deposit totals for this level
    total_deposits = serializers.IntegerField()
    total_deposit_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    completed_deposits = serializers.IntegerField()
    
    members = DownlineMemberSerializer(many=True)


class DownlineOverviewSerializer(serializers.Serializer):
    """Serializer for complete downline overview with investment and deposit data"""
    total_members = serializers.IntegerField()
    total_profit_commission = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_purchase_commission = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_earned_commission = serializers.DecimalField(max_digits=15, decimal_places=2)
    
    # Overall investment totals
    total_investments = serializers.IntegerField()
    total_investment_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    active_investments = serializers.IntegerField()
    
    # Overall deposit totals
    total_deposits = serializers.IntegerField()
    total_deposit_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    completed_deposits = serializers.IntegerField()
    
    levels = DownlineLevelSerializer(many=True)


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile - only full_name and username"""
    
    class Meta:
        model = User
        fields = ('full_name', 'username')
    
    def validate_username(self, value):
        """Validate that username is unique (excluding current user)"""
        user = self.instance
        if User.objects.filter(username=value).exclude(id=user.id).exists():
            raise serializers.ValidationError("Username sudah digunakan oleh user lain.")
        return value


