#!/usr/bin/env python3
"""
Test Results CLI tool for Test Results Management API.
Provides commands for data import, export, management, and validation.
"""

import asyncio
import csv
import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timezone

import click
import structlog
from rich import print as rprint
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, TaskID
from rich.prompt import Prompt, Confirm

# Import from the parent services
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.config import get_settings
from lib.database import init_database, get_session
from models.test_framework import TestFramework
from models.test_environment import TestEnvironment
from models.test_suite import TestSuite
from models.test_result import TestResult
from models.test_artifact import TestArtifact

logger = structlog.get_logger()
console = Console()


class TestResultsManager:
    """Manages test results data operations."""

    def __init__(self):
        self.settings = get_settings()

    async def import_data(self, file_path: Path, format_type: str = "auto") -> Dict[str, Any]:
        """Import test data from various formats."""
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Detect format if auto
        if format_type == "auto":
            format_type = self._detect_format(file_path)

        rprint(f"📥 Importing data from [cyan]{file_path}[/cyan] as [yellow]{format_type}[/yellow] format")

        with open(file_path, 'r', encoding='utf-8') as f:
            if format_type in ['json', 'playwright', 'cypress']:
                data = json.load(f)
                return await self._import_json_data(data, format_type)
            elif format_type == 'csv':
                return await self._import_csv_data(f)
            else:
                raise ValueError(f"Unsupported format: {format_type}")

    def _detect_format(self, file_path: Path) -> str:
        """Auto-detect file format based on extension and content."""
        extension = file_path.suffix.lower()

        if extension == '.csv':
            return 'csv'
        elif extension == '.json':
            # Try to detect JSON subformat
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)

                if 'config' in data and 'suites' in data:
                    return 'playwright'
                elif 'stats' in data and 'results' in data:
                    return 'cypress'
                else:
                    return 'json'
            except Exception:
                return 'json'
        else:
            return 'json'  # Default fallback

    async def _import_json_data(self, data: Dict[str, Any], format_type: str) -> Dict[str, Any]:
        """Import JSON data based on format type."""
        async with get_session() as session:
            if format_type == 'playwright':
                return await self._import_playwright_data(session, data)
            elif format_type == 'cypress':
                return await self._import_cypress_data(session, data)
            elif format_type == 'json':
                return await self._import_generic_json_data(session, data)
            else:
                raise ValueError(f"Unsupported JSON format: {format_type}")

    async def _import_playwright_data(self, session, data: Dict[str, Any]) -> Dict[str, Any]:
        """Import Playwright test results."""
        stats = {"frameworks": 0, "environments": 0, "suites": 0, "results": 0}

        # Extract framework info
        config = data.get('config', {})
        framework_name = 'playwright'
        framework_version = config.get('version', '1.55.0')

        # Create or get framework
        framework = await self._ensure_framework(
            session, framework_name, framework_version,
            {"source": "cli_import", "original_config": config}
        )
        stats["frameworks"] = 1

        # Process each project/suite
        for suite_data in data.get('suites', []):
            project_name = suite_data.get('title', 'default')

            # Create environment
            environment = await self._ensure_environment(
                session, f"playwright-{project_name}", "chromium", "ubuntu",
                {"project": project_name, "source": "cli_import"}
            )
            stats["environments"] += 1

            # Process specs and tests
            total_tests = 0
            passed_tests = 0
            failed_tests = 0
            total_duration = 0

            results_to_create = []

            for spec in suite_data.get('specs', []):
                for test in spec.get('tests', []):
                    total_tests += 1
                    test_result = test.get('results', [{}])[0]

                    status = test_result.get('status', 'unknown')
                    if status == 'passed':
                        passed_tests += 1
                    elif status == 'failed':
                        failed_tests += 1

                    duration = test_result.get('duration', 0)
                    total_duration += duration

                    results_to_create.append({
                        'name': test.get('title', 'Unknown Test'),
                        'status': status,
                        'duration_ms': duration,
                        'full_title': f"{suite_data.get('title', '')} {test.get('title', '')}".strip(),
                        'external_id': f"playwright-{project_name}-{test.get('title', '')}-{hash(test.get('title', ''))}",
                        'tags': ['playwright', project_name, 'imported'],
                        'metadata': {
                            'spec_file': spec.get('title', ''),
                            'retry_count': test_result.get('retry', 0),
                            'project': project_name,
                            'imported_at': datetime.now(timezone.utc).isoformat()
                        }
                    })

            # Create suite
            if total_tests > 0:
                suite = TestSuite(
                    framework_id=framework.id,
                    environment_id=environment.id,
                    name=f"Playwright {project_name} Suite",
                    total_count=total_tests,
                    passed_count=passed_tests,
                    failed_count=failed_tests,
                    skipped_count=total_tests - passed_tests - failed_tests,
                    duration_ms=total_duration,
                    metadata={
                        'project': project_name,
                        'source': 'cli_import',
                        'imported_at': datetime.now(timezone.utc).isoformat()
                    }
                )
                session.add(suite)
                await session.flush()
                stats["suites"] += 1

                # Create test results
                for result_data in results_to_create:
                    result = TestResult(
                        suite_id=suite.id,
                        **result_data
                    )
                    session.add(result)
                    stats["results"] += 1

            await session.commit()

        return stats

    async def _import_cypress_data(self, session, data: Dict[str, Any]) -> Dict[str, Any]:
        """Import Cypress test results."""
        stats = {"frameworks": 0, "environments": 0, "suites": 0, "results": 0}

        # Extract framework info
        meta = data.get('meta', {})
        framework_version = meta.get('mochawesome', {}).get('version', '13.6.0')

        # Create or get framework
        framework = await self._ensure_framework(
            session, 'cypress', framework_version,
            {"source": "cli_import", "meta": meta}
        )
        stats["frameworks"] = 1

        # Create environment
        environment = await self._ensure_environment(
            session, "cypress-import", "chrome", "ubuntu",
            {"source": "cli_import", "meta": meta}
        )
        stats["environments"] += 1

        # Extract stats
        test_stats = data.get('stats', {})
        total_tests = test_stats.get('tests', 0)
        passed_tests = test_stats.get('passes', 0)
        failed_tests = test_stats.get('failures', 0)
        skipped_tests = test_stats.get('pending', 0)
        total_duration = test_stats.get('duration', 0)

        # Create suite
        suite = TestSuite(
            framework_id=framework.id,
            environment_id=environment.id,
            name="Cypress Test Suite",
            total_count=total_tests,
            passed_count=passed_tests,
            failed_count=failed_tests,
            skipped_count=skipped_tests,
            duration_ms=total_duration,
            metadata={
                'source': 'cli_import',
                'imported_at': datetime.now(timezone.utc).isoformat(),
                'original_stats': test_stats
            }
        )
        session.add(suite)
        await session.flush()
        stats["suites"] += 1

        # Process test results
        for result_group in data.get('results', []):
            for suite_data in result_group.get('suites', []):
                for test in suite_data.get('tests', []):
                    result = TestResult(
                        suite_id=suite.id,
                        name=test.get('title', 'Unknown Test'),
                        status=test.get('state', 'unknown'),
                        duration_ms=test.get('duration', 0),
                        full_title=test.get('fullTitle', test.get('title', '')),
                        external_id=test.get('uuid', f"cypress-{hash(test.get('title', ''))}"),
                        error_message=test.get('err', {}).get('message') if test.get('err') else None,
                        tags=['cypress', 'imported'],
                        metadata={
                            'suite': suite_data.get('title', ''),
                            'file': result_group.get('file', ''),
                            'uuid': test.get('uuid'),
                            'imported_at': datetime.now(timezone.utc).isoformat()
                        }
                    )
                    session.add(result)
                    stats["results"] += 1

        await session.commit()
        return stats

    async def _import_generic_json_data(self, session, data: Union[List, Dict]) -> Dict[str, Any]:
        """Import generic JSON test data."""
        stats = {"frameworks": 0, "environments": 0, "suites": 0, "results": 0}

        # Handle both array and object formats
        if isinstance(data, dict):
            if 'results' in data:
                results_data = data['results']
                framework_info = data.get('framework', {})
                environment_info = data.get('environment', {})
            else:
                # Assume the dict itself contains result fields
                results_data = [data]
                framework_info = {}
                environment_info = {}
        else:
            results_data = data
            framework_info = {}
            environment_info = {}

        # Create framework
        framework_name = framework_info.get('name', 'generic')
        framework_version = framework_info.get('version', '1.0.0')
        framework = await self._ensure_framework(
            session, framework_name, framework_version,
            {"source": "cli_import", "imported_at": datetime.now(timezone.utc).isoformat()}
        )
        stats["frameworks"] = 1

        # Create environment
        environment_name = environment_info.get('name', 'generic-import')
        environment = await self._ensure_environment(
            session, environment_name,
            environment_info.get('browser', 'unknown'),
            environment_info.get('os', 'unknown'),
            {"source": "cli_import", "imported_at": datetime.now(timezone.utc).isoformat()}
        )
        stats["environments"] += 1

        # Calculate suite stats
        total_tests = len(results_data)
        passed_tests = sum(1 for r in results_data if r.get('status') == 'passed')
        failed_tests = sum(1 for r in results_data if r.get('status') == 'failed')
        skipped_tests = sum(1 for r in results_data if r.get('status') == 'skipped')
        total_duration = sum(r.get('duration_ms', 0) for r in results_data)

        # Create suite
        suite = TestSuite(
            framework_id=framework.id,
            environment_id=environment.id,
            name="Imported Test Suite",
            total_count=total_tests,
            passed_count=passed_tests,
            failed_count=failed_tests,
            skipped_count=skipped_tests,
            duration_ms=total_duration,
            metadata={
                'source': 'cli_import',
                'imported_at': datetime.now(timezone.utc).isoformat()
            }
        )
        session.add(suite)
        await session.flush()
        stats["suites"] += 1

        # Create test results
        for result_data in results_data:
            result = TestResult(
                suite_id=suite.id,
                name=result_data.get('name', result_data.get('title', 'Unknown Test')),
                status=result_data.get('status', 'unknown'),
                duration_ms=result_data.get('duration_ms', result_data.get('duration', 0)),
                full_title=result_data.get('full_title', result_data.get('name', '')),
                external_id=result_data.get('external_id', f"import-{hash(str(result_data))}"),
                error_message=result_data.get('error_message'),
                tags=result_data.get('tags', ['imported']),
                metadata={
                    **result_data.get('metadata', {}),
                    'imported_at': datetime.now(timezone.utc).isoformat()
                }
            )
            session.add(result)
            stats["results"] += 1

        await session.commit()
        return stats

    async def _import_csv_data(self, file_obj) -> Dict[str, Any]:
        """Import test data from CSV format."""
        stats = {"frameworks": 0, "environments": 0, "suites": 0, "results": 0}

        async with get_session() as session:
            reader = csv.DictReader(file_obj)

            # Create default framework and environment
            framework = await self._ensure_framework(
                session, 'csv-import', '1.0.0',
                {"source": "csv_import", "imported_at": datetime.now(timezone.utc).isoformat()}
            )
            stats["frameworks"] = 1

            environment = await self._ensure_environment(
                session, 'csv-import-env', 'unknown', 'unknown',
                {"source": "csv_import", "imported_at": datetime.now(timezone.utc).isoformat()}
            )
            stats["environments"] = 1

            # Group results by suite (if suite column exists)
            suites = {}
            results_data = []

            for row in reader:
                suite_name = row.get('suite', row.get('suite_name', 'Default Suite'))
                if suite_name not in suites:
                    suites[suite_name] = []

                suites[suite_name].append({
                    'name': row.get('name', row.get('test_name', 'Unknown')),
                    'status': row.get('status', 'unknown').lower(),
                    'duration_ms': int(float(row.get('duration_ms', row.get('duration', 0)))),
                    'error_message': row.get('error_message', row.get('error')),
                    'tags': [tag.strip() for tag in row.get('tags', 'imported').split(',')],
                    'metadata': {k: v for k, v in row.items() if k not in ['name', 'status', 'duration_ms', 'error_message', 'tags']}
                })

            # Create suites and results
            for suite_name, suite_results in suites.items():
                total_tests = len(suite_results)
                passed_tests = sum(1 for r in suite_results if r['status'] == 'passed')
                failed_tests = sum(1 for r in suite_results if r['status'] == 'failed')
                skipped_tests = sum(1 for r in suite_results if r['status'] == 'skipped')
                total_duration = sum(r['duration_ms'] for r in suite_results)

                suite = TestSuite(
                    framework_id=framework.id,
                    environment_id=environment.id,
                    name=suite_name,
                    total_count=total_tests,
                    passed_count=passed_tests,
                    failed_count=failed_tests,
                    skipped_count=skipped_tests,
                    duration_ms=total_duration,
                    metadata={
                        'source': 'csv_import',
                        'imported_at': datetime.now(timezone.utc).isoformat()
                    }
                )
                session.add(suite)
                await session.flush()
                stats["suites"] += 1

                # Create results
                for result_data in suite_results:
                    result = TestResult(
                        suite_id=suite.id,
                        external_id=f"csv-{hash(f'{suite_name}-{result_data['name']}')}",
                        **result_data
                    )
                    session.add(result)
                    stats["results"] += 1

            await session.commit()

        return stats

    async def _ensure_framework(self, session, name: str, version: str, metadata: Dict) -> TestFramework:
        """Get or create a framework."""
        from sqlalchemy import select

        # Try to find existing framework
        result = await session.execute(
            select(TestFramework).where(
                TestFramework.name == name,
                TestFramework.version == version
            )
        )
        framework = result.scalar_one_or_none()

        if not framework:
            framework = TestFramework(
                name=name,
                version=version,
                config_metadata=metadata
            )
            session.add(framework)
            await session.flush()

        return framework

    async def _ensure_environment(self, session, name: str, browser: str, os: str, metadata: Dict) -> TestEnvironment:
        """Get or create an environment."""
        from sqlalchemy import select

        # Try to find existing environment
        result = await session.execute(
            select(TestEnvironment).where(
                TestEnvironment.name == name,
                TestEnvironment.browser == browser,
                TestEnvironment.os == os
            )
        )
        environment = result.scalar_one_or_none()

        if not environment:
            environment = TestEnvironment(
                name=name,
                browser=browser,
                os=os,
                config_metadata=metadata
            )
            session.add(environment)
            await session.flush()

        return environment

    async def export_data(self, output_path: Path, format_type: str = "json", filters: Optional[Dict] = None) -> Dict[str, Any]:
        """Export test data in various formats."""
        rprint(f"📤 Exporting data to [cyan]{output_path}[/cyan] as [yellow]{format_type}[/yellow] format")

        async with get_session() as session:
            if format_type == "json":
                return await self._export_json_data(session, output_path, filters)
            elif format_type == "csv":
                return await self._export_csv_data(session, output_path, filters)
            else:
                raise ValueError(f"Unsupported export format: {format_type}")

    async def _export_json_data(self, session, output_path: Path, filters: Optional[Dict]) -> Dict[str, Any]:
        """Export data in JSON format."""
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        # Build query with filters
        query = select(TestSuite).options(
            selectinload(TestSuite.framework),
            selectinload(TestSuite.environment),
            selectinload(TestSuite.results)
        )

        if filters:
            if 'framework_name' in filters:
                query = query.join(TestFramework).where(TestFramework.name == filters['framework_name'])
            if 'environment_name' in filters:
                query = query.join(TestEnvironment).where(TestEnvironment.name == filters['environment_name'])

        result = await session.execute(query)
        suites = result.scalars().all()

        # Convert to JSON structure
        export_data = {
            "export_info": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "version": "1.0.0",
                "total_suites": len(suites),
                "filters": filters or {}
            },
            "suites": []
        }

        for suite in suites:
            suite_data = {
                "id": str(suite.id),
                "name": suite.name,
                "framework": {
                    "name": suite.framework.name,
                    "version": suite.framework.version,
                    "metadata": suite.framework.config_metadata
                },
                "environment": {
                    "name": suite.environment.name,
                    "browser": suite.environment.browser,
                    "os": suite.environment.os,
                    "metadata": suite.environment.config_metadata
                },
                "stats": {
                    "total_count": suite.total_count,
                    "passed_count": suite.passed_count,
                    "failed_count": suite.failed_count,
                    "skipped_count": suite.skipped_count,
                    "duration_ms": suite.duration_ms
                },
                "metadata": suite.metadata,
                "created_at": suite.created_at.isoformat(),
                "results": []
            }

            for result in suite.results:
                result_data = {
                    "id": str(result.id),
                    "name": result.name,
                    "status": result.status,
                    "duration_ms": result.duration_ms,
                    "full_title": result.full_title,
                    "external_id": result.external_id,
                    "error_message": result.error_message,
                    "tags": result.tags,
                    "metadata": result.metadata,
                    "created_at": result.created_at.isoformat()
                }
                suite_data["results"].append(result_data)

            export_data["suites"].append(suite_data)

        # Write to file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, default=str)

        return {
            "exported_suites": len(suites),
            "exported_results": sum(len(suite.results) for suite in suites),
            "output_file": str(output_path)
        }

    async def _export_csv_data(self, session, output_path: Path, filters: Optional[Dict]) -> Dict[str, Any]:
        """Export data in CSV format."""
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        # Build query
        query = select(TestResult).options(
            selectinload(TestResult.suite).selectinload(TestSuite.framework),
            selectinload(TestResult.suite).selectinload(TestSuite.environment)
        )

        result = await session.execute(query)
        results = result.scalars().all()

        # Write CSV
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # Header
            writer.writerow([
                'suite_name', 'framework_name', 'framework_version',
                'environment_name', 'browser', 'os',
                'test_name', 'status', 'duration_ms', 'error_message',
                'tags', 'external_id', 'created_at'
            ])

            # Data
            for result in results:
                writer.writerow([
                    result.suite.name,
                    result.suite.framework.name,
                    result.suite.framework.version,
                    result.suite.environment.name,
                    result.suite.environment.browser,
                    result.suite.environment.os,
                    result.name,
                    result.status,
                    result.duration_ms,
                    result.error_message or '',
                    ','.join(result.tags) if result.tags else '',
                    result.external_id,
                    result.created_at.isoformat()
                ])

        return {
            "exported_results": len(results),
            "output_file": str(output_path)
        }

    async def validate_data(self) -> Dict[str, Any]:
        """Validate data integrity and consistency."""
        async with get_session() as session:
            from sqlalchemy import func, select

            issues = []
            stats = {}

            # Count records
            frameworks_count = await session.scalar(select(func.count(TestFramework.id)))
            environments_count = await session.scalar(select(func.count(TestEnvironment.id)))
            suites_count = await session.scalar(select(func.count(TestSuite.id)))
            results_count = await session.scalar(select(func.count(TestResult.id)))
            artifacts_count = await session.scalar(select(func.count(TestArtifact.id)))

            stats = {
                "frameworks": frameworks_count,
                "environments": environments_count,
                "suites": suites_count,
                "results": results_count,
                "artifacts": artifacts_count
            }

            # Check for orphaned records
            orphaned_suites = await session.execute(
                select(TestSuite).outerjoin(TestFramework).where(TestFramework.id.is_(None))
            )
            if orphaned_suites.scalars().first():
                issues.append("Found suites with invalid framework references")

            orphaned_results = await session.execute(
                select(TestResult).outerjoin(TestSuite).where(TestSuite.id.is_(None))
            )
            if orphaned_results.scalars().first():
                issues.append("Found results with invalid suite references")

            # Check test count consistency
            inconsistent_suites = await session.execute(
                select(TestSuite).where(
                    TestSuite.total_count !=
                    (TestSuite.passed_count + TestSuite.failed_count + TestSuite.skipped_count)
                )
            )
            if inconsistent_suites.scalars().first():
                issues.append("Found suites with inconsistent test counts")

            return {
                "stats": stats,
                "issues": issues,
                "valid": len(issues) == 0
            }

    async def cleanup_data(self, older_than_days: int = 30, dry_run: bool = True) -> Dict[str, Any]:
        """Clean up old test data."""
        from datetime import timedelta
        from sqlalchemy import select, delete

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=older_than_days)

        async with get_session() as session:
            # Find old suites
            old_suites = await session.execute(
                select(TestSuite).where(TestSuite.created_at < cutoff_date)
            )
            suites_to_delete = old_suites.scalars().all()

            if dry_run:
                return {
                    "dry_run": True,
                    "suites_to_delete": len(suites_to_delete),
                    "cutoff_date": cutoff_date.isoformat()
                }
            else:
                # Delete old data (cascade will handle related records)
                await session.execute(
                    delete(TestSuite).where(TestSuite.created_at < cutoff_date)
                )
                await session.commit()

                return {
                    "dry_run": False,
                    "deleted_suites": len(suites_to_delete),
                    "cutoff_date": cutoff_date.isoformat()
                }


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.pass_context
def data_cli(ctx, verbose):
    """Test Results Data Management CLI.

    Import, export, validate, and manage test results data.
    """
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose

    if verbose:
        structlog.configure(
            wrapper_class=structlog.make_filtering_bound_logger(20),
        )


@data_cli.command('import')
@click.argument('file_path', type=click.Path(exists=True, path_type=Path))
@click.option('--format', '-f', type=click.Choice(['auto', 'json', 'csv', 'playwright', 'cypress']),
              default='auto', help='Input file format')
@click.option('--validate', is_flag=True, help='Validate data before import')
def import_data(file_path, format, validate):
    """Import test data from various formats.

    Examples:
      data import results.json
      data import results.csv --format csv
      data import playwright-results.json --format playwright --validate
    """
    async def _import():
        manager = TestResultsManager()

        if validate:
            rprint("🔍 Validating data before import...")
            validation = await manager.validate_data()
            if not validation["valid"]:
                rprint("⚠️ [yellow]Data validation issues found:[/yellow]")
                for issue in validation["issues"]:
                    rprint(f"   • {issue}")

        try:
            with Progress() as progress:
                task = progress.add_task("Importing data...", total=None)
                stats = await manager.import_data(file_path, format)
                progress.update(task, completed=1, total=1)

            # Display results
            rprint("\n✅ [bold green]Import completed successfully![/bold green]\n")

            table = Table(title="Import Statistics")
            table.add_column("Category", style="cyan")
            table.add_column("Count", style="white", justify="right")

            for category, count in stats.items():
                table.add_row(category.title(), str(count))

            console.print(table)

        except Exception as e:
            rprint(f"❌ [bold red]Import failed:[/bold red] {e}")
            if ctx.obj.get('verbose'):
                raise

    asyncio.run(_import())


@data_cli.command('export')
@click.argument('output_path', type=click.Path(path_type=Path))
@click.option('--format', '-f', type=click.Choice(['json', 'csv']), default='json',
              help='Output file format')
@click.option('--framework', help='Filter by framework name')
@click.option('--environment', help='Filter by environment name')
def export_data(output_path, format, framework, environment):
    """Export test data in various formats.

    Examples:
      data export results.json
      data export results.csv --format csv
      data export filtered.json --framework playwright --environment ci-chrome
    """
    async def _export():
        manager = TestResultsManager()

        filters = {}
        if framework:
            filters['framework_name'] = framework
        if environment:
            filters['environment_name'] = environment

        try:
            with Progress() as progress:
                task = progress.add_task("Exporting data...", total=None)
                result = await manager.export_data(output_path, format, filters)
                progress.update(task, completed=1, total=1)

            rprint("\n✅ [bold green]Export completed successfully![/bold green]\n")
            rprint(f"📁 Output file: [cyan]{result['output_file']}[/cyan]")
            rprint(f"📊 Exported {result.get('exported_suites', 0)} suites")
            rprint(f"📊 Exported {result.get('exported_results', 0)} results")

        except Exception as e:
            rprint(f"❌ [bold red]Export failed:[/bold red] {e}")
            raise

    asyncio.run(_export())


@data_cli.command('validate')
def validate_data():
    """Validate data integrity and consistency."""
    async def _validate():
        manager = TestResultsManager()

        try:
            rprint("🔍 Validating data integrity...")

            with Progress() as progress:
                task = progress.add_task("Running validation...", total=None)
                result = await manager.validate_data()
                progress.update(task, completed=1, total=1)

            # Display statistics
            rprint("\n📊 [bold]Database Statistics:[/bold]\n")

            stats_table = Table()
            stats_table.add_column("Entity", style="cyan")
            stats_table.add_column("Count", style="white", justify="right")

            for entity, count in result["stats"].items():
                stats_table.add_row(entity.title(), str(count))

            console.print(stats_table)

            # Display validation results
            if result["valid"]:
                rprint("\n✅ [bold green]Data validation passed![/bold green]")
                rprint("   No integrity issues found")
            else:
                rprint("\n⚠️ [bold yellow]Data validation issues found:[/bold yellow]")
                for issue in result["issues"]:
                    rprint(f"   • [red]{issue}[/red]")
                rprint("\n💡 Consider running cleanup or manual data fixes")

        except Exception as e:
            rprint(f"❌ [bold red]Validation failed:[/bold red] {e}")
            raise

    asyncio.run(_validate())


@data_cli.command('cleanup')
@click.option('--older-than', '-o', type=int, default=30,
              help='Delete data older than N days')
@click.option('--dry-run', is_flag=True, default=True,
              help='Show what would be deleted without actually deleting')
@click.option('--confirm', is_flag=True, help='Actually perform the deletion')
def cleanup_data(older_than, dry_run, confirm):
    """Clean up old test data.

    Examples:
      data cleanup --older-than 30 --dry-run
      data cleanup --older-than 90 --confirm
    """
    if confirm:
        dry_run = False

    async def _cleanup():
        manager = TestResultsManager()

        if not dry_run and not Confirm.ask(
            f"Are you sure you want to delete data older than {older_than} days?"
        ):
            rprint("❌ Cancelled")
            return

        try:
            rprint(f"🧹 {'Simulating' if dry_run else 'Performing'} cleanup...")

            result = await manager.cleanup_data(older_than, dry_run)

            if result["dry_run"]:
                rprint(f"\n🔍 [bold]Dry Run Results:[/bold]")
                rprint(f"   Suites to delete: {result['suites_to_delete']}")
                rprint(f"   Cutoff date: {result['cutoff_date'][:19]}")
                rprint(f"\n💡 Use --confirm to actually perform the deletion")
            else:
                rprint(f"\n✅ [bold green]Cleanup completed![/bold green]")
                rprint(f"   Deleted suites: {result['deleted_suites']}")
                rprint(f"   Cutoff date: {result['cutoff_date'][:19]}")

        except Exception as e:
            rprint(f"❌ [bold red]Cleanup failed:[/bold red] {e}")
            raise

    asyncio.run(_cleanup())


@data_cli.command('stats')
@click.option('--detailed', is_flag=True, help='Show detailed statistics')
def show_stats(detailed):
    """Show database statistics and insights."""
    async def _stats():
        async with get_session() as session:
            from sqlalchemy import func, select, distinct

            rprint("📊 [bold]Database Statistics[/bold]\n")

            # Basic counts
            frameworks_count = await session.scalar(select(func.count(TestFramework.id)))
            environments_count = await session.scalar(select(func.count(TestEnvironment.id)))
            suites_count = await session.scalar(select(func.count(TestSuite.id)))
            results_count = await session.scalar(select(func.count(TestResult.id)))
            artifacts_count = await session.scalar(select(func.count(TestArtifact.id)))

            # Basic stats table
            basic_table = Table()
            basic_table.add_column("Entity", style="cyan")
            basic_table.add_column("Count", style="white", justify="right")

            basic_table.add_row("Frameworks", str(frameworks_count))
            basic_table.add_row("Environments", str(environments_count))
            basic_table.add_row("Test Suites", str(suites_count))
            basic_table.add_row("Test Results", str(results_count))
            basic_table.add_row("Artifacts", str(artifacts_count))

            console.print(basic_table)

            if detailed:
                # Test status distribution
                rprint("\n📈 [bold]Test Status Distribution[/bold]\n")
                status_stats = await session.execute(
                    select(TestResult.status, func.count(TestResult.id))
                    .group_by(TestResult.status)
                )

                status_table = Table()
                status_table.add_column("Status", style="cyan")
                status_table.add_column("Count", style="white", justify="right")
                status_table.add_column("Percentage", style="yellow", justify="right")

                total_results = results_count
                for status, count in status_stats:
                    percentage = (count / total_results * 100) if total_results > 0 else 0
                    status_table.add_row(status, str(count), f"{percentage:.1f}%")

                console.print(status_table)

                # Framework distribution
                rprint("\n🎭 [bold]Framework Distribution[/bold]\n")
                framework_stats = await session.execute(
                    select(TestFramework.name, func.count(TestSuite.id))
                    .join(TestSuite)
                    .group_by(TestFramework.name)
                )

                framework_table = Table()
                framework_table.add_column("Framework", style="cyan")
                framework_table.add_column("Suites", style="white", justify="right")

                for name, count in framework_stats:
                    framework_table.add_row(name, str(count))

                console.print(framework_table)

    asyncio.run(_stats())


if __name__ == '__main__':
    data_cli()