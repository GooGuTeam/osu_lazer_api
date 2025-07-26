from __future__ import annotations

from datetime import UTC, datetime

from app.database import (
    LazerUserCounts,
    LazerUserProfile,
    LazerUserStatistics,
    User as DBUser,
)
from app.models.user import (
    Country,
    Cover,
    DailyChallengeStats,
    GradeCounts,
    GameMode,
    Kudosu,
    Level,
    Page,
    Rank,
    RankHighest,
    RankHistory,
    Statistics,
    User,
    UserAchievement,
)


def format_datetime_with_timezone(dt: datetime | None) -> str | None:
    """将datetime对象格式化为带+00:00时区的ISO字符串"""
    if dt is None:
        return None

    # 如果datetime没有时区信息，假设它是UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)

    # 转换为UTC并格式化为ISO字符串，确保以+00:00结尾
    return dt.astimezone(UTC).isoformat().replace('+00:00', '+00:00')


async def convert_db_user_to_api_user(db_user: DBUser, ruleset: str = "osu") -> User:
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
        profile = LazerUserProfile(
            user_id=user_id,
        )

    # 获取 Lazer 用户计数 - 使用正确的 lazer_counts 关系
    lzrcnt = db_user.lazer_counts

    if not lzrcnt:
        # 如果没有 lazer 计数，使用默认值
        lzrcnt = LazerUserCounts(user_id=user_id)

    # 获取指定模式的统计信息
    user_stats = None
    if db_user.lazer_statistics:
        for stat in db_user.lazer_statistics:
            if stat.mode == ruleset:
                user_stats = stat
                break

    if not user_stats:
        # 如果没有找到指定模式的统计，创建默认统计
        user_stats = LazerUserStatistics(user_id=user_id)

    # 获取国家信息并验证
    raw_country_code = db_user.country_code if db_user.country_code is not None else "Unknown"

    # 确保country_code是有效的两字母代码
    if raw_country_code and len(str(raw_country_code)) == 2:
        country_code = str(raw_country_code).upper()
    else:
        country_code = "Unknown"

    country = Country(code=country_code, name=get_country_name(country_code))

    # 获取 Kudosu 信息
    kudosu = Kudosu(available=0, total=0)

    # 获取计数信息
    # counts = LazerUserCounts(user_id=user_id)

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
        rank=Rank(country=user_stats.country_rank),
    )

    # 转换所有模式的统计信息 - 如果为空则返回None而不是空字典
    statistics_rulesets = None
    if db_user.statistics and len(db_user.statistics) > 0:
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
                rank=Rank(country=stat.country_rank),
            )

    # 转换国家信息
    country = Country(code=user_country_code, name=get_country_name(user_country_code))

    # 转换封面信息
    cover_url = profile.cover_url if profile and profile.cover_url else None
    cover = Cover(
        custom_url=profile.cover_url if profile else None,
        url=cover_url,
        id=None
    )

    # 转换 Kudosu 信息
    kudosu = Kudosu(available=0, total=0)

    # 转换成就信息
    user_achievements = []
    if db_user.lazer_achievements:
        for achievement in db_user.lazer_achievements:
            user_achievements.append({
                "achieved_at": format_datetime_with_timezone(achievement.achieved_at),
                "achievement_id": achievement.achievement_id,
            })

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
    # daily_challenge_stats = None
    # if db_user.daily_challenge_stats:
    # dcs = db_user.daily_challenge_stats
    # daily_challenge_stats = DailyChallengeStats(
    #     daily_streak_best=dcs.daily_streak_best,
    #     daily_streak_current=dcs.daily_streak_current,
    #     last_update=dcs.last_update,
    #     last_weekly_streak=dcs.last_weekly_streak,
    #     playcount=dcs.playcount,
    #     top_10p_placements=dcs.top_10p_placements,
    #     top_50p_placements=dcs.top_50p_placements,
    #     user_id=dcs.user_id,
    #     weekly_streak_best=dcs.weekly_streak_best,
    #     weekly_streak_current=dcs.weekly_streak_current,
    # )

    # 转换最高排名
    rank_highest = None
    if user_stats.rank_highest:
        rank_highest = RankHighest(
            rank=user_stats.rank_highest,
            updated_at=user_stats.rank_highest_updated_at or datetime.now(UTC),
        )

    # 转换团队信息
    team = None
    if db_user.team_membership:
        team_member = db_user.team_membership[0]  # 假设用户只属于一个团队
        team = team_member.team

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
    # if db_session and avatar_url is None:
    #     try:
    #         # 导入UserAvatar模型

    #         # 尝试查找用户的头像记录
    #         statement = select(UserAvatar).where(
    #             UserAvatar.user_id == user_id, UserAvatar.is_active == True
    #         )
    #         avatar_record = db_session.exec(statement).first()
    #         if avatar_record is not None:
    #             if avatar_record.r2_game_url is not None:
    #                 # 优先使用游戏用的头像URL
    #                 avatar_url = str(avatar_record.r2_game_url)
    #             elif avatar_record.r2_original_url is not None:
    #                 # 其次使用原始头像URL
    #                 avatar_url = str(avatar_record.r2_original_url)
    #     except Exception as e:
    #         print(f"获取用户头像时出错: {e}")
    # print(f"最终头像URL: {avatar_url}")
    # 如果仍然没有找到头像URL，则使用默认URL
    if avatar_url is None:
        avatar_url = "https://dev.ppy.sh/images/layout/avatar-guest@2x.png"

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
        profile_order = profile.profile_order.split(",")

    # 在convert_db_user_to_api_user函数中添加active_tournament_banners处理
    active_tournament_banners = []
    if db_user.active_banners:
        for banner in db_user.active_banners:
            active_tournament_banners.append(
                {
                    "tournament_id": banner.tournament_id,
                    "image_url": banner.image_url,
                    "is_active": banner.is_active,
                }
            )

    # 在convert_db_user_to_api_user函数中添加badges处理
    badges = []
    if db_user.lazer_badges:
        for badge in db_user.lazer_badges:
            badges.append(
                {
                    "badge_id": badge.badge_id,
                    "awarded_at": format_datetime_with_timezone(badge.awarded_at),
                    "description": badge.description,
                    "image_url": badge.image_url,
                    "url": badge.url,
                }
            )

    # 在convert_db_user_to_api_user函数中添加monthly_playcounts处理
    monthly_playcounts = []
    if db_user.lazer_monthly_playcounts:
        for playcount in db_user.lazer_monthly_playcounts:
            monthly_playcounts.append({
                "start_date": format_datetime_with_timezone(playcount.start_date) if hasattr(playcount.start_date, 'replace') else playcount.start_date.isoformat() if playcount.start_date else None,
                "count": playcount.play_count,
            })

    # 在convert_db_user_to_api_user函数中添加previous_usernames处理
    previous_usernames = []
    if db_user.lazer_previous_usernames:
        for username in db_user.lazer_previous_usernames:
            previous_usernames.append(username.username)

    # 在convert_db_user_to_api_user函数中添加replays_watched_counts处理
    replays_watched_counts = []
    if hasattr(db_user, "lazer_replays_watched") and db_user.lazer_replays_watched:
        for replay in db_user.lazer_replays_watched:
            replays_watched_counts.append(
                {
                    "start_date": format_datetime_with_timezone(replay.start_date) if hasattr(replay.start_date, 'replace') else replay.start_date.isoformat() if replay.start_date else None,
                    "count": replay.count,
                }
            )

    # 创建用户对象
    user = User(
        id=user_id,
        username=user_name,
        avatar_url=avatar_url,
        country_code=country_code,
        default_group=profile.default_group if profile else "default",
        is_active=profile.is_active,
        is_bot=profile.is_bot,
        is_deleted=profile.is_deleted,
        is_online=profile.is_online,
        is_supporter=profile.is_supporter,
        is_restricted=profile.is_restricted,
        last_visit=profile.last_visit if profile else None,
        pm_friends_only=profile.pm_friends_only,
        profile_colour=profile.profile_colour,
        cover_url=profile.cover_url if profile and profile.cover_url else None,
        discord=profile.discord if profile else None,
        has_supported=profile.has_supported if profile else False,
        interests=profile.interests if profile else None,
        join_date=profile.join_date if profile and profile.join_date else datetime.now(UTC),
        location=profile.location if profile else None,
        occupation=profile.occupation if profile else None,
        playmode="osu",  # 默认使用osu模式
        playstyle=None,  # 默认无游戏风格
        max_blocks=profile.max_blocks if profile and profile.max_blocks else 50,  # 修改默认值为50
        max_friends=profile.max_friends if profile and profile.max_friends else 250,  # 修改默认值为250
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
        statistics_rulesets=statistics_rulesets,  # 现在如果为空则返回None
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
        scores_pinned_count=lzrcnt.scores_pinned_count if lzrcnt and lzrcnt.scores_pinned_count else 0,
        scores_recent_count=lzrcnt.scores_recent_count if lzrcnt else 0,
        account_history=[],  # TODO: 获取用户历史账户信息
        # active_tournament_banner=len(active_tournament_banners),
        active_tournament_banners=active_tournament_banners,
        badges=badges,
        current_season_stats=None,
        daily_challenge_user_stats=DailyChallengeStats(
            daily_streak_best=0,
            daily_streak_current=0,
            last_update=datetime(2000, 1, 1, tzinfo=UTC),  # 添加UTC时区
            last_weekly_streak=datetime(2000, 1, 1, tzinfo=UTC),  # 添加UTC时区
            playcount=0,
            top_10p_placements=0,
            top_50p_placements=0,
            user_id=user_id,
            weekly_streak_best=0,
            weekly_streak_current=0,
        ),
        groups=[],
        monthly_playcounts=monthly_playcounts,
        page=Page(html=profile.page_html or "", raw=profile.page_raw or "")
        if profile and (profile.page_html or profile.page_raw)
        else Page(),
        previous_usernames=previous_usernames,
        rank_highest=rank_highest,
        rank_history=rank_history.data if rank_history else None,
        rankHistory=rank_history.data if rank_history else None,
        replays_watched_counts=replays_watched_counts,
        team=team,
        user_achievements=user_achievements,
    )

    return user


def get_country_name(country_code: str) -> str:
    """根据国家代码获取国家名称 - 基于osu客户端CountryCode枚举"""
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
        "RU": "Russian Federation",
        "TW": "Taiwan",
        "NL": "Netherlands",
        "IT": "Italy",
        "ES": "Spain",
        "PL": "Poland",
        "SE": "Sweden",
        "NO": "Norway",
        "FI": "Finland",
        "DK": "Denmark",
        "BE": "Belgium",
        "AT": "Austria",
        "CH": "Switzerland",
        "CZ": "Czech Republic",
        "HU": "Hungary",
        "PT": "Portugal",
        "GR": "Greece",
        "IE": "Ireland",
        "SK": "Slovakia",
        "LV": "Latvia",
        "LT": "Lithuania",
        "EE": "Estonia",
        "SI": "Slovenia",
        "HR": "Croatia",
        "BG": "Bulgaria",
        "RO": "Romania",
        "UA": "Ukraine",
        "BY": "Belarus",
        "MD": "Moldova",
        "RS": "Serbia",
        "ME": "Montenegro",
        "MK": "Macedonia",
        "BA": "Bosnia and Herzegovina",
        "AL": "Albania",
        "XK": "Kosovo",
        "MT": "Malta",
        "CY": "Cyprus",
        "LU": "Luxembourg",
        "IS": "Iceland",
        "LI": "Liechtenstein",
        "MC": "Monaco",
        "AD": "Andorra",
        "SM": "San Marino",
        "VA": "Vatican City",
        "MX": "Mexico",
        "AR": "Argentina",
        "CL": "Chile",
        "CO": "Colombia",
        "PE": "Peru",
        "VE": "Venezuela",
        "UY": "Uruguay",
        "PY": "Paraguay",
        "BO": "Bolivia",
        "EC": "Ecuador",
        "GY": "Guyana",
        "SR": "Suriname",
        "GF": "French Guiana",
        "IN": "India",
        "PK": "Pakistan",
        "BD": "Bangladesh",
        "LK": "Sri Lanka",
        "NP": "Nepal",
        "BT": "Bhutan",
        "MV": "Maldives",
        "TH": "Thailand",
        "VN": "Vietnam",
        "LA": "Laos",
        "KH": "Cambodia",
        "MM": "Myanmar",
        "MY": "Malaysia",
        "SG": "Singapore",
        "ID": "Indonesia",
        "PH": "Philippines",
        "BN": "Brunei",
        "TL": "East Timor",
        "MN": "Mongolia",
        "KZ": "Kazakhstan",
        "UZ": "Uzbekistan",
        "KG": "Kyrgyzstan",
        "TJ": "Tajikistan",
        "TM": "Turkmenistan",
        "AF": "Afghanistan",
        "IR": "Iran",
        "IQ": "Iraq",
        "SY": "Syria",
        "LB": "Lebanon",
        "JO": "Jordan",
        "IL": "Israel",
        "PS": "Palestine",
        "SA": "Saudi Arabia",
        "AE": "United Arab Emirates",
        "QA": "Qatar",
        "BH": "Bahrain",
        "KW": "Kuwait",
        "OM": "Oman",
        "YE": "Yemen",
        "TR": "Turkey",
        "GE": "Georgia",
        "AM": "Armenia",
        "AZ": "Azerbaijan",
        "EG": "Egypt",
        "LY": "Libya",
        "TN": "Tunisia",
        "DZ": "Algeria",
        "MA": "Morocco",
        "SD": "Sudan",
        "SS": "South Sudan",
        "ET": "Ethiopia",
        "ER": "Eritrea",
        "DJ": "Djibouti",
        "SO": "Somalia",
        "KE": "Kenya",
        "UG": "Uganda",
        "TZ": "Tanzania",
        "RW": "Rwanda",
        "BI": "Burundi",
        "ZA": "South Africa",
        "NA": "Namibia",
        "BW": "Botswana",
        "ZW": "Zimbabwe",
        "ZM": "Zambia",
        "MW": "Malawi",
        "MZ": "Mozambique",
        "SZ": "Swaziland",
        "LS": "Lesotho",
        "MG": "Madagascar",
        "MU": "Mauritius",
        "SC": "Seychelles",
        "KM": "Comoros",
        "YT": "Mayotte",
        "RE": "Reunion",
        "ZR": "Zaire",
        "AO": "Angola",
        "GW": "Guinea-Bissau",
        "GN": "Guinea",
        "SL": "Sierra Leone",
        "LR": "Liberia",
        "CI": "Ivory Coast",
        "GH": "Ghana",
        "TG": "Togo",
        "BJ": "Benin",
        "NE": "Niger",
        "BF": "Burkina Faso",
        "ML": "Mali",
        "SN": "Senegal",
        "GM": "Gambia",
        "GV": "Guinea-Bissau",
        "CV": "Cape Verde",
        "MR": "Mauritania",
        "EH": "Western Sahara",
        "ST": "Sao Tome and Principe",
        "GQ": "Equatorial Guinea",
        "GA": "Gabon",
        "CG": "Congo",
        "CD": "Democratic Republic of the Congo",
        "CF": "Central African Republic",
        "TD": "Chad",
        "CM": "Cameroon",
        "NG": "Nigeria",
        "Unknown": "Unknown",
        # 添加更多国家以匹配osu客户端枚举
    }

    # 验证country_code是否为有效的两字母代码
    if not country_code or len(country_code) != 2:
        return "Unknown"

    country_code = country_code.upper()
    return country_names.get(country_code, "Unknown")
