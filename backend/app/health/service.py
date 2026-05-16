"""Health check services for the AI Marketing Platform.

Provides individual and aggregated health checks for all platform
components including database, Redis, external services, disk, and memory.

Usage:
    from app.health.service import HealthAggregator

    aggregator = HealthAggregator()
    result = await aggregator.check_all()
    # Returns dict with overall status and individual component results
"""

import asyncio
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional

import aiohttp
from sqlalchemy import text

from app.database import engine
from app.redis_client import get_redis_client


class HealthStatus(str, Enum):
    """Health status enumeration."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a single health check.

    Attributes:
        component: Name of the component checked.
        status: Health status of the component.
        response_time_ms: Time taken to perform the check in milliseconds.
        message: Human-readable status message.
        details: Additional check-specific details.
        checked_at: ISO timestamp of when the check was performed.
    """

    component: str
    status: HealthStatus
    response_time_ms: float
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DatabaseHealthCheck:
    """Check MySQL database connectivity, query latency, and pool status.

    Performs a lightweight ``SELECT 1`` query to verify connectivity
    and measures response time. Also reports connection pool statistics.
    """

    COMPONENT = "database"
    TIMEOUT_MS = 5000
    SLOW_QUERY_MS = 200

    async def check(self) -> HealthCheckResult:
        """Execute database health check.

        Returns:
            HealthCheckResult with status, latency, and pool info.
        """
        start = time.perf_counter()
        try:
            async with engine.connect() as conn:
                result = await conn.execute(text("SELECT 1"))
                row = result.scalar()

            elapsed_ms = (time.perf_counter() - start) * 1000

            # Gather pool statistics
            pool = engine.pool
            pool_stats = {
                "size": pool.size() if hasattr(pool, "size") else -1,
                "checked_in": pool.checkedin() if hasattr(pool, "checkedin") else -1,
                "checked_out": pool.checkedout() if hasattr(pool, "checkedout") else -1,
                "overflow": pool.overflow() if hasattr(pool, "overflow") else -1,
            }

            if row != 1:
                return HealthCheckResult(
                    component=self.COMPONENT,
                    status=HealthStatus.UNHEALTHY,
                    response_time_ms=round(elapsed_ms, 2),
                    message="Database returned unexpected result",
                    details={"expected": 1, "actual": row, **pool_stats},
                )

            status = (
                HealthStatus.HEALTHY
                if elapsed_ms < self.SLOW_QUERY_MS
                else HealthStatus.DEGRADED
            )

            return HealthCheckResult(
                component=self.COMPONENT,
                status=status,
                response_time_ms=round(elapsed_ms, 2),
                message="Database connected" + ("" if status == HealthStatus.HEALTHY else " (slow)"),
                details=pool_stats,
            )

        except asyncio.TimeoutError:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return HealthCheckResult(
                component=self.COMPONENT,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=round(elapsed_ms, 2),
                message=f"Database connection timed out after {self.TIMEOUT_MS}ms",
                details={"timeout_ms": self.TIMEOUT_MS},
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return HealthCheckResult(
                component=self.COMPONENT,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=round(elapsed_ms, 2),
                message=f"Database connection failed: {type(exc).__name__}: {str(exc)}",
                details={"error_type": type(exc).__name__},
            )


class RedisHealthCheck:
    """Check Redis connectivity, latency, and memory usage.

    Sends a PING command and retrieves memory info via INFO command.
    """

    COMPONENT = "redis"
    TIMEOUT_MS = 3000
    SLOW_RESPONSE_MS = 100

    async def check(self) -> HealthCheckResult:
        """Execute Redis health check.

        Returns:
            HealthCheckResult with status, latency, and memory info.
        """
        start = time.perf_counter()
        try:
            redis = await get_redis_client()
            pong = await redis.ping()
            elapsed_ms = (time.perf_counter() - start) * 1000

            if not pong:
                return HealthCheckResult(
                    component=self.COMPONENT,
                    status=HealthStatus.UNHEALTHY,
                    response_time_ms=round(elapsed_ms, 2),
                    message="Redis ping returned unexpected result",
                )

            # Get memory info
            info: Dict[str, Any] = {}
            try:
                raw_info = await redis.info("memory")
                if isinstance(raw_info, dict):
                    info = {
                        "used_memory_human": raw_info.get("used_memory_human", "unknown"),
                        "used_memory_peak_human": raw_info.get("used_memory_peak_human", "unknown"),
                        "maxmemory_human": raw_info.get("maxmemory_human", "0"),
                        "mem_fragmentation_ratio": raw_info.get("mem_fragmentation_ratio", 0),
                    }
            except Exception:
                info = {"memory_info_error": "Could not retrieve memory info"}

            status = (
                HealthStatus.HEALTHY
                if elapsed_ms < self.SLOW_RESPONSE_MS
                else HealthStatus.DEGRADED
            )

            return HealthCheckResult(
                component=self.COMPONENT,
                status=status,
                response_time_ms=round(elapsed_ms, 2),
                message="Redis connected" + ("" if status == HealthStatus.HEALTHY else " (slow)"),
                details=info,
            )

        except asyncio.TimeoutError:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return HealthCheckResult(
                component=self.COMPONENT,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=round(elapsed_ms, 2),
                message=f"Redis connection timed out after {self.TIMEOUT_MS}ms",
                details={"timeout_ms": self.TIMEOUT_MS},
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return HealthCheckResult(
                component=self.COMPONENT,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=round(elapsed_ms, 2),
                message=f"Redis connection failed: {type(exc).__name__}: {str(exc)}",
                details={"error_type": type(exc).__name__},
            )


class ExternalServiceHealthCheck:
    """Check external API availability with configurable timeouts.

    Supports OpenAI, Meta Graph API, Google Ads API, and other
    external services configured via environment variables.
    """

    COMPONENT = "external"
    DEFAULT_TIMEOUT = 10  # seconds

    # Service endpoints for lightweight health checks
    SERVICES: Dict[str, Dict[str, str]] = {
        "openai": {
            "url": "https://api.openai.com/v1/models",
            "method": "GET",
            "timeout": "10",
        },
        "meta_graph": {
            "url": "https://graph.facebook.com/v18.0/me",
            "method": "GET",
            "timeout": "10",
        },
        "google_ads": {
            "url": "https://googleads.googleapis.com/v14/customers:listAccessibleCustomers",
            "method": "GET",
            "timeout": "10",
        },
    }

    async def _check_one(
        self, name: str, config: Dict[str, str], session: aiohttp.ClientSession
    ) -> Dict[str, Any]:
        """Check a single external service.

        Args:
            name: Service identifier.
            config: Dictionary with url, method, timeout keys.
            session: aiohttp ClientSession to use.

        Returns:
            Dict with status, latency, and response info.
        """
        start = time.perf_counter()
        timeout = int(config.get("timeout", self.DEFAULT_TIMEOUT))
        try:
            method = config.get("method", "GET").upper()
            async with session.request(
                method=method,
                url=config["url"],
                timeout=aiohttp.ClientTimeout(total=timeout),
                headers={"User-Agent": "AIMP-HealthCheck/2.0"},
            ) as resp:
                _ = await resp.text()
                elapsed_ms = (time.perf_counter() - start) * 1000
                status_code = resp.status
                is_healthy = status_code < 500  # 4xx is OK for health checks (service is up)
                return {
                    "name": name,
                    "status": HealthStatus.HEALTHY if is_healthy else HealthStatus.DEGRADED,
                    "response_time_ms": round(elapsed_ms, 2),
                    "status_code": status_code,
                    "url": config["url"],
                    "message": f"HTTP {status_code}" if is_healthy else f"HTTP error {status_code}",
                }
        except asyncio.TimeoutError:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return {
                "name": name,
                "status": HealthStatus.UNHEALTHY,
                "response_time_ms": round(elapsed_ms, 2),
                "status_code": None,
                "url": config["url"],
                "message": f"Request timed out after {timeout}s",
            }
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return {
                "name": name,
                "status": HealthStatus.UNHEALTHY,
                "response_time_ms": round(elapsed_ms, 2),
                "status_code": None,
                "url": config["url"],
                "message": f"{type(exc).__name__}: {str(exc)}",
            }

    async def check(self) -> HealthCheckResult:
        """Check all configured external services.

        Returns:
            HealthCheckResult with aggregated status and per-service details.
        """
        start = time.perf_counter()
        connector = aiohttp.TCPConnector(limit=10, limit_per_host=5, ssl=False)
        timeout = aiohttp.ClientTimeout(total=30)

        try:
            async with aiohttp.ClientSession(
                connector=connector, timeout=timeout
            ) as session:
                tasks = [
                    self._check_one(name, config, session)
                    for name, config in self.SERVICES.items()
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            await connector.close()

        elapsed_ms = (time.perf_counter() - start) * 1000

        # Handle exceptions in results
        service_results: List[Dict[str, Any]] = []
        for r in results:
            if isinstance(r, Exception):
                service_results.append({
                    "name": "unknown",
                    "status": HealthStatus.UNHEALTHY,
                    "message": f"Check failed: {type(r).__name__}: {str(r)}",
                })
            else:
                service_results.append(r)

        # Aggregate status
        statuses = [r["status"] for r in service_results if isinstance(r, dict)]
        if HealthStatus.UNHEALTHY in statuses:
            overall = HealthStatus.DEGRADED  # external failures are degraded, not unhealthy
        elif HealthStatus.DEGRADED in statuses:
            overall = HealthStatus.DEGRADED
        else:
            overall = HealthStatus.HEALTHY

        return HealthCheckResult(
            component=self.COMPONENT,
            status=overall,
            response_time_ms=round(elapsed_ms, 2),
            message=f"External services: {overall.value} ({sum(1 for s in statuses if s == HealthStatus.HEALTHY)}/{len(statuses)} healthy)",
            details={"services": service_results},
        )


class DiskHealthCheck:
    """Check local disk usage.

    Uses ``shutil.disk_usage`` to check available space.
    Configurable thresholds for warnings and critical alerts.
    """

    COMPONENT = "disk"
    WARNING_PERCENT = 80
    CRITICAL_PERCENT = 95

    async def check(self) -> HealthCheckResult:
        """Check disk usage on the root filesystem.

        Returns:
            HealthCheckResult with usage percentage and available bytes.
        """
        start = time.perf_counter()
        try:
            total, used, free = self._get_disk_usage("/")
            used_percent = (used / total) * 100 if total > 0 else 0
            elapsed_ms = (time.perf_counter() - start) * 1000

            if used_percent >= self.CRITICAL_PERCENT:
                status = HealthStatus.UNHEALTHY
            elif used_percent >= self.WARNING_PERCENT:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.HEALTHY

            return HealthCheckResult(
                component=self.COMPONENT,
                status=status,
                response_time_ms=round(elapsed_ms, 2),
                message=f"Disk usage: {used_percent:.1f}%",
                details={
                    "total_bytes": total,
                    "used_bytes": used,
                    "free_bytes": free,
                    "used_percent": round(used_percent, 2),
                    "warning_percent": self.WARNING_PERCENT,
                    "critical_percent": self.CRITICAL_PERCENT,
                },
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return HealthCheckResult(
                component=self.COMPONENT,
                status=HealthStatus.UNKNOWN,
                response_time_ms=round(elapsed_ms, 2),
                message=f"Disk check failed: {type(exc).__name__}: {str(exc)}",
            )

    @staticmethod
    def _get_disk_usage(path: str):
        """Get disk usage for a path.

        Uses shutil.disk_usage if available, otherwise falls back to
        parsing df output.
        """
        try:
            import shutil
            return shutil.disk_usage(path)
        except Exception:
            # Fallback: try parsing statvfs
            import os as _os
            st = _os.statvfs(path)
            total = st.f_blocks * st.f_frsize
            free = st.f_bavail * st.f_frsize
            used = total - free
            return total, used, free


class MemoryHealthCheck:
    """Check system memory usage.

    Uses ``/proc/meminfo`` on Linux, falls back to psutil if available.
    """

    COMPONENT = "memory"
    WARNING_PERCENT = 85
    CRITICAL_PERCENT = 95

    async def check(self) -> HealthCheckResult:
        """Check system memory usage.

        Returns:
            HealthCheckResult with usage percentage and memory stats.
        """
        start = time.perf_counter()
        try:
            mem_info = self._get_memory_info()
            elapsed_ms = (time.perf_counter() - start) * 1000

            total = mem_info.get("total", 0)
            available = mem_info.get("available", 0)
            used = total - available if total > 0 else 0
            used_percent = (used / total) * 100 if total > 0 else 0

            if used_percent >= self.CRITICAL_PERCENT:
                status = HealthStatus.UNHEALTHY
            elif used_percent >= self.WARNING_PERCENT:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.HEALTHY

            return HealthCheckResult(
                component=self.COMPONENT,
                status=status,
                response_time_ms=round(elapsed_ms, 2),
                message=f"Memory usage: {used_percent:.1f}%",
                details={
                    "total_bytes": total,
                    "available_bytes": available,
                    "used_bytes": used,
                    "used_percent": round(used_percent, 2),
                    "warning_percent": self.WARNING_PERCENT,
                    "critical_percent": self.CRITICAL_PERCENT,
                },
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return HealthCheckResult(
                component=self.COMPONENT,
                status=HealthStatus.UNKNOWN,
                response_time_ms=round(elapsed_ms, 2),
                message=f"Memory check failed: {type(exc).__name__}: {str(exc)}",
            )

    def _get_memory_info(self) -> Dict[str, int]:
        """Get memory information from the system.

        Tries /proc/meminfo first (Linux), then psutil, then sysconf.
        """
        # Try /proc/meminfo (Linux)
        try:
            with open("/proc/meminfo", "r") as f:
                lines = f.readlines()
            mem_info: Dict[str, int] = {}
            for line in lines:
                parts = line.split(":")
                if len(parts) == 2:
                    key = parts[0].strip()
                    value_str = parts[1].strip().split()[0]  # Get number, drop 'kB'
                    mem_info[key.lower()] = int(value_str) * 1024  # Convert kB to bytes
            return {
                "total": mem_info.get("memtotal", 0),
                "available": mem_info.get("memavailable", mem_info.get("memfree", 0)),
            }
        except (FileNotFoundError, PermissionError, ValueError):
            pass

        # Try psutil
        try:
            import psutil  # type: ignore[import-untyped]
            vm = psutil.virtual_memory()
            return {
                "total": vm.total,
                "available": vm.available,
            }
        except Exception:
            pass

        # Fallback: return zeros
        return {"total": 0, "available": 0}


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------

class HealthAggregator:
    """Aggregate health checks from all components.

    Runs all configured health checks concurrently and computes an
    overall status.  The overall status is the worst individual status
    in the order: healthy < degraded < unhealthy < unknown.

    Usage:
        aggregator = HealthAggregator()
        result = await aggregator.check_all()
        print(result["overall_status"])  # "healthy" | "degraded" | "unhealthy"
    """

    # Ordered from best to worst
    STATUS_PRIORITY = [HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.UNHEALTHY, HealthStatus.UNKNOWN]

    def __init__(self) -> None:
        self.checks: List[Callable[[], Coroutine[Any, Any, HealthCheckResult]]] = [
            DatabaseHealthCheck().check,
            RedisHealthCheck().check,
            ExternalServiceHealthCheck().check,
            DiskHealthCheck().check,
            MemoryHealthCheck().check,
        ]

    def _result_to_dict(self, result: HealthCheckResult) -> Dict[str, Any]:
        """Convert HealthCheckResult to a plain dict for JSON serialization."""
        return {
            "component": result.component,
            "status": result.status.value,
            "response_time_ms": result.response_time_ms,
            "message": result.message,
            "details": result.details,
            "checked_at": result.checked_at,
        }

    def _worst_status(self, statuses: List[HealthStatus]) -> HealthStatus:
        """Determine the worst status from a list using priority ordering."""
        worst = HealthStatus.HEALTHY
        for s in statuses:
            if self.STATUS_PRIORITY.index(s) > self.STATUS_PRIORITY.index(worst):
                worst = s
        return worst

    async def check_all(self) -> Dict[str, Any]:
        """Run all health checks concurrently.

        Returns:
            Dict with keys:
                - overall_status: "healthy" | "degraded" | "unhealthy"
                - version: API version string
                - checks: list of individual check results
                - total_response_time_ms: total time for all checks
                - checked_at: ISO timestamp
        """
        start = time.perf_counter()

        results = await asyncio.gather(
            *[check() for check in self.checks], return_exceptions=True
        )

        total_time_ms = (time.perf_counter() - start) * 1000

        # Normalize results
        normalized: List[HealthCheckResult] = []
        for r in results:
            if isinstance(r, Exception):
                normalized.append(
                    HealthCheckResult(
                        component="unknown",
                        status=HealthStatus.UNKNOWN,
                        response_time_ms=0.0,
                        message=f"Check crashed: {type(r).__name__}: {str(r)}",
                    )
                )
            else:
                normalized.append(r)

        statuses = [r.status for r in normalized]
        overall = self._worst_status(statuses)

        return {
            "overall_status": overall.value,
            "version": "2.0.0",
            "service": "AI Marketing Platform API",
            "checks": [self._result_to_dict(r) for r in normalized],
            "total_response_time_ms": round(total_time_ms, 2),
            "checks_count": {
                "healthy": sum(1 for s in statuses if s == HealthStatus.HEALTHY),
                "degraded": sum(1 for s in statuses if s == HealthStatus.DEGRADED),
                "unhealthy": sum(1 for s in statuses if s == HealthStatus.UNHEALTHY),
                "unknown": sum(1 for s in statuses if s == HealthStatus.UNKNOWN),
            },
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    async def check_database(self) -> Dict[str, Any]:
        """Check database health only.

        Returns:
            Dict with database check result.
        """
        result = await DatabaseHealthCheck().check()
        return self._result_to_dict(result)

    async def check_redis(self) -> Dict[str, Any]:
        """Check Redis health only.

        Returns:
            Dict with Redis check result.
        """
        result = await RedisHealthCheck().check()
        return self._result_to_dict(result)

    async def check_readiness(self) -> Dict[str, Any]:
        """Readiness probe: check DB and Redis only (core dependencies).

        Returns:
            Dict with overall status. HTTP 200 if healthy, 503 otherwise.
        """
        results = await asyncio.gather(
            DatabaseHealthCheck().check(),
            RedisHealthCheck().check(),
            return_exceptions=True,
        )

        normalized: List[HealthCheckResult] = []
        for r in results:
            if isinstance(r, Exception):
                normalized.append(
                    HealthCheckResult(
                        component="unknown",
                        status=HealthStatus.UNHEALTHY,
                        response_time_ms=0.0,
                        message=f"Check crashed: {type(r).__name__}: {str(r)}",
                    )
                )
            else:
                normalized.append(r)

        statuses = [r.status for r in normalized]
        overall = self._worst_status(statuses)

        return {
            "status": overall.value,
            "checks": [self._result_to_dict(r) for r in normalized],
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    async def check_liveness(self) -> Dict[str, Any]:
        """Liveness probe: lightweight check that the process is running.

        Returns:
            Dict with status "healthy" and process info.
        """
        return {
            "status": HealthStatus.HEALTHY.value,
            "pid": os.getpid(),
            "uptime_seconds": self._get_uptime(),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _get_uptime() -> float:
        """Get process uptime in seconds.

        Reads /proc/self/stat on Linux, returns 0 on other platforms.
        """
        try:
            with open("/proc/self/stat", "r") as f:
                fields = f.read().split()
            # starttime is field 22 (index 21), measured in clock ticks
            starttime_ticks = int(fields[21])
            with open("/proc/uptime", "r") as f:
                uptime_seconds = float(f.read().split()[0])
            with open("/proc/self/stat", "r") as f:
                pass
            # Calculate uptime from process start time
            import resource
            return resource.getrusage(resource.RUSAGE_SELF).ru_utime
        except Exception:
            return 0.0
