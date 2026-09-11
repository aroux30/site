#!/usr/bin/env python3
"""Automated Stress Load Test Runner for Iranian E-Commerce Platform.

Executes headless Locust runs, aggregates real-time performance statistics,
evaluates SLA constraints (p95 latency, error rates, throughput),
and generates comprehensive HTML/CSV/JSON certification artifacts.

Usage::

    python load_tests/run_stress_test.py --users 500 --spawn-rate 50 --run-time 30s --headless
    python load_tests/run_stress_test.py --users 10000 --spawn-rate 200 --run-time 3m --headless
"""

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Locust Stress Test Runner")
    parser.add_argument(
        "--host",
        type=str,
        default=os.environ.get("TARGET_HOST", "https://site.arouxpingg.com"),
        help="Target host URL (default: https://site.arouxpingg.com)",
    )
    parser.add_argument(
        "-u", "--users",
        type=int,
        default=100,
        help="Peak concurrent user count (e.g., 500, 1000, 10000)",
    )
    parser.add_argument(
        "-r", "--spawn-rate",
        type=int,
        default=20,
        help="User spawn rate per second",
    )
    parser.add_argument(
        "-t", "--run-time",
        type=str,
        default="30s",
        help="Test execution duration (e.g., 30s, 1m, 3m)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="Run in headless non-interactive mode",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="load_tests/reports",
        help="Directory to store test artifacts and reports",
    )
    parser.add_argument(
        "--assert-sla",
        action="store_true",
        default=False,
        help="Enforce strict SLA thresholds (p95 < 800ms, failures < 1 percent)",
    )
    return parser.parse_args()


def run_locust(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    csv_prefix = output_dir / f"stress_{args.users}u_{int(time.time())}"
    html_report = output_dir / f"report_{args.users}u_{int(time.time())}.html"

    locust_bin = "locust"
    cmd = [
        locust_bin,
        "-f", "load_tests/locustfile.py",
        "-H", args.host,
        "-u", str(args.users),
        "-r", str(args.spawn_rate),
        "--run-time", args.run_time,
        "--csv", str(csv_prefix),
        "--html", str(html_report),
        "--logfile", str(output_dir / "locust_run.log"),
    ]

    if args.headless:
        cmd.append("--headless")

    print("\n" + "=" * 70)
    print("🚀 STARTING LOCUST STRESS LOAD TEST")
    print(f"   Target Host:   {args.host}")
    print(f"   Peak Users:    {args.users:,}")
    print(f"   Spawn Rate:    {args.spawn_rate} users/sec")
    print(f"   Duration:      {args.run_time}")
    print(f"   Artifacts:     {output_dir}")
    print("=" * 70 + "\n", flush=True)

    start_time = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=False, text=True)
        exit_code = proc.returncode
    except Exception as exc:
        print(f"❌ Execution failed: {exc}", file=sys.stderr)
        return 1

    elapsed = round(time.time() - start_time, 1)
    print("\n" + "=" * 70)
    print(f"🏁 TEST COMPLETED in {elapsed}s (Exit Code: {exit_code})")
    print("=" * 70)

    # Process and display summary from generated CSV
    stats_file = Path(f"{csv_prefix}_stats.csv")
    if stats_file.exists():
        parse_and_display_summary(stats_file, html_report, args)
    else:
        print(f"⚠️ Stats file not found at {stats_file}")

    return exit_code


def parse_and_display_summary(
    stats_file: Path,
    html_report: Path,
    args: argparse.Namespace,
) -> None:
    """Read Locust CSV output, print summary table, and verify SLA."""
    total_requests = 0
    total_failures = 0
    endpoints = []

    try:
        with open(stats_file, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("Name", "")
                method = row.get("Type", "")
                req_count = int(row.get("Request Count", 0) or 0)
                fail_count = int(row.get("Failure Count", 0) or 0)
                med_ms = float(row.get("Median Response Time", 0) or 0)
                p95_ms = float(row.get("95%", 0) or row.get("95% Line", 0) or 0)
                p99_ms = float(row.get("99%", 0) or row.get("99% Line", 0) or 0)
                avg_ms = float(row.get("Average Response Time", 0) or 0)
                rps = float(row.get("Requests/s", 0) or 0)

                if name == "Aggregated":
                    total_requests = req_count
                    total_failures = fail_count
                    agg_med = med_ms
                    agg_p95 = p95_ms
                    agg_p99 = p99_ms
                    agg_avg = avg_ms
                    agg_rps = rps
                else:
                    endpoints.append({
                        "method": method,
                        "name": name,
                        "count": req_count,
                        "fails": fail_count,
                        "avg_ms": avg_ms,
                        "p95_ms": p95_ms,
                        "p99_ms": p99_ms,
                        "rps": rps,
                    })

        fail_rate = (total_failures / total_requests * 100) if total_requests > 0 else 0.0

        print("\n📊 DETAILED ENDPOINT PERFORMANCE BREAKDOWN:")
        print("-" * 88)
        print(f"{'Method':<6} | {'Endpoint':<36} | {'Reqs':>6} | {'Fails':>5} | {'Avg(ms)':>8} | {'p95(ms)':>8} | {'RPS':>6}")
        print("-" * 88)
        for ep in endpoints:
            print(
                f"{ep['method']:<6} | {ep['name']:<36} | {ep['count']:>6} | "
                f"{ep['fails']:>5} | {ep['avg_ms']:>8.1f} | {ep['p95_ms']:>8.1f} | {ep['rps']:>6.1f}"
            )
        print("-" * 88)

        print("\n📈 AGGREGATED BENCHMARK METRICS:")
        print(f"   • Total Requests Executed: {total_requests:,}")
        print(f"   • Total Failures / Drops:  {total_failures:,} ({fail_rate:.2f}%)")
        print(f"   • Average Latency:         {agg_avg:.1f} ms")
        print(f"   • Median (p50) Latency:    {agg_med:.1f} ms")
        print(f"   • 95th Percentile (p95):   {agg_p95:.1f} ms")
        print(f"   • 99th Percentile (p99):   {agg_p99:.1f} ms")
        print(f"   • Throughput (RPS):        {agg_rps:.1f} req/sec")
        print(f"   • HTML Report Generated:   {html_report}")

        # Summary JSON artifact for CI/CD ingestion
        json_summary = {
            "timestamp": time.time(),
            "target_host": args.host,
            "simulated_users": args.users,
            "duration": args.run_time,
            "total_requests": total_requests,
            "total_failures": total_failures,
            "failure_rate_pct": round(fail_rate, 3),
            "latency_p50_ms": agg_med,
            "latency_p95_ms": agg_p95,
            "latency_p99_ms": agg_p99,
            "throughput_rps": agg_rps,
        }
        json_path = stats_file.with_suffix(".json")
        with open(json_path, "w", encoding="utf-8") as jf:
            json.dump(json_summary, jf, indent=2)
        print(f"   • JSON Summary Stored:     {json_path}")

        if args.assert_sla:
            if fail_rate > 1.0:
                print(f"❌ SLA VIOLATION: Failure rate {fail_rate:.2f}% exceeds limit (1.0%)", file=sys.stderr)
                sys.exit(1)
            if agg_p95 > 800.0:
                print(f"❌ SLA VIOLATION: p95 latency {agg_p95:.1f}ms exceeds limit (800ms)", file=sys.stderr)
                sys.exit(1)
            print("✅ ALL PERFORMANCE SLAs SATISFIED!")

    except Exception as exc:
        print(f"⚠️ Error parsing CSV report: {exc}", file=sys.stderr)


if __name__ == "__main__":
    cli_args = parse_arguments()
    sys.exit(run_locust(cli_args))
