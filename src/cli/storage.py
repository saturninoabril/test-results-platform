#!/usr/bin/env python3
"""
Storage CLI tool for Test Results Management API.
Provides file management, cleanup, usage reporting, backup/restore utilities, and health monitoring.
"""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any

import click
import structlog
from rich import print as rprint
from rich.console import Console
from rich.progress import track
from rich.prompt import Confirm
from rich.table import Table

# Import from the parent services
from ..lib.config import get_settings
from ..lib.database import get_session, init_database
from ..lib.storage import close_storage, get_storage_client, init_storage
from ..models.test_artifact import TestArtifact

logger = structlog.get_logger()
console = Console()


class StorageManager:
    """Manages storage operations and utilities."""

    def __init__(self) -> None:
        self.settings = get_settings()

    async def get_usage_stats(self) -> dict[str, Any]:
        """Get storage usage statistics."""
        await init_storage()
        storage_client = get_storage_client()

        try:
            # List all files to calculate usage
            files = await storage_client.list_files("")

            total_files = len(files)
            total_size = 0
            file_types = {}

            for file_info in files:
                size = file_info.get("size", 0)
                total_size += size

                # Categorize by file extension
                key = file_info.get("key", "")
                extension = Path(key).suffix.lower() or "no-extension"

                if extension not in file_types:
                    file_types[extension] = {"count": 0, "size": 0}

                file_types[extension]["count"] += 1
                file_types[extension]["size"] += size

            return {
                "total_files": total_files,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "file_types": file_types,
                "bucket": storage_client.settings.storage.bucket,  # type: ignore[attr-defined]
            }

        finally:
            await close_storage()

    async def cleanup_orphaned_files(self, dry_run: bool = True) -> dict[str, Any]:
        """Clean up files that are no longer referenced in the database."""
        await init_database()
        await init_storage()

        storage_client = get_storage_client()

        try:
            # Get all files from storage
            storage_files = await storage_client.list_files("")
            storage_keys = {file_info["key"] for file_info in storage_files}

            # Get all referenced files from database
            async with get_session() as session:
                from sqlalchemy import select

                result = await session.execute(select(TestArtifact.storage_key))
                db_keys = {row[0] for row in result if row[0]}

            # Find orphaned files
            orphaned_keys = storage_keys - db_keys

            orphaned_size = sum(
                file_info["size"]
                for file_info in storage_files
                if file_info["key"] in orphaned_keys
            )

            if not dry_run and orphaned_keys:
                # Delete orphaned files
                for key in orphaned_keys:
                    await storage_client.delete_file(key)

            return {
                "orphaned_files": len(orphaned_keys),
                "orphaned_size_bytes": orphaned_size,
                "orphaned_size_mb": round(orphaned_size / (1024 * 1024), 2),
                "orphaned_keys": list(orphaned_keys)[:100],  # Limit for display
                "dry_run": dry_run,
            }

        finally:
            await close_storage()

    async def cleanup_old_files(
        self, older_than_days: int = 30, dry_run: bool = True
    ) -> dict[str, Any]:
        """Clean up files older than specified days."""
        await init_storage()
        storage_client = get_storage_client()

        try:
            cutoff_date = datetime.now(UTC) - timedelta(days=older_than_days)

            # Get all files
            files = await storage_client.list_files("")
            old_files = []
            old_size = 0

            for file_info in files:
                # Check last modified date
                last_modified = file_info.get("last_modified")
                if last_modified and last_modified < cutoff_date:
                    old_files.append(file_info["key"])
                    old_size += file_info.get("size", 0)

            if not dry_run and old_files:
                # Delete old files
                for key in old_files:
                    await storage_client.delete_file(key)

            return {
                "old_files": len(old_files),
                "old_size_bytes": old_size,
                "old_size_mb": round(old_size / (1024 * 1024), 2),
                "cutoff_date": cutoff_date.isoformat(),
                "dry_run": dry_run,
            }

        finally:
            await close_storage()

    async def optimize_storage(self) -> dict[str, Any]:
        """Optimize storage by removing duplicates and compressing files."""
        await init_storage()
        storage_client = get_storage_client()

        try:
            # Get all files
            files = await storage_client.list_files("")

            # Find duplicates by content hash (if available)
            duplicates: dict[str, list[dict[str, Any]]] = {}
            total_savings = 0

            for file_info in files:
                etag = file_info.get("etag")
                if etag and etag in duplicates:
                    duplicates[etag].append(file_info)
                    total_savings += file_info.get("size", 0)
                elif etag:
                    duplicates[etag] = [file_info]

            # Find actual duplicates (more than one file with same hash)
            actual_duplicates = {k: v for k, v in duplicates.items() if len(v) > 1}

            return {
                "total_files": len(files),
                "duplicate_groups": len(actual_duplicates),
                "duplicate_files": sum(len(v) - 1 for v in actual_duplicates.values()),
                "potential_savings_bytes": total_savings,
                "potential_savings_mb": round(total_savings / (1024 * 1024), 2),
                "duplicates": {
                    k: [{"key": f["key"], "size": f["size"]} for f in v[:5]]
                    for k, v in list(actual_duplicates.items())[:10]
                },
            }

        finally:
            await close_storage()

    async def backup_storage(self, backup_path: Path, include_data: bool = True) -> dict[str, Any]:
        """Create a backup of storage contents."""
        await init_database()
        await init_storage()

        storage_client = get_storage_client()
        backup_path.mkdir(parents=True, exist_ok=True)

        try:
            # Create backup manifest
            manifest = {
                "backup_date": datetime.now(UTC).isoformat(),
                "bucket": storage_client.settings.storage.bucket,  # type: ignore[attr-defined]
                "files": [],
            }

            # Get all files
            files = await storage_client.list_files("")

            if include_data:
                # Download all files
                for file_info in track(files, description="Backing up files..."):
                    key = file_info["key"]
                    try:
                        # Create local path preserving structure
                        local_path = backup_path / key
                        local_path.parent.mkdir(parents=True, exist_ok=True)

                        # Download file
                        content = await storage_client.download_file(key)
                        with open(local_path, "wb") as f:
                            f.write(content)

                        manifest["files"].append(
                            {
                                "key": key,
                                "size": file_info.get("size", 0),
                                "local_path": str(local_path.relative_to(backup_path)),
                                "etag": file_info.get("etag"),
                            }
                        )

                    except Exception as e:
                        rprint(f"⚠️  Failed to backup {key}: {e}")

            else:
                # Just create manifest without downloading
                manifest["files"] = [
                    {
                        "key": file_info["key"],
                        "size": file_info.get("size", 0),
                        "etag": file_info.get("etag"),
                        "last_modified": file_info.get("last_modified", "").isoformat()
                        if file_info.get("last_modified")
                        else None,
                    }
                    for file_info in files
                ]

            # Save manifest
            manifest_path = backup_path / "manifest.json"
            with open(manifest_path, "w", encoding="utf-8") as f:  # type: ignore[assignment]
                json.dump(manifest, f, indent=2, default=str)  # type: ignore[arg-type]

            # Get database backup
            async with get_session() as session:
                from sqlalchemy import select

                result = await session.execute(select(TestArtifact))
                artifacts = result.scalars().all()

                db_backup = [
                    {
                        "id": str(artifact.id),
                        "result_id": str(artifact.result_id),
                        "artifact_type": artifact.artifact_type,
                        "file_name": artifact.file_name,
                        "storage_key": artifact.storage_key,
                        "file_size": artifact.file_size,
                        "mime_type": artifact.mime_type,
                        "metadata": artifact.metadata,
                        "created_at": artifact.created_at.isoformat(),
                    }
                    for artifact in artifacts
                ]

                db_backup_path = backup_path / "artifacts_db.json"
                with open(db_backup_path, "w", encoding="utf-8") as f:  # type: ignore[assignment]
                    json.dump(db_backup, f, indent=2, default=str)  # type: ignore[arg-type]

            total_size = sum(f.get("size", 0) for f in files)

            return {
                "backup_path": str(backup_path),
                "total_files": len(files),
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "include_data": include_data,
                "manifest_file": str(manifest_path),
                "db_backup_file": str(db_backup_path),
            }

        finally:
            await close_storage()

    async def restore_storage(self, backup_path: Path, restore_data: bool = True) -> dict[str, Any]:
        """Restore storage from backup."""
        manifest_path = backup_path / "manifest.json"

        if not manifest_path.exists():
            raise FileNotFoundError(f"Backup manifest not found: {manifest_path}")

        await init_storage()
        storage_client = get_storage_client()

        try:
            # Load manifest
            with open(manifest_path) as f:
                manifest = json.load(f)

            restored_files = 0

            if restore_data:
                # Restore files
                for file_info in track(manifest["files"], description="Restoring files..."):
                    key = file_info["key"]
                    local_path = backup_path / file_info.get("local_path", key)

                    if local_path.exists():
                        with open(local_path, "rb") as f:
                            await storage_client.upload_file(
                                f,
                                key,
                                file_info.get("mime_type", "application/octet-stream"),
                            )
                        restored_files += 1

            # Restore database records (if needed)
            db_backup_path = backup_path / "artifacts_db.json"
            db_backup: list[dict[str, Any]] = []

            if db_backup_path.exists():
                with open(db_backup_path) as f:
                    db_backup = json.load(f)

                # Note: This is a simplified restore - in production, you'd want more
                # sophisticated conflict resolution
                rprint("ℹ️  Database restore not implemented - manual intervention required")
                rprint(f"   Found {len(db_backup)} artifact records in backup")

            return {
                "restored_files": restored_files,
                "total_files_in_backup": len(manifest["files"]),
                "restore_data": restore_data,
                "backup_date": manifest.get("backup_date"),
                "db_records_found": len(db_backup),
            }

        finally:
            await close_storage()

    async def health_check(self) -> dict[str, Any]:
        """Perform comprehensive storage health check."""
        health_status: dict[str, Any] = {
            "overall_healthy": True,
            "checks": {},
            "warnings": [],
            "errors": [],
        }

        try:
            await init_storage()
            storage_client = get_storage_client()

            # Check 1: Connection test
            try:
                await storage_client.list_files("", limit=1)
                health_status["checks"]["connection"] = {
                    "status": "healthy",
                    "message": "Storage connection successful",
                }
            except Exception as e:
                health_status["checks"]["connection"] = {"status": "error", "message": str(e)}
                health_status["errors"].append(f"Connection failed: {e}")
                health_status["overall_healthy"] = False

            # Check 2: Bucket access
            try:
                # Try to upload and delete a test file
                test_key = f"health-check-{datetime.now().timestamp()}.txt"
                test_content = BytesIO(b"health check")
                await storage_client.upload_file(test_content, test_key, "text/plain")
                await storage_client.delete_file(test_key)
                health_status["checks"]["write_access"] = {
                    "status": "healthy",
                    "message": "Write access confirmed",
                }
            except Exception as e:
                health_status["checks"]["write_access"] = {"status": "error", "message": str(e)}
                health_status["errors"].append(f"Write access failed: {e}")
                health_status["overall_healthy"] = False

            # Check 3: Storage usage
            try:
                usage_stats = await self.get_usage_stats()
                total_size_gb = usage_stats["total_size_bytes"] / (1024**3)

                # Warn if usage is high (> 10GB for this example)
                if total_size_gb > 10:
                    health_status["warnings"].append(f"High storage usage: {total_size_gb:.2f} GB")

                health_status["checks"]["usage"] = {
                    "status": "healthy" if total_size_gb <= 10 else "warning",
                    "message": f"Using {total_size_gb:.2f} GB ({usage_stats['total_files']} files)",
                }
            except Exception as e:
                health_status["checks"]["usage"] = {"status": "error", "message": str(e)}
                health_status["errors"].append(f"Usage check failed: {e}")

            # Check 4: Database consistency
            try:
                orphaned_stats = await self.cleanup_orphaned_files(dry_run=True)
                if orphaned_stats["orphaned_files"] > 0:
                    health_status["warnings"].append(
                        f"{orphaned_stats['orphaned_files']} orphaned files ({orphaned_stats['orphaned_size_mb']} MB)"
                    )

                health_status["checks"]["consistency"] = {
                    "status": "healthy" if orphaned_stats["orphaned_files"] == 0 else "warning",
                    "message": f"Found {orphaned_stats['orphaned_files']} orphaned files",
                }
            except Exception as e:
                health_status["checks"]["consistency"] = {"status": "error", "message": str(e)}
                health_status["errors"].append(f"Consistency check failed: {e}")

        finally:
            await close_storage()

        return health_status

    async def monitor_performance(self, test_count: int = 10) -> dict[str, Any]:
        """Monitor storage performance with test operations."""
        await init_storage()
        storage_client = get_storage_client()

        performance_results: dict[str, Any] = {"test_count": test_count, "operations": {}}

        try:
            import time

            # Test upload performance
            upload_times = []
            test_data = b"x" * 1024  # 1KB test file

            for i in track(range(test_count), description="Testing upload performance..."):
                test_key = f"perf-test-{i}-{int(time.time())}.bin"

                start_time = time.time()
                test_file = BytesIO(test_data)
                await storage_client.upload_file(test_file, test_key, "application/octet-stream")
                upload_time = time.time() - start_time
                upload_times.append(upload_time)

                # Clean up immediately
                await storage_client.delete_file(test_key)

            performance_results["operations"]["upload"] = {
                "avg_time_ms": round(sum(upload_times) / len(upload_times) * 1000, 2),
                "min_time_ms": round(min(upload_times) * 1000, 2),
                "max_time_ms": round(max(upload_times) * 1000, 2),
                "total_time_ms": round(sum(upload_times) * 1000, 2),
            }

            # Test list performance
            list_times = []

            for _ in track(range(min(test_count, 5)), description="Testing list performance..."):
                start_time = time.time()
                await storage_client.list_files("", limit=100)
                list_time = time.time() - start_time
                list_times.append(list_time)

            performance_results["operations"]["list"] = {
                "avg_time_ms": round(sum(list_times) / len(list_times) * 1000, 2),
                "min_time_ms": round(min(list_times) * 1000, 2),
                "max_time_ms": round(max(list_times) * 1000, 2),
                "total_time_ms": round(sum(list_times) * 1000, 2),
            }

        finally:
            await close_storage()

        return performance_results


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.pass_context
def storage_cli(ctx: Any, verbose: bool) -> None:
    """Test Results Storage Management CLI.

    File management, cleanup, backup/restore, and health monitoring for storage.
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose

    if verbose:
        structlog.configure(
            wrapper_class=structlog.make_filtering_bound_logger(20),
        )


@storage_cli.command("usage")
@click.option(
    "--format", "-f", type=click.Choice(["table", "json"]), default="table", help="Output format"
)
@click.pass_context
def show_usage(ctx: Any, format: str) -> None:
    """Show storage usage statistics."""

    async def _usage() -> None:
        manager = StorageManager()

        try:
            rprint("📊 Analyzing storage usage...")
            stats = await manager.get_usage_stats()

            if format == "json":
                rprint(json.dumps(stats, indent=2))
            else:
                # Display overview
                rprint(f"\n📁 [bold]Storage Overview[/bold] ({stats['bucket']})\n")

                overview_table = Table()
                overview_table.add_column("Metric", style="cyan")
                overview_table.add_column("Value", style="white")

                overview_table.add_row("Total Files", f"{stats['total_files']:,}")
                overview_table.add_row("Total Size", f"{stats['total_size_mb']:,.2f} MB")
                overview_table.add_row("Total Size", f"{stats['total_size_bytes']:,} bytes")

                console.print(overview_table)

                # Display file type breakdown
                if stats["file_types"]:
                    rprint("\n📋 [bold]File Type Breakdown[/bold]\n")

                    types_table = Table()
                    types_table.add_column("Extension", style="cyan")
                    types_table.add_column("Count", style="white", justify="right")
                    types_table.add_column("Size (MB)", style="yellow", justify="right")
                    types_table.add_column("Percentage", style="green", justify="right")

                    total_size = stats["total_size_bytes"]
                    for ext, info in sorted(
                        stats["file_types"].items(), key=lambda x: x[1]["size"], reverse=True
                    ):
                        size_mb = info["size"] / (1024 * 1024)
                        percentage = (info["size"] / total_size * 100) if total_size > 0 else 0
                        types_table.add_row(
                            ext if ext != "no-extension" else "<no-ext>",
                            f"{info['count']:,}",
                            f"{size_mb:.2f}",
                            f"{percentage:.1f}%",
                        )

                    console.print(types_table)

        except Exception as e:
            rprint(f"❌ [bold red]Failed to get usage stats:[/bold red] {e}")
            if ctx.obj.get("verbose"):
                raise

    asyncio.run(_usage())


@storage_cli.command("cleanup")
@click.option("--orphaned", is_flag=True, help="Clean up orphaned files")
@click.option("--old-files", is_flag=True, help="Clean up old files")
@click.option(
    "--older-than",
    "-o",
    type=int,
    default=30,
    help="Delete files older than N days (for --old-files)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=True,
    help="Show what would be cleaned without actually cleaning",
)
@click.option("--confirm", is_flag=True, help="Actually perform the cleanup")
@click.pass_context
def cleanup_storage(
    ctx: Any, orphaned: bool, old_files: bool, older_than: int, dry_run: bool, confirm: bool
) -> None:
    """Clean up storage by removing orphaned or old files.

    Examples:
      storage cleanup --orphaned --dry-run
      storage cleanup --old-files --older-than 90 --confirm
      storage cleanup --orphaned --old-files --confirm
    """
    if confirm:
        dry_run = False

    if not orphaned and not old_files:
        rprint("❌ Please specify --orphaned and/or --old-files")
        return

    async def _cleanup() -> None:
        manager = StorageManager()

        try:
            results = {}

            if orphaned:
                if not dry_run and not Confirm.ask("Clean up orphaned files?"):
                    rprint("❌ Orphaned cleanup cancelled")
                    return

                rprint("🧹 Checking for orphaned files...")
                orphaned_result = await manager.cleanup_orphaned_files(dry_run)
                results["orphaned"] = orphaned_result

            if old_files:
                if not dry_run and not Confirm.ask(f"Clean up files older than {older_than} days?"):
                    rprint("❌ Old files cleanup cancelled")
                    return

                rprint(f"🧹 Checking for files older than {older_than} days...")
                old_files_result = await manager.cleanup_old_files(older_than, dry_run)
                results["old_files"] = old_files_result

            # Display results
            for cleanup_type, result in results.items():
                rprint(f"\n📊 [bold]{cleanup_type.title()} Cleanup Results[/bold]\n")

                if cleanup_type == "orphaned":
                    if result["dry_run"]:
                        rprint(f"🔍 Found {result['orphaned_files']} orphaned files")
                        rprint(f"💾 Would free {result['orphaned_size_mb']} MB")
                    else:
                        rprint(f"✅ Cleaned {result['orphaned_files']} orphaned files")
                        rprint(f"💾 Freed {result['orphaned_size_mb']} MB")

                elif cleanup_type == "old_files":
                    if result["dry_run"]:
                        rprint(f"🔍 Found {result['old_files']} old files")
                        rprint(f"📅 Older than {result['cutoff_date'][:19]}")
                        rprint(f"💾 Would free {result['old_size_mb']} MB")
                    else:
                        rprint(f"✅ Cleaned {result['old_files']} old files")
                        rprint(f"💾 Freed {result['old_size_mb']} MB")

            if any(r["dry_run"] for r in results.values()):
                rprint("\n💡 Use --confirm to actually perform the cleanup")

        except Exception as e:
            rprint(f"❌ [bold red]Cleanup failed:[/bold red] {e}")
            if ctx.obj.get("verbose"):
                raise

    asyncio.run(_cleanup())


@storage_cli.command("optimize")
@click.pass_context
def optimize_storage(ctx: Any) -> None:
    """Optimize storage by finding duplicates and suggesting improvements."""

    async def _optimize() -> None:
        manager = StorageManager()

        try:
            rprint("🔍 Analyzing storage for optimization opportunities...")
            result = await manager.optimize_storage()

            rprint("\n📊 [bold]Storage Optimization Analysis[/bold]\n")

            overview_table = Table()
            overview_table.add_column("Metric", style="cyan")
            overview_table.add_column("Value", style="white")

            overview_table.add_row("Total Files", f"{result['total_files']:,}")
            overview_table.add_row("Duplicate Groups", str(result["duplicate_groups"]))
            overview_table.add_row("Duplicate Files", str(result["duplicate_files"]))
            overview_table.add_row("Potential Savings", f"{result['potential_savings_mb']} MB")

            console.print(overview_table)

            if result["duplicates"]:
                rprint("\n🔍 [bold]Sample Duplicates (by content hash)[/bold]\n")

                for etag, files in list(result["duplicates"].items())[:5]:
                    rprint(f"📄 Hash: [dim]{etag[:16]}...[/dim]")
                    for file_info in files:
                        size_kb = file_info["size"] / 1024
                        rprint(f"   • {file_info['key']} ({size_kb:.1f} KB)")
                    rprint()

            if result["duplicate_files"] > 0:
                rprint("💡 [yellow]Recommendations:[/yellow]")
                rprint("   • Review duplicate files for potential removal")
                rprint("   • Consider deduplication at the application level")
                rprint(f"   • Could save up to {result['potential_savings_mb']} MB")
            else:
                rprint("✅ [green]No duplicates found - storage is optimized![/green]")

        except Exception as e:
            rprint(f"❌ [bold red]Optimization analysis failed:[/bold red] {e}")
            if ctx.obj.get("verbose"):
                raise

    asyncio.run(_optimize())


@storage_cli.command("backup")
@click.argument("backup_path", type=click.Path(path_type=Path))
@click.option("--metadata-only", is_flag=True, help="Backup metadata only (no file data)")
@click.pass_context
def backup_storage(ctx: Any, backup_path: Path, metadata_only: bool) -> None:
    """Create a backup of storage contents.

    Examples:
      storage backup ./backup/2024-09-14
      storage backup ./backup/metadata --metadata-only
    """

    async def _backup() -> None:
        manager = StorageManager()

        try:
            include_data = not metadata_only

            if include_data:
                rprint(f"📦 Creating full backup to [cyan]{backup_path}[/cyan]...")
            else:
                rprint(f"📋 Creating metadata backup to [cyan]{backup_path}[/cyan]...")

            result = await manager.backup_storage(backup_path, include_data)

            rprint("\n✅ [bold green]Backup completed![/bold green]\n")

            backup_table = Table()
            backup_table.add_column("Item", style="cyan")
            backup_table.add_column("Value", style="white")

            backup_table.add_row("Backup Path", result["backup_path"])
            backup_table.add_row("Total Files", str(result["total_files"]))
            backup_table.add_row("Total Size", f"{result['total_size_mb']} MB")
            backup_table.add_row(
                "Include Data", "Yes" if result["include_data"] else "No (metadata only)"
            )
            backup_table.add_row("Manifest File", result["manifest_file"])
            backup_table.add_row("DB Backup File", result["db_backup_file"])

            console.print(backup_table)

            rprint(f"\n💡 To restore: [dim]storage restore {backup_path}[/dim]")

        except Exception as e:
            rprint(f"❌ [bold red]Backup failed:[/bold red] {e}")
            if ctx.obj.get("verbose"):
                raise

    asyncio.run(_backup())


@storage_cli.command("restore")
@click.argument("backup_path", type=click.Path(exists=True, path_type=Path))
@click.option("--metadata-only", is_flag=True, help="Restore metadata only (no file data)")
@click.option("--confirm", is_flag=True, help="Confirm the restore operation")
@click.pass_context
def restore_storage(ctx: Any, backup_path: Path, metadata_only: bool, confirm: bool) -> None:
    """Restore storage from backup.

    Examples:
      storage restore ./backup/2024-09-14 --confirm
      storage restore ./backup/metadata --metadata-only --confirm
    """
    if not confirm and not Confirm.ask("Are you sure you want to restore storage?"):
        rprint("❌ Restore cancelled")
        return

    async def _restore() -> None:
        manager = StorageManager()

        try:
            restore_data = not metadata_only

            if restore_data:
                rprint(f"📦 Restoring full backup from [cyan]{backup_path}[/cyan]...")
            else:
                rprint(f"📋 Restoring metadata from [cyan]{backup_path}[/cyan]...")

            result = await manager.restore_storage(backup_path, restore_data)

            rprint("\n✅ [bold green]Restore completed![/bold green]\n")

            restore_table = Table()
            restore_table.add_column("Item", style="cyan")
            restore_table.add_column("Value", style="white")

            restore_table.add_row("Restored Files", str(result["restored_files"]))
            restore_table.add_row("Total in Backup", str(result["total_files_in_backup"]))
            restore_table.add_row(
                "Include Data", "Yes" if result["restore_data"] else "No (metadata only)"
            )
            restore_table.add_row(
                "Backup Date", result["backup_date"][:19] if result["backup_date"] else "Unknown"
            )
            restore_table.add_row("DB Records Found", str(result["db_records_found"]))

            console.print(restore_table)

            if result["db_records_found"] > 0:
                rprint("\n⚠️  [yellow]Database records found in backup but not restored[/yellow]")
                rprint("   Manual intervention required for database restoration")

        except Exception as e:
            rprint(f"❌ [bold red]Restore failed:[/bold red] {e}")
            if ctx.obj.get("verbose"):
                raise

    asyncio.run(_restore())


@storage_cli.command("health")
@click.option("--detailed", is_flag=True, help="Show detailed health information")
@click.pass_context
def health_check(ctx: Any, detailed: bool) -> None:
    """Perform storage health check."""

    async def _health() -> None:
        manager = StorageManager()

        try:
            rprint("🏥 Performing storage health check...")

            result = await manager.health_check()

            # Overall status
            if result["overall_healthy"]:
                rprint("\n✅ [bold green]Storage is healthy![/bold green]\n")
            else:
                rprint("\n❌ [bold red]Storage health issues detected![/bold red]\n")

            # Health checks table
            checks_table = Table(title="Health Checks")
            checks_table.add_column("Check", style="cyan")
            checks_table.add_column("Status", style="white")
            checks_table.add_column("Details", style="blue")

            for check_name, check_result in result["checks"].items():
                status = check_result["status"]
                status_icon = {"healthy": "✅", "warning": "⚠️", "error": "❌"}.get(status, "❓")

                checks_table.add_row(
                    check_name.replace("_", " ").title(),
                    f"{status_icon} {status.title()}",
                    check_result["message"],
                )

            console.print(checks_table)

            # Warnings and errors
            if result["warnings"]:
                rprint("\n⚠️  [bold yellow]Warnings:[/bold yellow]")
                for warning in result["warnings"]:
                    rprint(f"   • {warning}")

            if result["errors"]:
                rprint("\n❌ [bold red]Errors:[/bold red]")
                for error in result["errors"]:
                    rprint(f"   • {error}")

            if detailed and (result["warnings"] or result["errors"]):
                rprint("\n💡 [bold blue]Recommendations:[/bold blue]")
                rprint("   • Run 'storage cleanup --orphaned --confirm' to remove orphaned files")
                rprint("   • Check storage credentials and network connectivity")
                rprint("   • Monitor storage usage and consider cleanup policies")

        except Exception as e:
            rprint(f"❌ [bold red]Health check failed:[/bold red] {e}")
            if ctx.obj.get("verbose"):
                raise

    asyncio.run(_health())


@storage_cli.command("monitor")
@click.option(
    "--test-count", "-c", type=int, default=10, help="Number of test operations to perform"
)
@click.pass_context
def monitor_performance(ctx: Any, test_count: int) -> None:
    """Monitor storage performance with test operations."""

    async def _monitor() -> None:
        manager = StorageManager()

        try:
            rprint(f"⚡ Testing storage performance with {test_count} operations...")

            result = await manager.monitor_performance(test_count)

            rprint("\n📊 [bold]Storage Performance Results[/bold]\n")

            perf_table = Table()
            perf_table.add_column("Operation", style="cyan")
            perf_table.add_column("Avg Time (ms)", style="white", justify="right")
            perf_table.add_column("Min Time (ms)", style="green", justify="right")
            perf_table.add_column("Max Time (ms)", style="red", justify="right")
            perf_table.add_column("Total Time (ms)", style="blue", justify="right")

            for operation, metrics in result["operations"].items():
                perf_table.add_row(
                    operation.title(),
                    str(metrics["avg_time_ms"]),
                    str(metrics["min_time_ms"]),
                    str(metrics["max_time_ms"]),
                    str(metrics["total_time_ms"]),
                )

            console.print(perf_table)

            # Performance assessment
            upload_avg = result["operations"]["upload"]["avg_time_ms"]
            list_avg = result["operations"]["list"]["avg_time_ms"]

            rprint("\n💡 [bold blue]Performance Assessment:[/bold blue]")

            if upload_avg < 100:
                rprint("   ✅ Upload performance: Excellent")
            elif upload_avg < 500:
                rprint("   👍 Upload performance: Good")
            else:
                rprint("   ⚠️  Upload performance: Slow - consider checking network/storage")

            if list_avg < 50:
                rprint("   ✅ List performance: Excellent")
            elif list_avg < 200:
                rprint("   👍 List performance: Good")
            else:
                rprint("   ⚠️  List performance: Slow - consider storage optimization")

        except Exception as e:
            rprint(f"❌ [bold red]Performance monitoring failed:[/bold red] {e}")
            if ctx.obj.get("verbose"):
                raise

    asyncio.run(_monitor())


if __name__ == "__main__":
    storage_cli()
