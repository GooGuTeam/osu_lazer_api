"""
重构的区间统计系统 - 真正统计半小时区间内的用户活跃情况
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import json

from app.dependencies.database import get_redis, get_redis_message
from app.log import logger
from app.router.private.stats import (
    REDIS_ONLINE_HISTORY_KEY,
    _get_online_users_count,
    _get_playing_users_count,
    _redis_exec,
)
from app.utils import utcnow

# Redis keys for interval statistics
INTERVAL_STATS_BASE_KEY = "server:interval_stats"
INTERVAL_ONLINE_USERS_KEY = "server:interval_online_users"  # 区间内在线用户集合
INTERVAL_PLAYING_USERS_KEY = "server:interval_playing_users"  # 区间内游玩用户集合
CURRENT_INTERVAL_INFO_KEY = "server:current_interval_info"  # 当前区间信息


@dataclass
class IntervalInfo:
    """区间信息"""

    start_time: datetime
    end_time: datetime
    interval_key: str

    def is_current(self) -> bool:
        """检查是否是当前区间"""
        now = utcnow()
        return self.start_time <= now < self.end_time

    def to_dict(self) -> dict:
        return {
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "interval_key": self.interval_key,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "IntervalInfo":
        return cls(
            start_time=datetime.fromisoformat(data["start_time"]),
            end_time=datetime.fromisoformat(data["end_time"]),
            interval_key=data["interval_key"],
        )


@dataclass
class IntervalStats:
    """区间统计数据"""

    interval_key: str
    start_time: datetime
    end_time: datetime
    unique_online_users: int  # 区间内独特在线用户数
    unique_playing_users: int  # 区间内独特游玩用户数
    peak_online_count: int  # 区间内在线用户数峰值
    peak_playing_count: int  # 区间内游玩用户数峰值
    total_samples: int  # 采样次数
    created_at: datetime

    def to_dict(self) -> dict:
        return {
            "interval_key": self.interval_key,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "unique_online_users": self.unique_online_users,
            "unique_playing_users": self.unique_playing_users,
            "peak_online_count": self.peak_online_count,
            "peak_playing_count": self.peak_playing_count,
            "total_samples": self.total_samples,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "IntervalStats":
        return cls(
            interval_key=data["interval_key"],
            start_time=datetime.fromisoformat(data["start_time"]),
            end_time=datetime.fromisoformat(data["end_time"]),
            unique_online_users=data["unique_online_users"],
            unique_playing_users=data["unique_playing_users"],
            peak_online_count=data["peak_online_count"],
            peak_playing_count=data["peak_playing_count"],
            total_samples=data["total_samples"],
            created_at=datetime.fromisoformat(data["created_at"]),
        )


class EnhancedIntervalStatsManager:
    """增强的区间统计管理器 - 真正统计半小时区间内的用户活跃情况"""

    @staticmethod
    def get_current_interval_boundaries() -> tuple[datetime, datetime]:
        """获取当前30分钟区间的边界"""
        now = utcnow()
        # 计算区间开始时间（向下取整到最近的30分钟）
        minute = (now.minute // 30) * 30
        start_time = now.replace(minute=minute, second=0, microsecond=0)
        # 区间结束时间
        end_time = start_time + timedelta(minutes=30)
        return start_time, end_time

    @staticmethod
    def generate_interval_key(start_time: datetime) -> str:
        """生成区间唯一标识"""
        return f"{INTERVAL_STATS_BASE_KEY}:{start_time.strftime('%Y%m%d_%H%M')}"

    @staticmethod
    async def get_current_interval_info() -> IntervalInfo:
        """获取当前区间信息"""
        start_time, end_time = EnhancedIntervalStatsManager.get_current_interval_boundaries()
        interval_key = EnhancedIntervalStatsManager.generate_interval_key(start_time)

        return IntervalInfo(start_time=start_time, end_time=end_time, interval_key=interval_key)

    @staticmethod
    async def initialize_current_interval() -> None:
        """初始化当前区间"""
        redis_sync = get_redis_message()
        redis_async = get_redis()

        try:
            current_interval = await EnhancedIntervalStatsManager.get_current_interval_info()

            # 存储当前区间信息
            await _redis_exec(
                redis_sync.set,
                CURRENT_INTERVAL_INFO_KEY,
                json.dumps(current_interval.to_dict()),
            )
            await redis_async.expire(CURRENT_INTERVAL_INFO_KEY, 35 * 60)  # 35分钟过期

            # 初始化区间用户集合（如果不存在）
            online_key = f"{INTERVAL_ONLINE_USERS_KEY}:{current_interval.interval_key}"
            playing_key = f"{INTERVAL_PLAYING_USERS_KEY}:{current_interval.interval_key}"

            # 设置过期时间为35分钟
            await redis_async.expire(online_key, 35 * 60)
            await redis_async.expire(playing_key, 35 * 60)

            # 初始化区间统计记录
            stats = IntervalStats(
                interval_key=current_interval.interval_key,
                start_time=current_interval.start_time,
                end_time=current_interval.end_time,
                unique_online_users=0,
                unique_playing_users=0,
                peak_online_count=0,
                peak_playing_count=0,
                total_samples=0,
                created_at=utcnow(),
            )

            await _redis_exec(
                redis_sync.set,
                current_interval.interval_key,
                json.dumps(stats.to_dict()),
            )
            await redis_async.expire(current_interval.interval_key, 35 * 60)

            # 如果历史记录为空，自动填充前24小时数据为0
            await EnhancedIntervalStatsManager._ensure_24h_history_exists()

            logger.info(
                f"Initialized interval stats for {current_interval.start_time.strftime('%H:%M')}"
                f" - {current_interval.end_time.strftime('%H:%M')}"
            )

        except Exception as e:
            logger.error(f"Error initializing current interval: {e}")

    @staticmethod
    async def _ensure_24h_history_exists() -> None:
        """确保24小时历史数据存在，不存在则用0填充"""
        redis_sync = get_redis_message()
        redis_async = get_redis()

        try:
            # 检查现有历史数据数量
            history_length = await _redis_exec(redis_sync.llen, REDIS_ONLINE_HISTORY_KEY)

            if history_length < 48:  # 少于48个数据点（24小时*2）
                logger.info(f"History has only {history_length} points, filling with zeros for 24h")

                # 计算需要填充的数据点数量
                needed_points = 48 - history_length

                # 从当前时间往前推，创建缺失的时间点（都填充为0）
                current_time = utcnow()  # noqa: F841
                current_interval_start, _ = EnhancedIntervalStatsManager.get_current_interval_boundaries()

                # 从当前区间开始往前推，创建历史数据点（确保时间对齐到30分钟边界）
                fill_points = []
                for i in range(needed_points):
                    # 每次往前推30分钟，确保时间对齐
                    point_time = current_interval_start - timedelta(minutes=30 * (i + 1))

                    # 确保时间对齐到30分钟边界
                    aligned_minute = (point_time.minute // 30) * 30
                    point_time = point_time.replace(minute=aligned_minute, second=0, microsecond=0)

                    history_point = {
                        "timestamp": point_time.isoformat(),
                        "online_count": 0,
                        "playing_count": 0,
                    }
                    fill_points.append(json.dumps(history_point))

                # 将填充数据添加到历史记录末尾（最旧的数据）
                if fill_points:
                    # 先将现有数据转移到临时位置
                    temp_key = f"{REDIS_ONLINE_HISTORY_KEY}_temp"
                    if history_length > 0:
                        # 复制现有数据到临时key
                        existing_data = await _redis_exec(redis_sync.lrange, REDIS_ONLINE_HISTORY_KEY, 0, -1)
                        if existing_data:
                            for data in existing_data:
                                await _redis_exec(redis_sync.rpush, temp_key, data)

                    # 清空原有key
                    await redis_async.delete(REDIS_ONLINE_HISTORY_KEY)

                    # 先添加填充数据（最旧的）
                    for point in reversed(fill_points):  # 反向添加，最旧的在最后
                        await _redis_exec(redis_sync.rpush, REDIS_ONLINE_HISTORY_KEY, point)

                    # 再添加原有数据（较新的）
                    if history_length > 0:
                        existing_data = await _redis_exec(redis_sync.lrange, temp_key, 0, -1)
                        for data in existing_data:
                            await _redis_exec(redis_sync.lpush, REDIS_ONLINE_HISTORY_KEY, data)

                    # 清理临时key
                    await redis_async.delete(temp_key)

                    # 确保只保留48个数据点
                    await _redis_exec(redis_sync.ltrim, REDIS_ONLINE_HISTORY_KEY, 0, 47)

                    # 设置过期时间
                    await redis_async.expire(REDIS_ONLINE_HISTORY_KEY, 26 * 3600)

                    logger.info(f"Filled {len(fill_points)} historical data points with zeros")

        except Exception as e:
            logger.error(f"Error ensuring 24h history exists: {e}")

    @staticmethod
    async def add_user_to_interval(user_id: int, is_playing: bool = False) -> None:
        """添加用户到当前区间统计 - 实时更新当前运行的区间"""
        redis_sync = get_redis_message()
        redis_async = get_redis()

        try:
            current_interval = await EnhancedIntervalStatsManager.get_current_interval_info()

            # 添加到区间在线用户集合
            online_key = f"{INTERVAL_ONLINE_USERS_KEY}:{current_interval.interval_key}"
            await _redis_exec(redis_sync.sadd, online_key, str(user_id))
            await redis_async.expire(online_key, 35 * 60)

            # 如果用户在游玩，也添加到游玩用户集合
            if is_playing:
                playing_key = f"{INTERVAL_PLAYING_USERS_KEY}:{current_interval.interval_key}"
                await _redis_exec(redis_sync.sadd, playing_key, str(user_id))
                await redis_async.expire(playing_key, 35 * 60)

            # 立即更新区间统计（同步更新，确保数据实时性）
            await EnhancedIntervalStatsManager._update_interval_stats()

            logger.debug(
                f"Added user {user_id} to current interval {current_interval.start_time.strftime('%H:%M')}"
                f"-{current_interval.end_time.strftime('%H:%M')}"
            )

        except Exception as e:
            logger.error(f"Error adding user {user_id} to interval: {e}")

    @staticmethod
    async def _update_interval_stats() -> None:
        """更新当前区间统计 - 立即同步更新"""
        redis_sync = get_redis_message()
        redis_async = get_redis()

        try:
            current_interval = await EnhancedIntervalStatsManager.get_current_interval_info()

            # 获取区间内独特用户数
            online_key = f"{INTERVAL_ONLINE_USERS_KEY}:{current_interval.interval_key}"
            playing_key = f"{INTERVAL_PLAYING_USERS_KEY}:{current_interval.interval_key}"

            unique_online = await _redis_exec(redis_sync.scard, online_key)
            unique_playing = await _redis_exec(redis_sync.scard, playing_key)

            # 获取当前实时用户数作为峰值参考
            current_online = await _get_online_users_count(redis_async)
            current_playing = await _get_playing_users_count(redis_async)

            # 获取现有统计数据
            existing_data = await _redis_exec(redis_sync.get, current_interval.interval_key)
            if existing_data:
                stats = IntervalStats.from_dict(json.loads(existing_data))
                # 更新峰值
                stats.peak_online_count = max(stats.peak_online_count, current_online)
                stats.peak_playing_count = max(stats.peak_playing_count, current_playing)
                stats.total_samples += 1
            else:
                # 创建新的统计记录
                stats = IntervalStats(
                    interval_key=current_interval.interval_key,
                    start_time=current_interval.start_time,
                    end_time=current_interval.end_time,
                    unique_online_users=0,
                    unique_playing_users=0,
                    peak_online_count=current_online,
                    peak_playing_count=current_playing,
                    total_samples=1,
                    created_at=utcnow(),
                )

            # 更新独特用户数
            stats.unique_online_users = unique_online
            stats.unique_playing_users = unique_playing

            # 立即保存更新的统计数据
            await _redis_exec(
                redis_sync.set,
                current_interval.interval_key,
                json.dumps(stats.to_dict()),
            )
            await redis_async.expire(current_interval.interval_key, 35 * 60)

            logger.debug(
                f"Updated interval stats: online={unique_online}, playing={unique_playing}, "
                f"peak_online={stats.peak_online_count}, peak_playing={stats.peak_playing_count}"
            )

        except Exception as e:
            logger.error(f"Error updating interval stats: {e}")

    @staticmethod
    async def finalize_interval() -> IntervalStats | None:
        """完成上一个已结束的区间统计并保存到历史"""
        redis_sync = get_redis_message()
        redis_async = get_redis()

        try:
            # 获取上一个已完成区间（当前区间的前一个）
            current_start, current_end = EnhancedIntervalStatsManager.get_current_interval_boundaries()
            # 上一个区间开始时间是当前区间开始时间减去30分钟
            previous_start = current_start - timedelta(minutes=30)
            previous_end = current_start  # 上一个区间的结束时间就是当前区间的开始时间

            interval_key = EnhancedIntervalStatsManager.generate_interval_key(previous_start)

            previous_interval = IntervalInfo(
                start_time=previous_start,
                end_time=previous_end,
                interval_key=interval_key,
            )

            # 获取最终统计数据
            stats_data = await _redis_exec(redis_sync.get, previous_interval.interval_key)
            if not stats_data:
                logger.warning(
                    f"No interval stats found to finalize for {previous_interval.start_time.strftime('%H:%M')}"
                )
                return None

            stats = IntervalStats.from_dict(json.loads(stats_data))

            # 创建历史记录点（使用区间开始时间作为时间戳）
            history_point = {
                "timestamp": previous_interval.start_time.isoformat(),
                "online_count": stats.unique_online_users,
                "playing_count": stats.unique_playing_users,
            }

            # 添加到历史记录
            await _redis_exec(redis_sync.lpush, REDIS_ONLINE_HISTORY_KEY, json.dumps(history_point))
            await _redis_exec(redis_sync.ltrim, REDIS_ONLINE_HISTORY_KEY, 0, 47)
            await redis_async.expire(REDIS_ONLINE_HISTORY_KEY, 26 * 3600)

            logger.info(
                f"Finalized interval stats: "
                f"unique_online={stats.unique_online_users}, "
                f"unique_playing={stats.unique_playing_users}, "
                f"peak_online={stats.peak_online_count}, "
                f"peak_playing={stats.peak_playing_count}, "
                f"samples={stats.total_samples} "
                f"for {stats.start_time.strftime('%H:%M')}-{stats.end_time.strftime('%H:%M')}"
            )

            return stats

        except Exception as e:
            logger.error(f"Error finalizing interval stats: {e}")
            return None

    @staticmethod
    async def get_current_interval_stats() -> IntervalStats | None:
        """获取当前区间统计"""
        redis_sync = get_redis_message()

        try:
            current_interval = await EnhancedIntervalStatsManager.get_current_interval_info()
            stats_data = await _redis_exec(redis_sync.get, current_interval.interval_key)

            if stats_data:
                return IntervalStats.from_dict(json.loads(stats_data))
            return None

        except Exception as e:
            logger.error(f"Error getting current interval stats: {e}")
            return None

    @staticmethod
    async def cleanup_old_intervals() -> None:
        """清理过期的区间数据"""
        redis_async = get_redis()

        try:
            # 删除过期的区间统计数据（超过2小时的）
            cutoff_time = utcnow() - timedelta(hours=2)
            pattern = f"{INTERVAL_STATS_BASE_KEY}:*"

            keys = await redis_async.keys(pattern)
            for key in keys:
                try:
                    # 从key中提取时间，处理字节或字符串类型
                    if isinstance(key, bytes):
                        key_str = key.decode()
                    else:
                        key_str = key
                    time_part = key_str.split(":")[-1]  # YYYYMMDD_HHMM格式
                    # 将时区无关的datetime转换为UTC时区感知的datetime进行比较
                    key_time = datetime.strptime(time_part, "%Y%m%d_%H%M").replace(tzinfo=UTC)

                    if key_time < cutoff_time:
                        await redis_async.delete(key)
                        # 也删除对应的用户集合
                        # 使用key_str确保正确拼接用户集合键
                        await redis_async.delete(f"{INTERVAL_ONLINE_USERS_KEY}:{key_str}")
                        await redis_async.delete(f"{INTERVAL_PLAYING_USERS_KEY}:{key}")

                except (ValueError, IndexError):
                    # 忽略解析错误的key
                    continue

            logger.debug("Cleaned up old interval data")

        except Exception as e:
            logger.error(f"Error cleaning up old intervals: {e}")


# 便捷函数，用于替换现有的统计更新函数
async def update_user_activity_in_interval(user_id: int, is_playing: bool = False) -> None:
    """用户活动时更新区间统计（在登录、开始游玩等时调用）"""
    await EnhancedIntervalStatsManager.add_user_to_interval(user_id, is_playing)
