"""
Performance benchmarking CLI tool for the Test Results Management API.
"""

import asyncio
import json
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import aiohttp
import click
from rich.console import Console
from rich.progress import Progress
from rich.table import Table

console = Console()


@dataclass
class BenchmarkResult:
    """Benchmark test result."""

    name: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_time: float
    requests_per_second: float
    avg_response_time: float
    p50_response_time: float
    p95_response_time: float
    p99_response_time: float
    min_response_time: float
    max_response_time: float
    error_rate: float


class APIBenchmark:
    """API performance benchmarking tool."""

    def __init__(self, base_url: str, auth_token: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self.headers = {}
        if auth_token:
            self.headers["Authorization"] = f"Bearer {auth_token}"

    async def benchmark_endpoint(
        self,
        endpoint: str,
        method: str = "GET",
        requests: int = 1000,
        concurrent: int = 100,
        data: dict[str, Any] | None = None,
        timeout: int = 30,
    ) -> BenchmarkResult:
        """Benchmark a specific endpoint."""

        url = f"{self.base_url}{endpoint}"
        response_times = []
        errors = 0
        successful = 0

        start_time = time.time()

        # Use semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(concurrent)

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=timeout), headers=self.headers
        ) as session:

            async def make_request() -> None:
                async with semaphore:
                    nonlocal errors, successful
                    request_start = time.time()

                    try:
                        if method.upper() == "GET":
                            async with session.get(url) as response:
                                await response.text()  # Consume response
                                response_time = time.time() - request_start
                                response_times.append(response_time)
                                if response.status < 400:
                                    successful += 1
                                else:
                                    errors += 1

                        elif method.upper() == "POST":
                            async with session.post(url, json=data) as response:
                                await response.text()
                                response_time = time.time() - request_start
                                response_times.append(response_time)
                                if response.status < 400:
                                    successful += 1
                                else:
                                    errors += 1

                    except Exception:
                        errors += 1
                        response_time = time.time() - request_start
                        response_times.append(response_time)

            # Create tasks
            tasks = [make_request() for _ in range(requests)]

            # Execute with progress tracking
            with Progress() as progress:
                task_id = progress.add_task(f"Benchmarking {method} {endpoint}", total=requests)

                for completed, coro in enumerate(asyncio.as_completed(tasks), 1):
                    await coro
                    progress.update(task_id, completed=completed)

        total_time = time.time() - start_time

        # Calculate statistics
        if response_times:
            avg_response_time = statistics.mean(response_times)
            p50_response_time = statistics.median(response_times)
            p95_response_time = statistics.quantiles(response_times, n=20)[18]  # 95th percentile
            p99_response_time = statistics.quantiles(response_times, n=100)[98]  # 99th percentile
            min_response_time = min(response_times)
            max_response_time = max(response_times)
        else:
            avg_response_time = p50_response_time = p95_response_time = p99_response_time = 0
            min_response_time = max_response_time = 0

        return BenchmarkResult(
            name=f"{method} {endpoint}",
            total_requests=requests,
            successful_requests=successful,
            failed_requests=errors,
            total_time=total_time,
            requests_per_second=requests / total_time if total_time > 0 else 0,
            avg_response_time=avg_response_time * 1000,  # Convert to ms
            p50_response_time=p50_response_time * 1000,
            p95_response_time=p95_response_time * 1000,
            p99_response_time=p99_response_time * 1000,
            min_response_time=min_response_time * 1000,
            max_response_time=max_response_time * 1000,
            error_rate=(errors / requests) * 100 if requests > 0 else 0,
        )

    async def comprehensive_benchmark(
        self, requests_per_endpoint: int = 1000, concurrent_requests: int = 100
    ) -> list[BenchmarkResult]:
        """Run comprehensive API benchmark."""

        endpoints_to_test = [
            ("GET", "/health"),
            ("GET", "/v1/frameworks"),
            ("GET", "/v1/environments"),
            ("GET", "/v1/suites"),
            ("GET", "/v1/results"),
        ]

        results = []

        console.print("[bold blue]Starting comprehensive API benchmark...[/bold blue]")

        for method, endpoint in endpoints_to_test:
            console.print(f"\n[yellow]Testing {method} {endpoint}[/yellow]")

            result = await self.benchmark_endpoint(
                endpoint=endpoint,
                method=method,
                requests=requests_per_endpoint,
                concurrent=concurrent_requests,
            )

            results.append(result)

            # Show immediate results
            self._display_result(result)

        return results

    def _display_result(self, result: BenchmarkResult) -> None:
        """Display benchmark result in a formatted table."""

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="dim")
        table.add_column("Value", justify="right")

        table.add_row("Endpoint", result.name)
        table.add_row("Total Requests", str(result.total_requests))
        table.add_row("Successful", str(result.successful_requests))
        table.add_row("Failed", str(result.failed_requests))
        table.add_row("Error Rate", f"{result.error_rate:.2f}%")
        table.add_row("Total Time", f"{result.total_time:.2f}s")
        table.add_row("Requests/sec", f"{result.requests_per_second:.2f}")
        table.add_row("Avg Response", f"{result.avg_response_time:.2f}ms")
        table.add_row("P50 Response", f"{result.p50_response_time:.2f}ms")
        table.add_row("P95 Response", f"{result.p95_response_time:.2f}ms")
        table.add_row("P99 Response", f"{result.p99_response_time:.2f}ms")
        table.add_row("Min Response", f"{result.min_response_time:.2f}ms")
        table.add_row("Max Response", f"{result.max_response_time:.2f}ms")

        console.print(table)

    def display_summary(self, results: list[BenchmarkResult]) -> None:
        """Display benchmark summary."""

        console.print("\n[bold green]Benchmark Summary[/bold green]")

        summary_table = Table(show_header=True, header_style="bold magenta")
        summary_table.add_column("Endpoint", style="cyan")
        summary_table.add_column("RPS", justify="right")
        summary_table.add_column("P95 (ms)", justify="right")
        summary_table.add_column("Error %", justify="right")
        summary_table.add_column("Status", justify="center")

        for result in results:
            # Determine status based on performance targets
            status = "✅"
            if result.requests_per_second < 100:  # Below minimum threshold
                status = "❌"
            elif result.p95_response_time > 200 or result.error_rate > 1:  # Above 200ms target
                status = "⚠️"

            summary_table.add_row(
                result.name,
                f"{result.requests_per_second:.1f}",
                f"{result.p95_response_time:.1f}",
                f"{result.error_rate:.1f}%",
                status,
            )

        console.print(summary_table)

        # Overall assessment
        total_rps = sum(r.requests_per_second for r in results)
        avg_p95 = statistics.mean([r.p95_response_time for r in results])
        max_error_rate = max([r.error_rate for r in results])

        console.print("\n[bold]Overall Performance:[/bold]")
        console.print(f"Total RPS: {total_rps:.1f}")
        console.print(f"Average P95: {avg_p95:.1f}ms")
        console.print(f"Max Error Rate: {max_error_rate:.1f}%")

        # Performance targets assessment
        if total_rps >= 1000 and avg_p95 <= 200 and max_error_rate <= 1:
            console.print("[bold green]✅ All performance targets met![/bold green]")
        else:
            console.print("[bold red]❌ Performance targets not met[/bold red]")
            if total_rps < 1000:
                console.print(f"  • RPS below target: {total_rps:.1f} < 1000")
            if avg_p95 > 200:
                console.print(f"  • P95 above target: {avg_p95:.1f}ms > 200ms")
            if max_error_rate > 1:
                console.print(f"  • Error rate above target: {max_error_rate:.1f}% > 1%")

    def export_results(self, results: list[BenchmarkResult], filename: str) -> None:
        """Export results to JSON file."""

        export_data = {
            "timestamp": datetime.now().isoformat(),
            "results": [
                {
                    "name": r.name,
                    "total_requests": r.total_requests,
                    "successful_requests": r.successful_requests,
                    "failed_requests": r.failed_requests,
                    "total_time": r.total_time,
                    "requests_per_second": r.requests_per_second,
                    "avg_response_time_ms": r.avg_response_time,
                    "p50_response_time_ms": r.p50_response_time,
                    "p95_response_time_ms": r.p95_response_time,
                    "p99_response_time_ms": r.p99_response_time,
                    "min_response_time_ms": r.min_response_time,
                    "max_response_time_ms": r.max_response_time,
                    "error_rate_percent": r.error_rate,
                }
                for r in results
            ],
        }

        with open(filename, "w") as f:
            json.dump(export_data, f, indent=2)

        console.print(f"[green]Results exported to {filename}[/green]")


@click.group()
def benchmark() -> None:
    """Performance benchmarking tools."""
    pass


@benchmark.command()
@click.option("--url", default="http://localhost:8000", help="API base URL")
@click.option("--token", help="Authorization token")
@click.option("--requests", default=1000, help="Number of requests per endpoint")
@click.option("--concurrent", default=100, help="Concurrent requests")
@click.option("--export", help="Export results to JSON file")
def api(url: str, token: str, requests: int, concurrent: int, export: str) -> None:
    """Benchmark API endpoints."""

    async def run_benchmark() -> None:
        benchmark_tool = APIBenchmark(url, token)

        results = await benchmark_tool.comprehensive_benchmark(
            requests_per_endpoint=requests, concurrent_requests=concurrent
        )

        benchmark_tool.display_summary(results)

        if export:
            benchmark_tool.export_results(results, export)

    try:
        asyncio.run(run_benchmark())
    except KeyboardInterrupt:
        console.print("[yellow]Benchmark interrupted by user[/yellow]")
        sys.exit(1)


@benchmark.command()
@click.option("--url", default="http://localhost:8000", help="API base URL")
@click.option("--token", help="Authorization token")
@click.option("--endpoint", default="/health", help="Endpoint to test")
@click.option("--method", default="GET", help="HTTP method")
@click.option("--requests", default=1000, help="Number of requests")
@click.option("--concurrent", default=100, help="Concurrent requests")
@click.option("--data", help="JSON data for POST requests")
def single(
    url: str, token: str, endpoint: str, method: str, requests: int, concurrent: int, data: str
) -> None:
    """Benchmark a single endpoint."""

    async def run_single_benchmark() -> None:
        benchmark_tool = APIBenchmark(url, token)

        request_data = None
        if data:
            try:
                request_data = json.loads(data)
            except json.JSONDecodeError:
                console.print("[red]Invalid JSON data provided[/red]")
                sys.exit(1)

        result = await benchmark_tool.benchmark_endpoint(
            endpoint=endpoint,
            method=method,
            requests=requests,
            concurrent=concurrent,
            data=request_data,
        )

        benchmark_tool._display_result(result)

    try:
        asyncio.run(run_single_benchmark())
    except KeyboardInterrupt:
        console.print("[yellow]Benchmark interrupted by user[/yellow]")
        sys.exit(1)


@benchmark.command()
@click.option("--url", default="http://localhost:8000", help="API base URL")
@click.option("--token", help="Authorization token")
@click.option("--target-rps", default=1000, help="Target requests per second")
@click.option("--duration", default=60, help="Test duration in seconds")
def load_test(url: str, token: str, target_rps: int, duration: int) -> None:
    """Run sustained load test."""

    console.print(f"[blue]Starting {duration}s load test at {target_rps} RPS...[/blue]")

    async def run_load_test() -> None:
        benchmark_tool = APIBenchmark(url, token)

        # Calculate requests needed
        target_rps * duration
        concurrent = min(100, target_rps // 10)  # Reasonable concurrency

        start_time = time.time()
        results = []

        # Run test in chunks to maintain steady rate
        chunk_duration = 10  # 10-second chunks
        requests_per_chunk = target_rps * chunk_duration

        for i in range(duration // chunk_duration):
            chunk_start = time.time()

            result = await benchmark_tool.benchmark_endpoint(
                endpoint="/health",
                requests=requests_per_chunk,
                concurrent=concurrent,
                timeout=chunk_duration + 5,
            )

            results.append(result)

            chunk_time = time.time() - chunk_start
            console.print(
                f"Chunk {i + 1}: {result.requests_per_second:.1f} RPS, "
                f"P95: {result.p95_response_time:.1f}ms"
            )

            # Sleep if we completed too quickly
            if chunk_time < chunk_duration:
                await asyncio.sleep(chunk_duration - chunk_time)

        # Calculate overall statistics
        total_time = time.time() - start_time
        total_requests_made = sum(r.total_requests for r in results)
        total_successful = sum(r.successful_requests for r in results)
        avg_rps = total_requests_made / total_time
        avg_p95 = statistics.mean([r.p95_response_time for r in results])
        error_rate = ((total_requests_made - total_successful) / total_requests_made) * 100

        console.print("\n[bold green]Load Test Results:[/bold green]")
        console.print(f"Duration: {total_time:.1f}s")
        console.print(f"Total Requests: {total_requests_made}")
        console.print(f"Average RPS: {avg_rps:.1f}")
        console.print(f"Average P95: {avg_p95:.1f}ms")
        console.print(f"Error Rate: {error_rate:.2f}%")

        # Assessment
        if avg_rps >= target_rps * 0.9 and avg_p95 <= 200 and error_rate <= 1:
            console.print("[bold green]✅ Load test passed![/bold green]")
        else:
            console.print("[bold red]❌ Load test failed[/bold red]")

    try:
        asyncio.run(run_load_test())
    except KeyboardInterrupt:
        console.print("[yellow]Load test interrupted by user[/yellow]")
        sys.exit(1)


if __name__ == "__main__":
    benchmark()
