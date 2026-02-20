from decimal import Decimal
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from drf_spectacular.utils import extend_schema, OpenApiResponse

from .models import Mission, MissionUserState
from .serializers import (
    MissionSerializer,
    ClaimMissionSerializer,
    MissionListResponseSerializer,
    ClaimMissionResponseSerializer,
)
from .utils import compute_mission_progress
from products.models import Transaction
from accounts.models import RankLevel, GeneralSetting
from products.models import Investment
from deposits.models import Deposit
from django.db.models import Sum


class MissionListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["User API"],
        description="List active missions with user-specific progress and claimability",
        responses={200: OpenApiResponse(response=MissionListResponseSerializer)},
    )
    def get(self, request):
        missions = Mission.objects.filter(is_active=True)
        states = MissionUserState.objects.filter(user=request.user, mission__in=missions)
        state_map = {s.mission_id: s for s in states}
        groups = {}
        mission_by_id = {m.id: m for m in missions}
        for m in missions:
            lvls = [lvl for lvl in (m.referral_levels or []) if lvl in [1, 2, 3]]
            key = (m.type, tuple(lvls) if lvls else ('default',))
            groups.setdefault(key, []).append(m.id)
        progress_map = {}
        deposit_totals_map = {}
        for key, ids in groups.items():
            try:
                sample = mission_by_id.get(ids[0])
                val = compute_mission_progress(sample, request.user) if sample else 0
            except Exception:
                val = 0
            for mid in ids:
                progress_map[mid] = val
            try:
                if sample and sample.type == 'deposit':
                    lvls = [lvl for lvl in (sample.referral_levels or []) if lvl in [1, 2, 3]] or [1]
                    # Compute decimal sum for downline deposits
                    downline_ids = []
                    current_level = [request.user]
                    for lvl in range(1, max(lvls or [0]) + 1):
                        next_level = []
                        for u in current_level:
                            ds = list(u.referrals.all())
                            next_level.extend(ds)
                            if lvl in lvls:
                                downline_ids.extend([d.id for d in ds])
                        current_level = next_level
                        if not current_level:
                            break
                    agg2 = Deposit.objects.filter(user_id__in=downline_ids, status='COMPLETED').aggregate(total=Sum('amount'))
                    dec_total = agg2.get('total') or 0
                    for mid in ids:
                        deposit_totals_map[mid] = dec_total
            except Exception:
                for mid in ids:
                    deposit_totals_map[mid] = 0
        dep_total = None
        try:
            agg = Deposit.objects.filter(user_id=request.user.id, status='COMPLETED').aggregate(total=Sum('amount'))
            dep_total = agg.get('total') or 0
        except Exception:
            dep_total = 0
        ser = MissionSerializer(
            missions,
            many=True,
            context={
                'request': request,
                'state_map': state_map,
                'progress_map': progress_map,
                'deposit_self_total': dep_total,
                'deposit_totals_map': deposit_totals_map,
            }
        )
        return Response({'count': len(ser.data), 'results': ser.data})


class ClaimMissionView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = 'missions_claim'

    @extend_schema(
        tags=["User API"],
        description="Claim mission reward for the authenticated user",
        request=ClaimMissionSerializer,
        responses={
            200: OpenApiResponse(response=ClaimMissionResponseSerializer),
            400: OpenApiResponse(description='Requirements not met or already claimed'),
            404: OpenApiResponse(description='Mission not found or inactive'),
        },
    )
    @transaction.atomic
    def post(self, request):
        serializer = ClaimMissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        mission_id = serializer.validated_data['mission_id']
        times = serializer.validated_data.get('times', 1)

        mission = Mission.objects.filter(id=mission_id, is_active=True).first()
        if not mission:
            return Response({'error': 'Mission not found or inactive'}, status=status.HTTP_404_NOT_FOUND)

        user = request.user
        progress = compute_mission_progress(mission, user)
        state, _ = MissionUserState.objects.get_or_create(user=user, mission=mission)
        claimed = state.claimed_count
        available = (progress // mission.requirement) - claimed

        if available <= 0:
            return Response({'error': 'Requirements not met or already claimed'}, status=status.HTTP_400_BAD_REQUEST)

        if not mission.is_repeatable:
            # Only allow 1 claim for non-repeatable missions
            times = 1
            if claimed >= 1:
                return Response({'error': 'Mission already claimed'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Clamp times to available
            times = min(times, available)

        reward_total = Decimal(str(mission.reward)) * times
        balance_field = 'balance' if mission.reward_balance_type == 'balance' else 'balance_deposit'

        with transaction.atomic():
            # Credit user
            current_balance = getattr(user, balance_field)
            setattr(user, balance_field, current_balance + reward_total)
            user.save()

            # Create transaction record
            trx = Transaction.objects.create(
                user=user,
                type='MISSIONS',
                amount=reward_total,
                description=f'Mission reward: {mission.description} (x{times})',
                status='COMPLETED',
                wallet_type=balance_field.upper(),
                trx_id=f'MSN-{timezone.now().strftime("%Y%m%d%H%M%S")}-{user.id}-{mission.id}'
            )

            # Update state
            state.claimed_count = claimed + times
            state.last_claimed_at = timezone.now()
            state.save()

        # Setelah update claimed_count dan transaksi reward, evaluasi rank user
        try:
            # Ambil kebijakan rank
            settings_obj = GeneralSetting.objects.order_by('-updated_at').first()
            levels_upto = settings_obj.rank_count_levels_upto if settings_obj else 1
            use_missions = True if not settings_obj else bool(settings_obj.rank_use_missions)
            use_downlines_total = False if not settings_obj else bool(settings_obj.rank_use_downlines_total)
            use_downlines_active = False if not settings_obj else bool(settings_obj.rank_use_downlines_active)

            # Hitung kandidat progres per basis yang dipilih, lalu ambil maksimum (OR)
            progress_candidates = []
            if use_missions:
                progress_candidates.append(
                    MissionUserState.objects
                    .filter(user=user, claimed_count__gte=1)
                    .values('mission_id')
                    .distinct()
                    .count()
                )
                if use_downlines_total or use_downlines_active:
                    current_level_users = [user]
                    total_downlines = 0
                    active_downlines = 0
                    for lvl in range(1, max(1, int(levels_upto)) + 1):
                        next_level = []
                        for u in current_level_users:
                            ds = list(u.referrals.all())
                            next_level.extend(ds)
                            total_downlines += len(ds)
                            for d in ds:
                                if Investment.objects.filter(
                                    user=d,
                                    status='ACTIVE',
                                    product__qualify_as_active_investment=True,
                                ).exists():
                                    active_downlines += 1
                        current_level_users = next_level
                if use_downlines_total:
                    progress_candidates.append(total_downlines)
                if use_downlines_active:
                    progress_candidates.append(active_downlines)

            progress_count = max(progress_candidates) if progress_candidates else 0

            # Cari rank tertinggi yang memenuhi syarat threshold
            target = RankLevel.objects.filter(missions_required_total__lte=progress_count).order_by('-rank').first()
            if target and (user.rank is None or target.rank > user.rank):
                user.rank = target.rank
                user.save(update_fields=['rank'])
        except Exception:
            # Jangan gagalkan klaim misi hanya karena gagal evaluasi rank
            pass
        return Response({
            'message': 'Mission claimed successfully',
            'mission_id': mission.id,
            'times_claimed': times,
            'reward_amount': str(reward_total),
            'wallet_type': balance_field,
            'transaction_id': trx.trx_id,
            'new_balance': str(getattr(user, balance_field)),
        }, status=status.HTTP_200_OK)
