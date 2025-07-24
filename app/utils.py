from __future__ import annotations

from datetime import datetime

from app.database import User as DBUser
from app.models.user import (
    Country,
    Cover,
    DailyChallengeStats,
    GradeCounts,
    Kudosu,
    Level,
    Page,
    RankHighest,
    RankHistory,
    Statistics,
    Team,
    User,
    UserAchievement,
)

from sqlalchemy.orm import Session


def convert_db_user_to_api_user(
    db_user: DBUser, ruleset: str = "osu", db_session: Session | None = None
) -> User:
    """将数据库用户模型转换为API用户模型（使用 Lazer 表）"""

    # 从db_user获取基本字段值
    user_id = getattr(db_user, "id")
    user_name = getattr(db_user, "name")
    user_country = getattr(db_user, "country")
    user_country_code = user_country  # 在User模型中，country字段就是country_code

    # 获取 Lazer 用户资料
    profile = db_user.lazer_profile
    if not profile:
        # 如果没有 lazer 资料，使用默认值
        profile = create_default_profile(db_user)

    # 获取 Lazer 用户计数

    lzrcnt = db_user.lazer_statistics
    if not lzrcnt:
        # 如果没有 lazer 计数，使用默认值
        lzrcnt = create_default_counts()

    # 获取指定模式的统计信息
    user_stats = None
    for stat in db_user.lazer_statistics:
        if stat.mode == ruleset:
            user_stats = stat
            break

    if not user_stats:
        # 如果没有找到指定模式的统计，创建默认统计
        user_stats = create_default_lazer_statistics(ruleset)

    # 获取国家信息
    country_code = db_user.country_code if db_user.country_code is not None else "XX"

    country = Country(code=str(country_code), name=get_country_name(str(country_code)))

    # 获取 Kudosu 信息
    kudosu = Kudosu(available=0, total=0)

    # 获取计数信息
    counts = create_default_counts()

    # 转换统计信息
    statistics = Statistics(
        count_100=user_stats.count_100,
        count_300=user_stats.count_300,
        count_50=user_stats.count_50,
        count_miss=user_stats.count_miss,
        level=Level(
            current=user_stats.level_current, progress=user_stats.level_progress
        ),
        global_rank=user_stats.global_rank,
        global_rank_exp=user_stats.global_rank_exp,
        pp=float(user_stats.pp) if user_stats.pp else 0.0,
        pp_exp=float(user_stats.pp_exp) if user_stats.pp_exp else 0.0,
        ranked_score=user_stats.ranked_score,
        hit_accuracy=float(user_stats.hit_accuracy) if user_stats.hit_accuracy else 0.0,
        play_count=user_stats.play_count,
        play_time=user_stats.play_time,
        total_score=user_stats.total_score,
        total_hits=user_stats.total_hits,
        maximum_combo=user_stats.maximum_combo,
        replays_watched_by_others=user_stats.replays_watched_by_others,
        is_ranked=user_stats.is_ranked,
        grade_counts=GradeCounts(
            ss=user_stats.grade_ss,
            ssh=user_stats.grade_ssh,
            s=user_stats.grade_s,
            sh=user_stats.grade_sh,
            a=user_stats.grade_a,
        ),
        country_rank=user_stats.country_rank,
        rank={"country": user_stats.country_rank} if user_stats.country_rank else None,
    )

    # 转换所有模式的统计信息
    statistics_rulesets = {}
    for stat in db_user.statistics:
        statistics_rulesets[stat.mode] = Statistics(
            count_100=stat.count_100,
            count_300=stat.count_300,
            count_50=stat.count_50,
            count_miss=stat.count_miss,
            level=Level(current=stat.level_current, progress=stat.level_progress),
            global_rank=stat.global_rank,
            global_rank_exp=stat.global_rank_exp,
            pp=stat.pp,
            pp_exp=stat.pp_exp,
            ranked_score=stat.ranked_score,
            hit_accuracy=stat.hit_accuracy,
            play_count=stat.play_count,
            play_time=stat.play_time,
            total_score=stat.total_score,
            total_hits=stat.total_hits,
            maximum_combo=stat.maximum_combo,
            replays_watched_by_others=stat.replays_watched_by_others,
            is_ranked=stat.is_ranked,
            grade_counts=GradeCounts(
                ss=stat.grade_ss,
                ssh=stat.grade_ssh,
                s=stat.grade_s,
                sh=stat.grade_sh,
                a=stat.grade_a,
            ),
        )

    # 转换国家信息
    country = Country(code=user_country_code, name=get_country_name(user_country_code))

    # 转换封面信息
    cover_url = (
        profile.cover_url
        if profile and profile.cover_url
        else "https://assets.ppy.sh/user-profile-covers/default.jpeg"
    )
    cover = Cover(
        custom_url=profile.cover_url if profile else None, url=str(cover_url), id=None
    )

    # 转换 Kudosu 信息
    kudosu = Kudosu(available=0, total=0)

    # 转换成就信息
    user_achievements = []
    if db_user.lazer_achievements:
        for achievement in db_user.lazer_achievements:
            user_achievements.append(
                UserAchievement(
                    achieved_at=achievement.achieved_at,
                    achievement_id=achievement.achievement_id,
                )
            )

    # 转换排名历史
    rank_history = None
    rank_history_data = None
    for rh in db_user.rank_history:
        if rh.mode == ruleset:
            rank_history_data = rh.rank_data
            break

    if rank_history_data:
        rank_history = RankHistory(mode=ruleset, data=rank_history_data)

    # 转换每日挑战统计
    daily_challenge_stats = None
    if db_user.daily_challenge_stats:
        dcs = db_user.daily_challenge_stats
        daily_challenge_stats = DailyChallengeStats(
            daily_streak_best=dcs.daily_streak_best,
            daily_streak_current=dcs.daily_streak_current,
            last_update=dcs.last_update,
            last_weekly_streak=dcs.last_weekly_streak,
            playcount=dcs.playcount,
            top_10p_placements=dcs.top_10p_placements,
            top_50p_placements=dcs.top_50p_placements,
            user_id=dcs.user_id,
            weekly_streak_best=dcs.weekly_streak_best,
            weekly_streak_current=dcs.weekly_streak_current,
        )

    # 转换最高排名
    rank_highest = None
    if user_stats.rank_highest:
        rank_highest = RankHighest(
            rank=user_stats.rank_highest,
            updated_at=user_stats.rank_highest_updated_at or datetime.utcnow(),
        )

    # 转换团队信息
    team = None
    if db_user.team_membership:
        team_member = db_user.team_membership[0]  # 假设用户只属于一个团队
        team = Team(
            flag_url=team_member.team.flag_url or "",
            id=team_member.team.id,
            name=team_member.team.name,
            short_name=team_member.team.short_name,
        )

    # 创建用户对象
    # 从db_user获取基本字段值
    user_id = getattr(db_user, "id")
    user_name = getattr(db_user, "name")
    user_country = getattr(db_user, "country")

    # 获取用户头像URL
    avatar_url = None

    # 首先检查 profile 中的 avatar_url
    if profile and hasattr(profile, "avatar_url") and profile.avatar_url:
        avatar_url = str(profile.avatar_url)

    # 然后检查是否有关联的头像记录
    if avatar_url is None and hasattr(db_user, "avatar") and db_user.avatar is not None:
        if db_user.avatar.r2_game_url:
            # 优先使用游戏用的头像URL
            avatar_url = str(db_user.avatar.r2_game_url)
        elif db_user.avatar.r2_original_url:
            # 其次使用原始头像URL
            avatar_url = str(db_user.avatar.r2_original_url)

    # 如果还是没有找到，通过查询获取
    if db_session and avatar_url is None:
        try:
            # 导入UserAvatar模型
            from app.database import UserAvatar

            # 尝试查找用户的头像记录
            avatar_record = (
                db_session.query(UserAvatar)
                .filter_by(user_id=user_id, is_active=True)
                .first()
            )
            if avatar_record is not None:
                if avatar_record.r2_game_url is not None:
                    # 优先使用游戏用的头像URL
                    avatar_url = str(avatar_record.r2_game_url)
                elif avatar_record.r2_original_url is not None:
                    # 其次使用原始头像URL
                    avatar_url = str(avatar_record.r2_original_url)
        except Exception as e:
            print(f"获取用户头像时出错: {e}")
    print(f"最终头像URL: {avatar_url}")
    # 如果仍然没有找到头像URL，则使用默认URL
    if avatar_url is None:
        avatar_url = "https://a.gu-osu.gmoe.cc/api/users/avatar/1"

    # 处理 profile_order 列表排序
    profile_order = [
        "me",
        "recent_activity",
        "top_ranks",
        "medals",
        "historical",
        "beatmaps",
        "kudosu",
    ]
    if profile and profile.profile_order:
        profile_order = profile.profile_order

    # 在convert_db_user_to_api_user函数中添加active_tournament_banners处理
    active_tournament_banners = []
    if (
        hasattr(db_user, "lazer_tournament_banners")
        and db_user.lazer_tournament_banners
    ):
        for banner in db_user.lazer_tournament_banners:
            active_tournament_banners.append(
                {
                    "tournament_id": banner.tournament_id,
                    "image_url": banner.image_url,
                    "is_active": banner.is_active,
                }
            )

    # 在convert_db_user_to_api_user函数中添加badges处理
    badges = []
    if hasattr(db_user, "lazer_badges") and db_user.lazer_badges:
        for badge in db_user.lazer_badges:
            badges.append(
                {
                    "badge_id": badge.badge_id,
                    "awarded_at": badge.awarded_at,
                    "description": badge.description,
                    "image_url": badge.image_url,
                    "url": badge.url,
                }
            )

    # 在convert_db_user_to_api_user函数中添加monthly_playcounts处理
    monthly_playcounts = []
    if (
        hasattr(db_user, "lazer_monthly_playcounts")
        and db_user.lazer_monthly_playcounts
    ):
        for playcount in db_user.lazer_monthly_playcounts:
            monthly_playcounts.append(
                {
                    "start_date": playcount.start_date.isoformat()
                    if playcount.start_date
                    else None,
                    "play_count": playcount.play_count,
                }
            )

    # 在convert_db_user_to_api_user函数中添加previous_usernames处理
    previous_usernames = []
    if (
        hasattr(db_user, "lazer_previous_usernames")
        and db_user.lazer_previous_usernames
    ):
        for username in db_user.lazer_previous_usernames:
            previous_usernames.append(
                {
                    "username": username.username,
                    "changed_at": username.changed_at.isoformat()
                    if username.changed_at
                    else None,
                }
            )

    # 在convert_db_user_to_api_user函数中添加replays_watched_counts处理
    replays_watched_counts = []
    if hasattr(db_user, "lazer_replays_watched") and db_user.lazer_replays_watched:
        for replay in db_user.lazer_replays_watched:
            replays_watched_counts.append(
                {
                    "start_date": replay.start_date.isoformat()
                    if replay.start_date
                    else None,
                    "count": replay.count,
                }
            )

    # 创建用户对象
    user = User(
        id=user_id,
        username=user_name,
        avatar_url=avatar_url,
        country_code=str(country_code),
        default_group=profile.default_group if profile else "default",
        is_active=profile.is_active if profile else True,
        is_bot=profile.is_bot if profile else False,
        is_deleted=profile.is_deleted if profile else False,
        is_online=profile.is_online if profile else True,
        is_supporter=profile.is_supporter if profile else False,
        is_restricted=profile.is_restricted if profile else False,
        last_visit=db_user.last_visit if db_user.last_visit else None,
        pm_friends_only=profile.pm_friends_only if profile else False,
        profile_colour=profile.profile_colour if profile else None,
        cover_url=profile.cover_url
        if profile and profile.cover_url
        else "https://assets.ppy.sh/user-profile-covers/default.jpeg",
        discord=profile.discord if profile else None,
        has_supported=profile.has_supported if profile else False,
        interests=profile.interests if profile else None,
        join_date=profile.join_date,
        location=profile.location if profile else None,
        max_blocks=profile.max_blocks if profile and profile.max_blocks else 100,
        max_friends=profile.max_friends if profile and profile.max_friends else 500,
        post_count=profile.post_count if profile and profile.post_count else 0,
        profile_hue=profile.profile_hue if profile and profile.profile_hue else None,
        profile_order=profile_order,  # 使用排序后的 profile_order
        title=profile.title if profile else None,
        title_url=profile.title_url if profile else None,
        twitter=profile.twitter if profile else None,
        website=profile.website if profile else None,
        session_verified=True,
        support_level=profile.support_level if profile else 0,
        country=country,
        cover=cover,
        kudosu=kudosu,
        statistics=statistics,
        statistics_rulesets=statistics_rulesets,
        beatmap_playcounts_count=lzrcnt.beatmap_playcounts_count if lzrcnt else 0,
        comments_count=lzrcnt.comments_count if lzrcnt else 0,
        favourite_beatmapset_count=lzrcnt.favourite_beatmapset_count if lzrcnt else 0,
        follower_count=lzrcnt.follower_count if lzrcnt else 0,
        graveyard_beatmapset_count=lzrcnt.graveyard_beatmapset_count if lzrcnt else 0,
        guest_beatmapset_count=lzrcnt.guest_beatmapset_count if lzrcnt else 0,
        loved_beatmapset_count=lzrcnt.loved_beatmapset_count if lzrcnt else 0,
        mapping_follower_count=lzrcnt.mapping_follower_count if lzrcnt else 0,
        nominated_beatmapset_count=lzrcnt.nominated_beatmapset_count if lzrcnt else 0,
        pending_beatmapset_count=lzrcnt.pending_beatmapset_count if lzrcnt else 0,
        ranked_beatmapset_count=lzrcnt.ranked_beatmapset_count if lzrcnt else 0,
        ranked_and_approved_beatmapset_count=lzrcnt.ranked_and_approved_beatmapset_count
        if lzrcnt
        else 0,
        unranked_beatmapset_count=lzrcnt.unranked_beatmapset_count if lzrcnt else 0,
        scores_best_count=lzrcnt.scores_best_count if lzrcnt else 0,
        scores_first_count=lzrcnt.scores_first_count if lzrcnt else 0,
        scores_pinned_count=lzrcnt.scores_pinned_count,
        scores_recent_count=lzrcnt.scores_recent_count if lzrcnt else 0,
        account_history=[],  # TODO: 获取用户历史账户信息
        # active_tournament_banner=len(active_tournament_banners),
        active_tournament_banners=active_tournament_banners,
        badges=badges,
        current_season_stats=None,
        daily_challenge_user_stats=None,
        groups=[],
        monthly_playcounts=monthly_playcounts,
        page=Page(html=profile.page_html, raw=profile.page_raw)
        if profile.page_html or profile.page_raw
        else Page(),
        previous_usernames=previous_usernames,
        rank_highest=rank_highest,
        rank_history=rank_history,
        rankHistory=rank_history,
        replays_watched_counts=replays_watched_counts,
        team=team,
        user_achievements=user_achievements,
    )

    return user


def get_country_name(country_code: str) -> str:
    """根据国家代码获取国家名称"""
    country_names = {
        "CN": "China",
        "JP": "Japan",
        "US": "United States",
        "GB": "United Kingdom",
        "DE": "Germany",
        "FR": "France",
        "KR": "South Korea",
        "CA": "Canada",
        "AU": "Australia",
        "BR": "Brazil",
        # 可以添加更多国家
    }
    return country_names.get(country_code, "Unknown")


def create_default_profile(db_user: DBUser):
    """创建默认的用户资料"""

    # 完善 MockProfile 类定义
    class MockProfile:
        def __init__(self):
            self.is_active = True
            self.is_bot = False
            self.is_deleted = False
            self.is_online = True
            self.is_supporter = False
            self.is_restricted = False
            self.session_verified = False
            self.has_supported = False
            self.pm_friends_only = False
            self.default_group = "default"
            self.last_visit = None
            self.join_date = db_user.join_date if db_user else datetime.utcnow()
            self.profile_colour = None
            self.profile_hue = None
            self.avatar_url = None
            self.cover_url = None
            self.discord = None
            self.twitter = None
            self.website = None
            self.title = None
            self.title_url = None
            self.interests = None
            self.location = None
            self.occupation = None
            self.playmode = "osu"
            self.support_level = 0
            self.max_blocks = 100
            self.max_friends = 500
            self.post_count = 0
            # 添加profile_order字段
            self.profile_order = [
                "me",
                "recent_activity",
                "top_ranks",
                "medals",
                "historical",
                "beatmaps",
                "kudosu",
            ]
            self.page_html = ""
            self.page_raw = ""
            # 在MockProfile类中添加active_tournament_banners字段
            self.active_tournament_banners = (
                MockLazerTournamentBanner.create_default_banners()
            )
            self.active_tournament_banners = []  # 默认空列表

    return MockProfile()


def create_default_lazer_statistics(mode: str):
    """创建默认的 Lazer 统计信息"""

    class MockLazerStatistics:
        def __init__(self, mode: str):
            self.mode = mode
            self.count_100 = 0
            self.count_300 = 0
            self.count_50 = 0
            self.count_miss = 0
            self.level_current = 1
            self.level_progress = 0
            self.global_rank = None
            self.global_rank_exp = None
            self.pp = 0.0
            self.pp_exp = 0.0
            self.ranked_score = 0
            self.hit_accuracy = 0.0
            self.total_score = 0
            self.total_hits = 0
            self.maximum_combo = 0
            self.play_count = 0
            self.play_time = 0
            self.replays_watched_by_others = 0
            self.is_ranked = False
            self.grade_ss = 0
            self.grade_ssh = 0
            self.grade_s = 0
            self.grade_sh = 0
            self.grade_a = 0
            self.country_rank = None
            self.rank_highest = None
            self.rank_highest_updated_at = None

    return MockLazerStatistics(mode)


def create_default_country(country_code: str):
    """创建默认的国家信息"""

    class MockCountry:
        def __init__(self, code: str):
            self.code = code
            self.name = get_country_name(code)

    return MockCountry(country_code)


def create_default_kudosu():
    """创建默认的 Kudosu 信息"""

    class MockKudosu:
        def __init__(self):
            self.available = 0
            self.total = 0

    return MockKudosu()


def create_default_counts():
    """创建默认的计数信息"""

    class MockCounts:
        def __init__(self):
            self.recent_scores_count = None
            self.beatmap_playcounts_count = 0
            self.scores_first_count = 0
            self.scores_pinned_count = 0
            self.comments_count = 0
            self.favourite_beatmapset_count = 0
            self.follower_count = 0
            self.graveyard_beatmapset_count = 0
            self.guest_beatmapset_count = 0
            self.loved_beatmapset_count = 0
            self.mapping_follower_count = 0
            self.nominated_beatmapset_count = 0
            self.pending_beatmapset_count = 0
            self.ranked_beatmapset_count = 0
            self.ranked_and_approved_beatmapset_count = 0
            self.unranked_beatmapset_count = 0
            self.scores_best_count = 0
            self.scores_first_count = 0
            self.scores_pinned_count = 0
            self.scores_recent_count = 0

    return MockCounts()


class MockLazerTournamentBanner:
    def __init__(self, tournament_id: int, image_url: str, is_active: bool = True):
        self.tournament_id = tournament_id
        self.image_url = image_url
        self.is_active = is_active

    @staticmethod
    def create_default_banners():
        """创建默认的锦标赛横幅配置"""
        return [
            MockLazerTournamentBanner(1, "https://example.com/banner1.jpg", True),
            MockLazerTournamentBanner(2, "https://example.com/banner2.jpg", False),
        ]


