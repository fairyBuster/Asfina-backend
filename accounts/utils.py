from accounts.models import GeneralSetting
from missions.models import MissionUserState
from products.models import Investment

def calculate_user_rank_progress(user):
    """
    Menghitung progress rank user berdasarkan GeneralSetting.
    Mengembalikan integer jumlah progress (misi selesai, downline total, atau downline aktif).
    """
    if not user or not user.is_authenticated:
        return 0

    try:
        settings_obj = GeneralSetting.objects.order_by('-updated_at').first()
        levels_upto = settings_obj.rank_count_levels_upto if settings_obj else 1
        
        # Default policy logic
        use_missions = True if not settings_obj else bool(settings_obj.rank_use_missions)
        use_downlines_total = False if not settings_obj else bool(settings_obj.rank_use_downlines_total)
        use_downlines_active = False if not settings_obj else bool(settings_obj.rank_use_downlines_active)

        progress_candidates = []
        
        # 1. Based on Missions
        if use_missions:
            progress_candidates.append(
                MissionUserState.objects
                .filter(user=user, claimed_count__gte=1)
                .values('mission_id')
                .distinct()
                .count()
            )
            
        # 2. Based on Downlines (Total or Active)
        if use_downlines_total or use_downlines_active:
            current_level_users = [user]
            total_downlines = 0
            active_downlines = 0
            
            # BFS / Level traversal
            for lvl in range(1, max(1, int(levels_upto)) + 1):
                next_level = []
                for u in current_level_users:
                    ds = list(u.referrals.all())
                    next_level.extend(ds)
                    
                    total_downlines += len(ds)
                    for d in ds:
                        if Investment.objects.filter(user=d, status='ACTIVE').exists():
                            active_downlines += 1
                            
                current_level_users = next_level
                if not current_level_users:
                    break

            if use_downlines_total:
                progress_candidates.append(total_downlines)
            if use_downlines_active:
                progress_candidates.append(active_downlines)

        return max(progress_candidates) if progress_candidates else 0
        
    except Exception:
        return 0
