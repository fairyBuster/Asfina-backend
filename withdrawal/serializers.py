from decimal import Decimal
from rest_framework import serializers
from django.db.models import Sum
from .models import Withdrawal, WithdrawalSettings
from banks.models import UserBank, Bank
from products.models import Transaction
import uuid


class WithdrawalSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = WithdrawalSettings
        fields = [
            'is_active', 'balance_source', 'require_bank_account', 'require_pin', 'minimum_product_quantity', 'required_product'
        ]


class WithdrawalSerializer(serializers.ModelSerializer):
    bank_account_id = serializers.IntegerField(write_only=True, required=False)
    pin = serializers.CharField(write_only=True, required=False, allow_blank=True)
    bank_account_number = serializers.CharField(source='bank_account.account_number', read_only=True)
    bank_account_name = serializers.CharField(source='bank_account.account_name', read_only=True)
    bank_name = serializers.CharField(source='bank_account.bank.name', read_only=True)
    bank_code = serializers.CharField(source='bank_account.bank.code', read_only=True)

    class Meta:
        model = Withdrawal
        fields = [
            'id', 'amount', 'fee', 'net_amount', 'status', 'bank_account', 'bank_account_id', 'created_at', 'pin',
            'bank_account_number', 'bank_account_name', 'bank_name', 'bank_code'
        ]
        read_only_fields = ['fee', 'net_amount', 'status', 'bank_account', 'created_at', 'bank_account_number', 'bank_account_name', 'bank_name', 'bank_code']

    def validate(self, attrs):
        user = self.context['request'].user
        amount = attrs.get('amount')
        bank_account_id = self.initial_data.get('bank_account_id')
        provided_pin = (self.initial_data.get('pin') or '').strip()

        # Settings checks
        settings_obj = WithdrawalSettings.objects.order_by('-updated_at').first()
        if not settings_obj or not settings_obj.is_active:
            raise serializers.ValidationError('Withdrawal is not available right now.')

        # Bank account requirement
        user_bank = None
        if settings_obj.require_bank_account:
            if not bank_account_id:
                # use default user bank if exists
                user_bank = UserBank.objects.filter(user=user, is_default=True).first()
                if not user_bank:
                    raise serializers.ValidationError('Bank account is required.')
            else:
                try:
                    user_bank = UserBank.objects.get(id=bank_account_id, user=user)
                except UserBank.DoesNotExist:
                    raise serializers.ValidationError('Invalid bank account.')

        # Validate against bank limits
        if user_bank:
            bank = user_bank.bank
            if bank.min_withdrawal and amount < bank.min_withdrawal:
                raise serializers.ValidationError(f'Minimum withdrawal is {bank.min_withdrawal}.')
            if bank.max_withdrawal and amount > bank.max_withdrawal:
                raise serializers.ValidationError(f'Maximum withdrawal is {bank.max_withdrawal}.')

        # Validate user balances according to settings
        wallet_field = 'balance' if settings_obj.balance_source == 'balance' else 'balance_deposit'
        user_wallet_amount = getattr(user, wallet_field)
        if user_wallet_amount < amount:
            raise serializers.ValidationError('Insufficient balance.')

        # Check if active investment is required (any product)
        if getattr(settings_obj, 'require_active_investment', False):
            from products.models import Investment
            if not Investment.objects.filter(user=user, status='ACTIVE').exists():
                raise serializers.ValidationError('Anda harus memiliki setidaknya satu produk aktif untuk melakukan penarikan.')

        # Product requirement (if specified)
        # Minimal: ensure user has at least minimum_product_quantity investments
        # If required_product is set, check specific product. Otherwise check any product.
        if settings_obj.minimum_product_quantity > 0:
            from products.models import Investment
            if settings_obj.required_product:
                qty = Investment.objects.filter(user=user, product=settings_obj.required_product).aggregate(Sum('quantity'))['quantity__sum'] or 0
                if qty < settings_obj.minimum_product_quantity:
                    raise serializers.ValidationError(f'Anda harus memiliki minimal {settings_obj.minimum_product_quantity} unit produk {settings_obj.required_product.name} untuk melakukan penarikan.')
            else:
                qty = Investment.objects.filter(user=user).aggregate(Sum('quantity'))['quantity__sum'] or 0
                if qty < settings_obj.minimum_product_quantity:
                    raise serializers.ValidationError(f'Anda harus memiliki minimal {settings_obj.minimum_product_quantity} produk aktif untuk melakukan penarikan.')

        # PIN requirement
        if getattr(settings_obj, 'require_pin', False):
            # Must have a PIN set
            if not user.withdraw_pin:
                raise serializers.ValidationError('Withdrawal PIN not set. Please set your PIN first.')
            # Must provide PIN
            if not provided_pin:
                raise serializers.ValidationError('PIN is required for withdrawal.')
            # Must be exactly 6 digits
            if not (len(provided_pin) == 6 and provided_pin.isdigit()):
                raise serializers.ValidationError('PIN must be exactly 6 digits.')
            # Must match stored PIN
            if not user.check_withdraw_pin(provided_pin):
                raise serializers.ValidationError('Invalid PIN.')

        attrs['_settings_obj'] = settings_obj
        attrs['_user_bank'] = user_bank
        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        amount = validated_data['amount']
        user_bank = validated_data.get('_user_bank')

        # Compute fee from bank withdrawal_fee as percentage of amount
        from decimal import Decimal
        fee = Decimal(0)
        if user_bank:
            rate = (user_bank.bank.withdrawal_fee or Decimal(0))
            fee = (amount * rate / Decimal('100')).quantize(Decimal('0.01'))

        net_amount = amount - fee
        wallet_field = 'balance' if validated_data['_settings_obj'].balance_source == 'balance' else 'balance_deposit'
        wallet_type = 'BALANCE' if wallet_field == 'balance' else 'BALANCE_DEPOSIT'

        # Create Transaction linked to withdrawal
        trx = Transaction.objects.create(
            user=user,
            product=None,
            upline_user=None,
            trx_id=f"WD-{uuid.uuid4().hex[:10].upper()}",
            type='WITHDRAW',
            amount=amount,
            description='Withdrawal request',
            status='PENDING',
            wallet_type=wallet_type,
        )

        withdrawal = Withdrawal.objects.create(
            user=user,
            bank_account=user_bank,
            amount=amount,
            fee=fee,
            net_amount=net_amount,
            status='PENDING',
            transaction=trx,
        )

        # Deduct user wallet immediately or mark for processing
        # For now, deduct on request from selected wallet
        setattr(user, wallet_field, getattr(user, wallet_field) - amount)
        user.save(update_fields=[wallet_field])

        return withdrawal
