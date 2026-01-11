from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from django.db.models import Sum, Count, Q, Case, When, IntegerField, Value, DecimalField
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from accounts.models import User, GeneralSetting, UserAddress
from accounts.serializers import DownlineOverviewSerializer, UserAddressSerializer
from deposits.models import Deposit
from products.models import Transaction, Investment
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.settings import api_settings
from django.contrib.auth import get_user_model, authenticate
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiExample, OpenApiResponse
from .serializers import RankLevelSerializer, RankStatusResponseSerializer
from .models import RankLevel
from .utils import calculate_user_rank_progress
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.exceptions import AuthenticationFailed

USER_TAG = "User API"
ADMIN_TAG = "Admin API"
from .serializers import (RegisterSerializer, UserSerializer, ChangePasswordByPhoneSerializer, 
                         AccountInfoSerializer, DownlineOverviewSerializer, DownlineMemberSerializer,
                         ProfileUpdateSerializer, DownlineStatsLevelSerializer, DownlineStatsResponseSerializer,
                         WithdrawPinSerializer)
from .balance_serializers import BalanceStatisticsSerializer
from products.models import Transaction, Investment
from deposits.models import Deposit
from withdrawal.models import Withdrawal

# Django template views
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect

User = get_user_model()

@method_decorator(csrf_exempt, name='dispatch')
class RegisterView(generics.CreateAPIView):
    """
    Register a new user with phone number authentication
    """
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    throttle_scope = 'auth_register'
    serializer_class = RegisterSerializer

    @extend_schema(
        description='Register a new user account',
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'username': {'type': 'string', 'description': 'Unique username'},
                    'phone': {'type': 'string', 'description': 'Nomor telepon sesuai input frontend (tanpa dipaksa awalan "0")'},
                    'password': {'type': 'string', 'format': 'password'},
                    'password2': {'type': 'string', 'format': 'password', 'description': 'Password confirmation'},
                    'email': {'type': 'string', 'format': 'email'},
                    'full_name': {'type': 'string'},
                    'referral_code': {'type': 'string', 'description': 'Optional referral code'}
                },
                'required': ['username', 'phone', 'password', 'password2', 'email', 'full_name']
            }
        },
        responses={
            201: OpenApiResponse(
                description='User successfully registered',
                examples=[
                    OpenApiExample(
                        'Success Response',
                        value={
                            'user': {
                                'id': 1,
                                'username': 'user123',
                                'phone': '085112345678',
                                'email': 'user@example.com',
                                'full_name': 'User Name',
                                'referral_code': 'ABC123'
                            },
                            'token': 'your_auth_token_here'
                        }
                    )
                ]
            ),
            400: OpenApiResponse(
                description='Invalid input',
                examples=[
                    OpenApiExample(
                        'Validation Error',
                        value={
                            'phone': ['This phone number is already in use.'],
                            'password': ['Password fields didn\'t match.'],
                            'referral_code': ['Invalid referral code.']
                        }
                    )
                ]
            )
        }
    )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        setting = GeneralSetting.objects.first()
        auto_login = True if setting is None else bool(setting.auto_login_on_register)
        if setting and setting.registration_bonus_enabled and setting.registration_bonus_amount and setting.registration_bonus_amount > 0:
            amt = setting.registration_bonus_amount
            wallet_field = 'balance' if setting.registration_bonus_wallet == 'balance' else 'balance_deposit'
            setattr(user, wallet_field, getattr(user, wallet_field) + amt)
            user.save(update_fields=[wallet_field])
            from products.models import Transaction
            from zoneinfo import ZoneInfo
            Transaction.objects.create(
                user=user,
                amount=amt,
                type='BONUS',
                status='COMPLETED',
                trx_id=f"REG-{user.id}-{timezone.localtime(timezone.now(), ZoneInfo('Asia/Jakarta')).strftime('%Y%m%d%H%M%S')}",
                wallet_type=wallet_field.upper(),
                description='Registration bonus'
            )

        response_data = {
            'user': UserSerializer(user).data,
        }

        if auto_login:
            token, _ = Token.objects.get_or_create(user=user)
            response_data['token'] = token.key

        return Response(response_data, status=status.HTTP_201_CREATED)

@extend_schema(exclude=True)
@method_decorator(csrf_exempt, name='dispatch')
@extend_schema(exclude=True)
class CustomAuthToken(ObtainAuthToken):
    """
    Custom auth token view that uses phone number instead of username
    """
    permission_classes = (AllowAny,)
    # Ensure global throttles apply; parent may disable throttling
    throttle_classes = api_settings.DEFAULT_THROTTLE_CLASSES
    throttle_scope = 'auth_login'
    @extend_schema(
        description='Login with phone number and password',
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'phone': {'type': 'string', 'description': 'Nomor telepon sesuai input frontend (tanpa dipaksa awalan "0")'},
                    'password': {'type': 'string', 'format': 'password'}
                },
                'required': ['phone', 'password']
            }
        },
        responses={
            200: OpenApiResponse(
                description='Login successful',
                examples=[
                    OpenApiExample(
                        'Success Response',
                        value={
                            'token': 'your_auth_token_here',
                            'user': {
                                'id': 1,
                                'phone': '085112345678',
                                'email': 'user@example.com',
                                'full_name': 'User Name',
                                'balance': '0.00',
                                'balance_deposit': '0.00',
                                'referral_code': 'ABC123'
                            }
                        }
                    )
                ]
            ),
            400: OpenApiResponse(
                description='Invalid credentials',
                examples=[
                    OpenApiExample(
                        'Error Response',
                        value={
                            'error': 'Invalid phone number or password'
                        }
                    )
                ]
            )
        }
    )
    def post(self, request, *args, **kwargs):
        phone = request.data.get('phone')
        password = request.data.get('password')
        
        if not phone or not password:
            return Response({
                'error': 'Please provide both phone and password'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        user = authenticate(request=request, username=phone, password=password)
        
        if user:
            token, created = Token.objects.get_or_create(user=user)
            return Response({
                'token': token.key,
                'user': UserSerializer(user).data
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'error': 'Invalid phone number or password'
            }, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(exclude=True)
@method_decorator(csrf_exempt, name='dispatch')
class LogoutView(APIView):
    """
    Logout the current user by invalidating their auth token
    """
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        description='Logout and invalidate current auth token',
        responses={
            200: OpenApiResponse(
                description='Logout successful',
                examples=[
                    OpenApiExample(
                        'Success Response',
                        value={
                            'detail': 'Successfully logged out.'
                        }
                    )
                ]
            ),
            401: OpenApiResponse(
                description='Unauthorized',
                examples=[
                    OpenApiExample(
                        'Error Response',
                        value={
                            'detail': 'Authentication credentials were not provided.'
                        }
                    )
                ]
            )
        }
    )
    def post(self, request):
        # Support both TokenAuthentication and SessionAuthentication
        try:
            # If token is present, delete it
            if getattr(request, 'auth', None):
                try:
                    request.auth.delete()
                except Exception:
                    pass

            # Also clear session if logged in via session
            if request.user.is_authenticated:
                logout(request)

            return Response({"detail": "Successfully logged out."}, status=status.HTTP_200_OK)
        except Exception:
            return Response({"detail": "Authentication credentials were not provided or invalid."}, 
                            status=status.HTTP_401_UNAUTHORIZED)

@method_decorator(csrf_exempt, name='dispatch')
class ChangePasswordByPhoneView(APIView):
    """
    Change user password by verifying phone and current password.
    """
    permission_classes = (AllowAny,)
    throttle_scope = 'auth_password_change'

    @extend_schema(
        description='Change password using phone and current password',
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'phone': {'type': 'string', 'description': 'Nomor telepon sesuai input frontend (tanpa dipaksa awalan "0")'},
                    'old_password': {'type': 'string', 'format': 'password'},
                    'new_password': {'type': 'string', 'format': 'password'}
                },
                'required': ['phone', 'old_password', 'new_password']
            }
        },
        responses={
            200: OpenApiResponse(
                description='Password changed successfully',
                examples=[
                    OpenApiExample(
                        'Success Response',
                        value={'detail': 'Password updated successfully.'}
                    )
                ]
            ),
            400: OpenApiResponse(
                description='Validation error',
                examples=[
                    OpenApiExample(
                        'Error Response',
                        value={'old_password': ['Current password is incorrect.']}
                    )
                ]
            )
        }
    )
    def post(self, request):
        serializer = ChangePasswordByPhoneSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({'detail': 'Password updated successfully.'}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@method_decorator(csrf_exempt, name='dispatch')
class AccountInfoView(APIView):
    """
    Get authenticated user's account information
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = AccountInfoSerializer

    @extend_schema(
        description='Get current user account information',
        responses={
            200: OpenApiResponse(
                description='Account information retrieved successfully',
                examples=[
                    OpenApiExample(
                        'Success Response',
                        value={
                            'id': 1,
                            'username': 'user123',
                            'email': 'user@example.com',
                            'full_name': 'User Name',
                            'phone': '085112345678',
                            'balance': '1000.00',
                            'balance_deposit': '500.00',
                            'referral_by_username': 'referrer123',
                            'referral_by_phone': '085987654321',
                            'root_parent_username': 'root_user',
                            'root_parent_phone': '085111111111',
                            'referral_code': 'ABC123',
                            'rank': 1,
                            'created_at': '2024-01-01T00:00:00Z',
                            'updated_at': '2024-01-01T00:00:00Z'
                        }
                    )
                ]
            ),
            401: OpenApiResponse(
                description='Unauthorized',
                examples=[
                    OpenApiExample(
                        'Error Response',
                        value={
                            'detail': 'Authentication credentials were not provided.'
                        }
                    )
                ]
            )
        }
    )
    def get(self, request):
        """Get current user's account information"""
        serializer = self.serializer_class(request.user, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name='dispatch')
class ProfileUpdateView(APIView):
    """
    Update user profile - only full_name and username
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = ProfileUpdateSerializer

    @extend_schema(
        description='Update user profile (full_name and username only)',
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'full_name': {'type': 'string', 'description': 'Full name of the user'},
                    'username': {'type': 'string', 'description': 'Username (must be unique)'}
                }
            }
        },
        responses={
            200: OpenApiResponse(
                description='Profile updated successfully',
                examples=[
                    OpenApiExample(
                        'Success Response',
                        value={
                            'full_name': 'Updated Full Name',
                            'username': 'updated_username'
                        }
                    )
                ]
            ),
            400: OpenApiResponse(
                description='Validation error',
                examples=[
                    OpenApiExample(
                        'Error Response',
                        value={
                            'username': ['Username sudah digunakan oleh user lain.']
                        }
                    )
                ]
            ),
            401: OpenApiResponse(
                description='Unauthorized',
                examples=[
                    OpenApiExample(
                        'Error Response',
                        value={
                            'detail': 'Authentication credentials were not provided.'
                        }
                    )
                ]
            )
        }
    )
    def put(self, request):
        """Update user profile"""
        serializer = self.serializer_class(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(csrf_exempt, name='dispatch')
class DownlineOverviewView(APIView):
    """
    API endpoint to get downline members overview with commission statistics
    """
    permission_classes = (IsAuthenticated,)
    
    def _get_downlines_by_level(self, user, max_level=5):
        """Get downline members organized by level (1-5) with bulk aggregations"""
        levels_data = {}
        current_level = [user]

        for level in range(1, max_level + 1):
            downlines_qs = User.objects.filter(referral_by__in=current_level)
            level_members = list(downlines_qs)
            next_level = level_members

            if level_members:
                ids = [m.id for m in level_members]

                tx_map = {
                    r['upline_user_id']: r
                    for r in Transaction.objects.filter(user=user, upline_user_id__in=ids)
                    .values('upline_user_id')
                    .annotate(
                        total_profit_commission=Sum(
                            Case(
                                When(type='PROFIT_COMMISSION', then='amount'),
                                default=Value(0),
                                output_field=DecimalField(max_digits=15, decimal_places=2),
                            )
                        ),
                        total_purchase_commission=Sum(
                            Case(
                                When(type='PURCHASE_COMMISSION', then='amount'),
                                default=Value(0),
                                output_field=DecimalField(max_digits=15, decimal_places=2),
                            )
                        ),
                        total_earned_commission=Sum(
                            Case(
                                When(type='EARNED', then='amount'),
                                default=Value(0),
                                output_field=DecimalField(max_digits=15, decimal_places=2),
                            )
                        ),
                        commission_count=Count(
                            Case(
                                When(
                                    type__in=['PROFIT_COMMISSION', 'PURCHASE_COMMISSION', 'EARNED'],
                                    then=1,
                                ),
                                output_field=IntegerField(),
                            )
                        ),
                    )
                }

                inv_map = {
                    r['user_id']: r
                    for r in Investment.objects.filter(user_id__in=ids)
                    .values('user_id')
                    .annotate(
                        total_investments=Count('id'),
                        total_investment_amount=Sum('total_amount'),
                        active_investments=Count(Case(When(status='ACTIVE', then=1), output_field=IntegerField())),
                    )
                }

                dep_map = {
                    r['user_id']: r
                    for r in Deposit.objects.filter(user_id__in=ids, status='COMPLETED')
                    .values('user_id')
                    .annotate(
                        total_deposits=Count('id'),
                        total_deposit_amount=Sum('amount'),
                    )
                }

                for m in level_members:
                    t = tx_map.get(m.id, {})
                    i = inv_map.get(m.id, {})
                    d = dep_map.get(m.id, {})

                    m.total_profit_commission = t.get('total_profit_commission', 0) or 0
                    m.total_purchase_commission = t.get('total_purchase_commission', 0) or 0
                    m.total_earned_commission = t.get('total_earned_commission', 0) or 0
                    m.commission_count = t.get('commission_count', 0) or 0

                    m.total_investments = i.get('total_investments', 0) or 0
                    m.total_investment_amount = i.get('total_investment_amount', 0) or 0
                    m.active_investments = i.get('active_investments', 0) or 0
                    m.is_active = (m.total_investments > 0)

                    m.total_deposits = d.get('total_deposits', 0) or 0
                    m.total_deposit_amount = d.get('total_deposit_amount', 0) or 0
                    m.completed_deposits = d.get('total_deposits', 0) or 0

                    m.transaction_history = Transaction.objects.filter(
                        user=user,
                        upline_user=m,
                        type__in=['PURCHASE_COMMISSION', 'PROFIT_COMMISSION']
                    ).select_related('product', 'user').order_by('-created_at')[:20]

                levels_data[level] = {
                    'level': level,
                    'member_count': len(level_members),
                    'total_profit_commission': sum(m.total_profit_commission for m in level_members),
                    'total_purchase_commission': sum(m.total_purchase_commission for m in level_members),
                    'total_earned_commission': sum(m.total_earned_commission for m in level_members),
                    'total_investments': sum(m.total_investments for m in level_members),
                    'total_investment_amount': sum(m.total_investment_amount for m in level_members),
                    'active_investments': sum(m.active_investments for m in level_members),
                    'total_deposits': sum(m.total_deposits for m in level_members),
                    'total_deposit_amount': sum(m.total_deposit_amount for m in level_members),
                    'completed_deposits': sum(m.completed_deposits for m in level_members),
                    'members': level_members,
                }

            current_level = next_level
            if not current_level:
                break

        return levels_data
    
    @extend_schema(
        description='Get downline members overview with commission statistics (levels 1-5)',
        responses={
            200: OpenApiResponse(
                description='Downline overview retrieved successfully',
                examples=[
                    OpenApiExample(
                        'Success Response',
                        value={
                            'total_members': 25,
                            'total_profit_commission': '150000.00',
                            'total_purchase_commission': '75000.00',
                            'total_earned_commission': '50000.00',
                            'levels': [
                                {
                                    'level': 1,
                                    'member_count': 10,
                                    'total_profit_commission': '100000.00',
                                    'total_purchase_commission': '50000.00',
                                    'total_earned_commission': '30000.00',
                                    'members': [
                                        {
                                            'id': 2,
                                            'username': 'member1',
                                            'phone': '085123456789',
                                            'full_name': 'Member One',
                                            'created_at': '2024-01-01T00:00:00Z',
                                            'total_profit_commission': '10000.00',
                                            'total_purchase_commission': '5000.00',
                                            'total_earned_commission': '3000.00',
                                            'commission_count': 5
                                        }
                                    ]
                                }
                            ]
                        }
                    )
                ]
            ),
            401: OpenApiResponse(
                description='Unauthorized',
                examples=[
                    OpenApiExample(
                        'Error Response',
                        value={
                            'detail': 'Authentication credentials were not provided.'
                        }
                    )
                ]
            )
        }
    )
    def get(self, request):
        """Get downline members overview with commission statistics"""
        user = request.user
        levels_data = self._get_downlines_by_level(user)
        
        # Calculate overall totals
        total_members = sum(level['member_count'] for level in levels_data.values())
        total_profit_commission = sum(level['total_profit_commission'] for level in levels_data.values())
        total_purchase_commission = sum(level['total_purchase_commission'] for level in levels_data.values())
        total_earned_commission = sum(level['total_earned_commission'] for level in levels_data.values())
        
        # Calculate overall investment totals
        total_investments = sum(level['total_investments'] for level in levels_data.values())
        total_investment_amount = sum(level['total_investment_amount'] for level in levels_data.values())
        active_investments = sum(level['active_investments'] for level in levels_data.values())
        
        # Calculate overall deposit totals
        total_deposits = sum(level['total_deposits'] for level in levels_data.values())
        total_deposit_amount = sum(level['total_deposit_amount'] for level in levels_data.values())
        completed_deposits = sum(level['completed_deposits'] for level in levels_data.values())
        
        # Prepare response data
        response_data = {
            'total_members': total_members,
            'total_profit_commission': total_profit_commission,
            'total_purchase_commission': total_purchase_commission,
            'total_earned_commission': total_earned_commission,
            'total_investments': total_investments,
            'total_investment_amount': total_investment_amount,
            'active_investments': active_investments,
            'total_deposits': total_deposits,
            'total_deposit_amount': total_deposit_amount,
            'completed_deposits': completed_deposits,
            'levels': []
        }
        
        # Add levels data in order
        for level in range(1, 6):
            if level in levels_data:
                level_data = levels_data[level]
                # Hapus serialisasi dini; biarkan DownlineOverviewSerializer menangani nested members
                # Serialize members
                # members_serializer = DownlineMemberSerializer(level_data['members'], many=True)
                # level_data['members'] = members_serializer.data
                response_data['levels'].append(level_data)
        
        serializer = DownlineOverviewSerializer(response_data)
        return Response(serializer.data, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name='dispatch')
class AdminDownlineOverviewView(APIView):
    """
    Admin-only endpoint to inspect a user's downline overview up to 3 levels.
    Provide target user's phone via query param `phone`.
    """
    permission_classes = (IsAuthenticated, IsAdminUser,)

    def _get_downlines_by_level(self, target_user, max_level=3):
        """Get downline members organized by level (1..max_level) for target_user with bulk aggregations"""
        levels_data = {}
        current_level = [target_user]

        for level in range(1, max_level + 1):
            downlines_qs = User.objects.filter(referral_by__in=current_level)
            level_members = list(downlines_qs)
            next_level = level_members

            if level_members:
                ids = [m.id for m in level_members]

                tx_map = {
                    r['upline_user_id']: r
                    for r in Transaction.objects.filter(user=target_user, upline_user_id__in=ids)
                    .values('upline_user_id')
                    .annotate(
                        total_profit_commission=Sum(
                            Case(
                                When(type='PROFIT_COMMISSION', then='amount'),
                                default=Value(0),
                                output_field=DecimalField(max_digits=15, decimal_places=2),
                            )
                        ),
                        total_purchase_commission=Sum(
                            Case(
                                When(type='PURCHASE_COMMISSION', then='amount'),
                                default=Value(0),
                                output_field=DecimalField(max_digits=15, decimal_places=2),
                            )
                        ),
                        total_earned_commission=Sum(
                            Case(
                                When(type='EARNED', then='amount'),
                                default=Value(0),
                                output_field=DecimalField(max_digits=15, decimal_places=2),
                            )
                        ),
                        commission_count=Count(
                            Case(
                                When(
                                    type__in=['PROFIT_COMMISSION', 'PURCHASE_COMMISSION', 'EARNED'],
                                    then=1,
                                ),
                                output_field=IntegerField(),
                            )
                        ),
                    )
                }

                inv_map = {
                    r['user_id']: r
                    for r in Investment.objects.filter(user_id__in=ids)
                    .values('user_id')
                    .annotate(
                        total_investments=Count('id'),
                        total_investment_amount=Sum('total_amount'),
                        active_investments=Count(Case(When(status='ACTIVE', then=1), output_field=IntegerField())),
                    )
                }

                dep_map = {
                    r['user_id']: r
                    for r in Deposit.objects.filter(user_id__in=ids, status='COMPLETED')
                    .values('user_id')
                    .annotate(
                        total_deposits=Count('id'),
                        total_deposit_amount=Sum('amount'),
                    )
                }

                for m in level_members:
                    t = tx_map.get(m.id, {})
                    i = inv_map.get(m.id, {})
                    d = dep_map.get(m.id, {})

                    m.total_profit_commission = t.get('total_profit_commission', 0) or 0
                    m.total_purchase_commission = t.get('total_purchase_commission', 0) or 0
                    m.total_earned_commission = t.get('total_earned_commission', 0) or 0
                    m.commission_count = t.get('commission_count', 0) or 0

                    m.total_investments = i.get('total_investments', 0) or 0
                    m.total_investment_amount = i.get('total_investment_amount', 0) or 0
                    m.active_investments = i.get('active_investments', 0) or 0
                    m.is_active = (m.total_investments > 0)

                    m.total_deposits = d.get('total_deposits', 0) or 0
                    m.total_deposit_amount = d.get('total_deposit_amount', 0) or 0
                    m.completed_deposits = d.get('total_deposits', 0) or 0

                    m.transaction_history = Transaction.objects.filter(
                        user=target_user,
                        upline_user=m,
                        type__in=['PURCHASE_COMMISSION', 'PROFIT_COMMISSION']
                    ).select_related('product', 'user').order_by('-created_at')[:50]

                levels_data[level] = {
                    'level': level,
                    'member_count': len(level_members),
                    'total_profit_commission': sum(m.total_profit_commission for m in level_members),
                    'total_purchase_commission': sum(m.total_purchase_commission for m in level_members),
                    'total_earned_commission': sum(m.total_earned_commission for m in level_members),
                    'total_investments': sum(m.total_investments for m in level_members),
                    'total_investment_amount': sum(m.total_investment_amount for m in level_members),
                    'active_investments': sum(m.active_investments for m in level_members),
                    'total_deposits': sum(m.total_deposits for m in level_members),
                    'total_deposit_amount': sum(m.total_deposit_amount for m in level_members),
                    'completed_deposits': sum(m.completed_deposits for m in level_members),
                    'members': level_members,
                }

            current_level = next_level
            if not current_level:
                break

        return levels_data

    @extend_schema(
        tags=[ADMIN_TAG],
        description='Admin: overview downline user target (by phone) up to 3 levels',
    )
    def get(self, request):
        phone = request.query_params.get('phone')
        if not phone:
            return Response({'error': 'Parameter "phone" wajib diisi'}, status=status.HTTP_400_BAD_REQUEST)

        target_user = User.objects.filter(phone=phone).first()
        if not target_user:
            return Response({'error': 'User dengan phone tersebut tidak ditemukan'}, status=status.HTTP_404_NOT_FOUND)

        levels_data = self._get_downlines_by_level(target_user, max_level=3)

        # Overall totals
        total_members = sum(level['member_count'] for level in levels_data.values())
        total_profit_commission = sum(level['total_profit_commission'] for level in levels_data.values())
        total_purchase_commission = sum(level['total_purchase_commission'] for level in levels_data.values())
        total_earned_commission = sum(level['total_earned_commission'] for level in levels_data.values())

        total_investments = sum(level['total_investments'] for level in levels_data.values())
        total_investment_amount = sum(level['total_investment_amount'] for level in levels_data.values())
        active_investments = sum(level['active_investments'] for level in levels_data.values())

        total_deposits = sum(level['total_deposits'] for level in levels_data.values())
        total_deposit_amount = sum(level['total_deposit_amount'] for level in levels_data.values())
        completed_deposits = sum(level['completed_deposits'] for level in levels_data.values())

        response_data = {
            'total_members': total_members,
            'total_profit_commission': total_profit_commission,
            'total_purchase_commission': total_purchase_commission,
            'total_earned_commission': total_earned_commission,
            'total_investments': total_investments,
            'total_investment_amount': total_investment_amount,
            'active_investments': active_investments,
            'total_deposits': total_deposits,
            'total_deposit_amount': total_deposit_amount,
            'completed_deposits': completed_deposits,
            'levels': [],
        }

        for level in range(1, 4):
            if level in levels_data:
                response_data['levels'].append(levels_data[level])

        serializer = DownlineOverviewSerializer(response_data)
        return Response(serializer.data, status=status.HTTP_200_OK)


# Django Template Views for Testing
@csrf_protect
def user_login(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        phone = request.POST.get('phone')
        password = request.POST.get('password')
        
        user = authenticate(request, username=phone, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f'Welcome back, {user.phone}!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid phone number or password.')
    
    return render(request, 'accounts/login.html')

@login_required
def dashboard(request):
    return render(request, 'accounts/dashboard.html', {'user': request.user})


class BalanceStatisticsView(APIView):
    """
    API untuk mendapatkan statistik balance, deposit, withdraw, dan komisi
    Mendukung 2 versi: today dan all_time
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, period=None):
        """
        GET /api/accounts/balance-statistics/{period}/
        period: 'today' atau 'all-time'
        """
        user = request.user
        
        # Validasi period parameter
        if period not in ['today', 'all-time']:
            return Response({
                'error': 'Invalid period. Use "today" or "all-time"'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Set date filter berdasarkan period
        if period == 'today':
            today = timezone.now().date()
            date_filter = Q(created_at__date=today)
            period_label = 'today'
        else:
            date_filter = Q()  # No date filter for all time
            period_label = 'all_time'
        
        # Current balance dari user
        current_balance = user.balance
        current_balance_deposit = user.balance_deposit
        
        # Deposit statistics (COMPLETED only)
        deposit_stats = Deposit.objects.filter(
            user=user,
            status='COMPLETED'
        ).filter(date_filter).aggregate(
            total_amount=Sum('amount'),
            total_count=Count('id')
        )
        
        total_deposit_completed = deposit_stats['total_amount'] or Decimal('0.00')
        total_deposit_count = deposit_stats['total_count'] or 0
        
        # Withdrawal statistics (COMPLETED only)
        withdrawal_stats = Withdrawal.objects.filter(
            user=user,
            status='COMPLETED'
        ).filter(date_filter).aggregate(
            total_amount=Sum('amount'),
            total_count=Count('id')
        )
        
        total_withdraw_completed = withdrawal_stats['total_amount'] or Decimal('0.00')
        total_withdraw_count = withdrawal_stats['total_count'] or 0
        
        # Commission statistics dari Transaction
        commission_filter = Q(user=user, status='COMPLETED') & date_filter
        
        # Profit Commission
        profit_commission = Transaction.objects.filter(
            commission_filter,
            type='PROFIT_COMMISSION'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Purchase Commission  
        purchase_commission = Transaction.objects.filter(
            commission_filter,
            type='PURCHASE_COMMISSION'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Interest (profit claim)
        interest_total = Transaction.objects.filter(
            commission_filter,
            type='INTEREST'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Voucher credit
        voucher_total = Transaction.objects.filter(
            commission_filter,
            type='VOUCHER'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Attendance credit
        attendance_total = Transaction.objects.filter(
            commission_filter,
            type='ATTENDANCE'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Manual credit
        credit_total = Transaction.objects.filter(
            commission_filter,
            type='CREDIT'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        total_cashback = Transaction.objects.filter(
            commission_filter,
            type='CASHBACK'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Mission rewards
        missions_total = Transaction.objects.filter(
            commission_filter,
            type='MISSIONS'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Total Commission
        total_commission = profit_commission + purchase_commission
        
        # Total income (keuntungan all-time)
        total_income = interest_total + total_commission + voucher_total + attendance_total + credit_total + missions_total + total_cashback
        
        # Total transactions count
        total_transactions = Transaction.objects.filter(
            Q(user=user, status='COMPLETED') & date_filter
        ).count()

        # Active investments / products owned (independen dari period)
        active_investments_qs = Investment.objects.filter(user=user, status='ACTIVE')
        active_investments_count = active_investments_qs.count()
        products_summary = active_investments_qs.values('product_id', 'product__name').annotate(
            active_count=Count('id'),
            total_quantity=Sum('quantity'),
            total_amount=Sum('total_amount'),
        )
        active_products = [
            {
                'product_id': item['product_id'],
                'name': item['product__name'],
                'active_count': item['active_count'],
                'total_quantity': item['total_quantity'] or 0,
                'total_amount': item['total_amount'] or Decimal('0.00'),
            }
            for item in products_summary
        ]

        # Hitung total anggota aktif per level downline (level 1-3)
        try:
            active_members_level_1 = 0
            active_members_level_2 = 0
            active_members_level_3 = 0

            current_level_users = [user]
            for lvl in range(1, 3 + 1):
                level_users = []
                for u in current_level_users:
                    # Ambil referrals untuk level ini
                    ds = list(u.referrals.all())
                    level_users.extend(ds)
                # Hitung aktif: punya investasi status ACTIVE
                active_count = 0
                for d in level_users:
                    if Investment.objects.filter(user=d, status='ACTIVE').exists():
                        active_count += 1
                if lvl == 1:
                    active_members_level_1 = active_count
                elif lvl == 2:
                    active_members_level_2 = active_count
                elif lvl == 3:
                    active_members_level_3 = active_count
                current_level_users = level_users
            active_members_total_1_3 = active_members_level_1 + active_members_level_2 + active_members_level_3
        except Exception:
            active_members_level_1 = 0
            active_members_level_2 = 0
            active_members_level_3 = 0
            active_members_total_1_3 = 0
        
        # Prepare response data
        response_data = {
            'balance': current_balance,
            'balance_deposit': current_balance_deposit,
            'total_deposit_completed': total_deposit_completed,
            'total_deposit_count': total_deposit_count,
            'total_withdraw_completed': total_withdraw_completed,
            'total_withdraw_count': total_withdraw_count,
            'total_commission': total_commission,
            'profit_commission': profit_commission,
            'purchase_commission': purchase_commission,
            'interest_total': interest_total,
            # Tambahkan total attendance
            'attendance_total': attendance_total,
            'total_income': total_income,
            'total_cashback': total_cashback,

            'total_transactions': total_transactions,
            'period': period_label,
            'active_investments_count': active_investments_count,
            'active_products': active_products,
            # Downline aktif per level
            'active_members_level_1': active_members_level_1,
            'active_members_level_2': active_members_level_2,
            'active_members_level_3': active_members_level_3,
            'active_members_total_1_3': active_members_total_1_3,
        }
        
        serializer = BalanceStatisticsSerializer(response_data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class BalanceStatisticsTodayView(BalanceStatisticsView):
    """
    API khusus untuk statistik balance hari ini
    GET /api/accounts/balance-statistics/today/
    """
    
    def get(self, request):
        return super().get(request, period='today')


class BalanceStatisticsAllTimeView(BalanceStatisticsView):
    """
    API khusus untuk statistik balance sepanjang waktu
    GET /api/accounts/balance-statistics/all-time/
    """
    
    def get(self, request):
        return super().get(request, period='all-time')


def user_logout(request):
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('user_login')



@method_decorator(csrf_exempt, name='dispatch')
class DownlineStatsView(APIView):
    """
    API untuk statistik anggota downline level 1-5:
    - Total anggota per level (aktif vs tidak aktif)
    - Total deposit (COMPLETED) per level
    - Total withdraw (COMPLETED) per level
    - Total commission per level (profit & purchase)
    """
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=[USER_TAG],
        description='Dapatkan statistik downline per level (1-5): members, deposit, withdraw, commission',
        responses={
            200: OpenApiResponse(
                response=DownlineStatsResponseSerializer,
                description='Statistik berhasil diambil',
                examples=[
                    OpenApiExample(
                        'Contoh Respons',
                        value={
                            'levels': [
                                {
                                    'level': 1,
                                    'members_total': 3,
                                    'members_active': 2,
                                    'members_inactive': 1,
                                    'deposits_total_count': 5,
                                    'deposits_total_amount': '150000.00',
                                    'withdrawals_completed_count': 2,
                                    'withdrawals_completed_amount': '50000.00',
                                    'profit_commission_amount': '25000.00',
                                    'purchase_commission_amount': '10000.00'
                                }
                            ]
                        }
                    )
                ]
            ),
            401: OpenApiResponse(
                description='Unauthorized',
                examples=[
                    OpenApiExample(
                        'Error Response',
                        value={'detail': 'Authentication credentials were not provided.'}
                    )
                ]
            )
        }
    )
    def get(self, request):
        user = request.user
        levels = []
        current_level = [user]

        for level in range(1, 6):
            next_level = []
            member_ids = []

            for u in current_level:
                for d in u.referrals.all():
                    next_level.append(d)
                    member_ids.append(d.id)

            members_total = len(member_ids)

            # Aktif jika punya investasi apapun
            active_user_ids = set(
                Investment.objects.filter(user_id__in=member_ids)
                .values_list('user_id', flat=True)
                .distinct()
            )
            members_active = len(active_user_ids)
            members_inactive = members_total - members_active

            # Deposit totals (COMPLETED only)
            deposit_agg = Deposit.objects.filter(
                user_id__in=member_ids,
                status='COMPLETED'
            ).aggregate(
                total_amount=Sum('amount'),
                total_count=Count('id')
            )

            # Withdrawals (COMPLETED)
            withdraw_agg = Withdrawal.objects.filter(
                user_id__in=member_ids,
                status='COMPLETED'
            ).aggregate(
                total_amount=Sum('amount'),
                total_count=Count('id')
            )

            # Commission totals (to current user) per level
            profit_commission = Transaction.objects.filter(
                user=user,
                type='PROFIT_COMMISSION',
                commission_level=level
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

            purchase_commission = Transaction.objects.filter(
                user=user,
                type='PURCHASE_COMMISSION',
                commission_level=level
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

            level_data = {
                'level': level,
                'members_total': members_total,
                'members_active': members_active,
                'members_inactive': members_inactive,
                'deposits_total_count': deposit_agg.get('total_count') or 0,
                'deposits_total_amount': deposit_agg.get('total_amount') or Decimal('0.00'),
                'withdrawals_completed_count': withdraw_agg.get('total_count') or 0,
                'withdrawals_completed_amount': withdraw_agg.get('total_amount') or Decimal('0.00'),
                'profit_commission_amount': profit_commission,
                'purchase_commission_amount': purchase_commission,
            }

            levels.append(level_data)
            current_level = next_level

        serializer = DownlineStatsResponseSerializer({'levels': levels})
        return Response(serializer.data, status=status.HTTP_200_OK)


class RankLevelListView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["User API"],
        description="List konfigurasi RankLevel (syarat total misi per rank)",
        responses={200: OpenApiResponse(response=RankLevelSerializer)},
    )
    def get(self, request):
        levels = RankLevel.objects.all()
        # Calculate progress once
        user_progress = calculate_user_rank_progress(request.user)
        ser = RankLevelSerializer(levels, many=True, context={'request': request, 'user_progress': user_progress})
        return Response(ser.data)


class RankStatusView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["User API"],
        description="Status rank user saat ini dan info rank berikutnya",
        responses={200: OpenApiResponse(response=RankStatusResponseSerializer)},
    )
    def get(self, request):
        user = request.user
        progress_count = calculate_user_rank_progress(user)

        current_rank = user.rank
        current_level = RankLevel.objects.filter(rank=current_rank).first() if current_rank is not None else None
        current_title = current_level.title if current_level else None

        # Cari rank berikutnya yang syaratnya lebih besar dari progress sekarang
        next_level = RankLevel.objects.filter(missions_required_total__gt=progress_count).order_by('missions_required_total').first()

        return Response({
            'current_rank': current_rank,
            'current_title': current_title,
            'completed_missions': progress_count,
            'next_rank': next_level.rank if next_level else None,
            'next_title': next_level.title if next_level else None,
            'next_required_missions': next_level.missions_required_total if next_level else None,
        }, status=status.HTTP_200_OK)


class PhoneTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        phone = attrs.get('phone')
        password = attrs.get('password')
        if not phone or not password:
            raise AuthenticationFailed('Please provide both phone and password')
        user = authenticate(request=self.context.get('request'), username=phone, password=password)
        if not user:
            raise AuthenticationFailed('Invalid phone number or password')
        if not user.is_active:
            raise AuthenticationFailed('User account is disabled')
        self.user = user
        refresh = self.get_token(user)
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': UserSerializer(user).data,
        }

class PhoneTokenObtainPairView(TokenObtainPairView):
    permission_classes = (AllowAny,)
    throttle_classes = api_settings.DEFAULT_THROTTLE_CLASSES
    throttle_scope = 'auth_login'
    serializer_class = PhoneTokenObtainPairSerializer

    @extend_schema(
        summary="Login dengan phone + password (JWT)",
        tags=[USER_TAG],
        responses={
            200: OpenApiResponse(
                description="Login sukses, kembalikan access dan refresh token",
                examples=[
                    OpenApiExample(
                        'Success',
                        value={
                            "access": "<jwt_access>",
                            "refresh": "<jwt_refresh>",
                            "user": {
                                "id": 1,
                                "phone": "085112345678",
                                "email": "user@example.com",
                                "full_name": "User Name",
                                "balance": "0.00",
                                "balance_deposit": "0.00",
                                "referral_code": "ABC123",
                            },
                        },
                    ),
                ],
            ),
            401: OpenApiResponse(
                description="Login gagal",
                examples=[
                    OpenApiExample(
                        'Error',
                        value={"detail": "Invalid phone number or password"},
                    ),
                ],
            ),
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        try:
            serializer.is_valid(raise_exception=True)
        except AuthenticationFailed as e:
            return Response({"detail": str(e)}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name='dispatch')
class WithdrawPinView(APIView):
    permission_classes = (IsAuthenticated,)
    throttle_scope = 'auth_pin'

    @extend_schema(
        tags=[USER_TAG],
        summary='Set or update withdrawal PIN (6 digits)',
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'pin': {'type': 'string', 'description': 'New PIN (6 digits)'},
                    'current_pin': {'type': 'string', 'description': 'Current PIN (required if updating)', 'nullable': True},
                },
                'required': ['pin']
            }
        },
        responses={
            200: OpenApiResponse(description='PIN set/updated successfully', examples=[]),
            400: OpenApiResponse(description='Validation error', examples=[]),
            401: OpenApiResponse(description='Unauthorized', examples=[]),
        }
    )
    def post(self, request):
        serializer = WithdrawPinSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'detail': 'Withdrawal PIN updated successfully.'}, status=status.HTTP_200_OK)

    @extend_schema(
        tags=[USER_TAG],
        summary='Check if withdrawal PIN is set',
        responses={
            200: OpenApiResponse(description='PIN status', examples=[]),
            401: OpenApiResponse(description='Unauthorized', examples=[]),
        }
    )
    def get(self, request):
        return Response({'pin_set': bool(request.user.withdraw_pin)}, status=status.HTTP_200_OK)


class TopActiveLevel1View(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        tags=[USER_TAG],
        summary='Top 10 users dengan downline level-1 aktif terbanyak',
        responses={
            200: OpenApiResponse(description='Daftar top 10')
        }
    )
    def get(self, request):
        from products.models import Investment
        from django.db.models import Count

        rows = (
            Investment.objects
            .filter(
                status='ACTIVE',
                user__referral_by__isnull=False,
                user__referral_by__is_staff=False,
                user__referral_by__is_superuser=False,
            )
            .values('user__referral_by')
            .annotate(active_level1_count=Count('user', distinct=True))
            .order_by('-active_level1_count')[:10]
        )

        user_map = {r['user__referral_by']: r['active_level1_count'] for r in rows}
        users = User.objects.filter(
            id__in=list(user_map.keys()),
            is_staff=False,
            is_superuser=False,
        )
        results = [
            {
                'id': u.id,
                'phone': u.phone,
                'full_name': u.full_name,
                'active_level1_count': int(user_map.get(u.id, 0)),
            }
            for u in users
        ]
        results.sort(key=lambda x: x['active_level1_count'], reverse=True)
        return Response({'count': len(results), 'results': results}, status=status.HTTP_200_OK)


@extend_schema_view(
    get=extend_schema(
        tags=[USER_TAG],
        summary="List alamat user",
        responses={
            200: OpenApiResponse(response=UserAddressSerializer(many=True)),
        },
    ),
    post=extend_schema(
        tags=[USER_TAG],
        summary="Tambah alamat user",
        request=UserAddressSerializer,
        responses={
            201: OpenApiResponse(response=UserAddressSerializer),
        },
    ),
)
class UserAddressListCreateView(generics.ListCreateAPIView):
    serializer_class = UserAddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return UserAddress.objects.filter(user=self.request.user)


class TopDepositorsView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        tags=[USER_TAG],
        summary='Top 10 users dengan total deposit terbanyak (completed)',
        responses={
            200: OpenApiResponse(description='Daftar top 10 depositor')
        }
    )
    def get(self, request):
        from deposits.models import Deposit
        from django.db.models import Sum

        rows = (
            Deposit.objects
            .filter(
                status='COMPLETED',
                user__is_staff=False,
                user__is_superuser=False,
            )
            .values('user')
            .annotate(total_deposit=Sum('amount'))
            .order_by('-total_deposit')[:10]
        )

        user_map = {r['user']: r['total_deposit'] for r in rows}
        users = User.objects.filter(id__in=list(user_map.keys()))
        
        results = [
            {
                'id': u.id,
                'phone': u.phone,
                'full_name': u.full_name,
                'total_deposit': str(user_map.get(u.id, 0)),
            }
            for u in users
        ]
        # Re-sort because filtering by id might lose order
        results.sort(key=lambda x: float(x['total_deposit']), reverse=True)
        
        return Response({'count': len(results), 'results': results}, status=status.HTTP_200_OK)


@extend_schema_view(
    get=extend_schema(
        tags=[USER_TAG],
        summary="Detail alamat user",
        responses={
            200: OpenApiResponse(response=UserAddressSerializer),
        },
    ),
    put=extend_schema(
        tags=[USER_TAG],
        summary="Update alamat user",
        request=UserAddressSerializer,
        responses={
            200: OpenApiResponse(response=UserAddressSerializer),
        },
    ),
    patch=extend_schema(
        tags=[USER_TAG],
        summary="Partial update alamat user",
        request=UserAddressSerializer,
        responses={
            200: OpenApiResponse(response=UserAddressSerializer),
        },
    ),
    delete=extend_schema(
        tags=[USER_TAG],
        summary="Hapus alamat user",
        responses={
            204: OpenApiResponse(description="Deleted"),
        },
    ),
)
class UserAddressDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = UserAddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return UserAddress.objects.filter(user=self.request.user)
