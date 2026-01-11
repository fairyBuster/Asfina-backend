from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, OpenApiResponse
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
import random
from .models import AttendanceSettings, AttendanceLog
from products.models import Transaction
import uuid
from .serializers import AttendanceSettingsSerializer, AttendanceLogSerializer
from zoneinfo import ZoneInfo


USER_TAG = "User API"
ADMIN_TAG = "Admin API"


class AttendanceSettingsViewSet(viewsets.ModelViewSet):
    queryset = AttendanceSettings.objects.all()
    serializer_class = AttendanceSettingsSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [IsAuthenticated()]

    @extend_schema(
        tags=[ADMIN_TAG],
        responses={
            200: OpenApiResponse(response=AttendanceSettingsSerializer(many=True), description='List attendance settings'),
        },
        description='List all attendance settings (admin-only for write operations)'
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=[USER_TAG],
        responses={
            200: OpenApiResponse(response=AttendanceSettingsSerializer, description='Get active attendance settings'),
            404: OpenApiResponse(description='No active settings found'),
        },
        description='Retrieve the currently active attendance settings'
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        tags=[USER_TAG],
        responses={
            200: OpenApiResponse(response=AttendanceSettingsSerializer, description='Active attendance settings'),
            404: OpenApiResponse(description='No active settings found'),
        },
        description='Get the first active attendance settings'
    )
    @action(detail=False, methods=['get'], url_path='active')
    def get_active(self, request):
        settings = AttendanceSettings.objects.filter(is_active=True).order_by('-created_at').first()
        if not settings:
            return Response({'detail': 'No active settings found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(AttendanceSettingsSerializer(settings).data)


class AttendanceLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AttendanceLogSerializer
    permission_classes = [IsAuthenticated]
    throttle_scope = 'attendance_claim'

    def get_queryset(self):
        # Users can only see their own logs; admin can see all
        qs = AttendanceLog.objects.all()
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        return qs

    @extend_schema(
        tags=[USER_TAG],
        responses={
            200: OpenApiResponse(
                response=AttendanceLogSerializer,
                description='Klaim absensi harian berhasil'
            ),
            400: OpenApiResponse(description='Sudah klaim hari ini atau konfigurasi tidak tersedia')
        },
        description='Klaim absensi harian. Hanya bisa sekali per hari per user.'
    )
    @action(detail=False, methods=['post'], url_path='claim')
    def claim(self, request):
        user = request.user
        # Gunakan tanggal lokal Asia/Jakarta agar batas hari mengikuti waktu Indonesia
        local_zone = ZoneInfo('Asia/Jakarta')
        now_local = timezone.localtime(timezone.now(), local_zone)
        today = now_local.date()

        # Cek sudah klaim hari ini
        if AttendanceLog.objects.filter(user=user, date=today).exists():
            return Response({'error': 'Anda sudah klaim absensi hari ini.'}, status=status.HTTP_400_BAD_REQUEST)

        # Ambil setting aktif
        settings = AttendanceSettings.objects.filter(is_active=True).order_by('-created_at').first()
        if not settings:
            return Response({'error': 'Konfigurasi attendance tidak tersedia.'}, status=status.HTTP_400_BAD_REQUEST)

        # Hitung streak
        last_log = AttendanceLog.objects.filter(user=user).order_by('-date').first()
        yesterday = today - timezone.timedelta(days=1)
        if last_log and last_log.date == yesterday:
            streak = last_log.streak_count + 1
        else:
            streak = 1

        # Tentukan reward dasar berdasarkan reward_type
        rt = settings.reward_type
        if rt == 'fixed':
            base_amount = Decimal(settings.fixed_amount or 0)
        elif rt == 'random':
            min_amt = Decimal(settings.min_amount or 0)
            max_amt = Decimal(settings.max_amount or 0)
            if max_amt < min_amt:
                max_amt = min_amt
            rand_float = random.uniform(float(min_amt), float(max_amt))
            base_amount = Decimal(str(rand_float)).quantize(Decimal('0.01'))
        elif rt == 'rank':
            # Gunakan user.rank sebagai key '1'..'6'
            rank_key = str(user.rank or '').strip()
            amount_from_rank = None
            if rank_key:
                try:
                    amount_from_rank = Decimal(str(settings.rank_rewards.get(rank_key, 0)))
                except Exception:
                    amount_from_rank = Decimal('0')
            # Fallback jika rank tidak tersedia atau tidak terkonfigurasi
            base_amount = amount_from_rank if amount_from_rank and amount_from_rank > 0 else Decimal(settings.fixed_amount or 0)
        elif rt == 'daily':
            # Calculate day in cycle (1-based)
            cycle_days = settings.daily_cycle_days if settings.daily_cycle_days > 0 else 7
            cycle_day = (streak - 1) % cycle_days + 1
            cycle_key = str(cycle_day)
            
            try:
                base_amount = Decimal(str(settings.daily_rewards.get(cycle_key, 0)))
            except Exception:
                base_amount = Decimal('0')
                
            # Fallback if 0
            if base_amount <= 0:
                base_amount = Decimal(settings.fixed_amount or 0)
        else:
            # Default fallback bila reward_type tidak dikenali
            base_amount = Decimal(settings.fixed_amount or 0)

        # Bonus streak
        bonus = Decimal('0')
        if settings.consecutive_bonus_enabled:
            if streak == 7 and settings.bonus_7_days:
                bonus += Decimal(settings.bonus_7_days)
            if streak == 30 and settings.bonus_30_days:
                bonus += Decimal(settings.bonus_30_days)

        total_amount = (base_amount + bonus).quantize(Decimal('0.01'))

        # Tentukan sumber saldo sesuai konfigurasi
        balance_field = 'balance' if settings.balance_source == 'balance' else 'balance_deposit'
        wallet_type = 'BALANCE' if balance_field == 'balance' else 'BALANCE_DEPOSIT'

        with transaction.atomic():
            # Tambahkan reward ke sumber saldo yang dipilih
            current_balance = getattr(user, balance_field)
            setattr(user, balance_field, current_balance + total_amount)
            user.save()

            # Simpan log
            log = AttendanceLog.objects.create(
                user=user,
                date=today,
                streak_count=streak,
                amount=total_amount,
            )

            # Catat transaksi kredit ke tabel transactions
            trx_id = f'ATT-{timezone.now().strftime("%Y%m%d%H%M%S")}-{uuid.uuid4().hex[:6].upper()}'
            attendance_tx = Transaction.objects.create(
                user=user,
                product=None,
                type='ATTENDANCE',
                amount=total_amount,
                description='Daily attendance claim',
                status='COMPLETED',
                wallet_type=wallet_type,
                trx_id=trx_id
            )

        return Response({
            'message': 'Klaim absensi berhasil',
            'claimed_amount': str(total_amount),
            'streak': streak,
            'balance_type': settings.balance_source,
            'balance_after': str(getattr(user, balance_field)),
            'next_claim_date': str(today + timezone.timedelta(days=1)),
            'log': AttendanceLogSerializer(log).data,
            'transaction_id': attendance_tx.trx_id
        })