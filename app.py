#!/usr/bin/env python3
"""
Cast AI Value Realization Report to CSV Exporter

This script fetches cluster data and value realization reports from Cast AI API
and exports the results to a CSV file.

Usage:
    python castai_value_realization_to_csv.py --start-month 2025-01 --end-month 2025-12 \
        --org-id <org_id> --api-key <api_key>

    Or set environment variables:
    export CASTAI_ORG_ID=<org_id>
    export CASTAI_API_KEY=<api_key>
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Any
import requests
from urllib.parse import quote


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Export Cast AI Value Realization Report to CSV'
    )
    parser.add_argument(
        '--start-month',
        required=True,
        help='Start month in YYYY-MM format (e.g., 2025-01)'
    )
    parser.add_argument(
        '--end-month',
        required=True,
        help='End month in YYYY-MM format (e.g., 2025-12)'
    )
    parser.add_argument(
        '--org-id',
        default=os.getenv('CASTAI_ORG_ID'),
        help='Cast AI Organization ID (or set CASTAI_ORG_ID env var)'
    )
    parser.add_argument(
        '--api-key',
        default=os.getenv('CASTAI_API_KEY'),
        help='Cast AI API Key (or set CASTAI_API_KEY env var)'
    )
    parser.add_argument(
        '--output',
        default='value_realization_report.csv',
        help='Output CSV file path (default: value_realization_report.csv)'
    )

    args = parser.parse_args()

    # Validate required arguments
    if not args.org_id:
        parser.error('--org-id is required (or set CASTAI_ORG_ID environment variable)')
    if not args.api_key:
        parser.error('--api-key is required (or set CASTAI_API_KEY environment variable)')

    return args


def validate_date_format(date_str: str, param_name: str) -> str:
    """Validate and convert date string to ISO format."""
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m')
        # Set to first day of month at midnight UTC
        return date_obj.strftime('%Y-%m-01T00:00:00.000000000Z')
    except ValueError:
        print(f"Error: {param_name} must be in YYYY-MM format (e.g., 2025-01)")
        sys.exit(1)


def get_cluster_ids(start_time: str, end_time: str, api_key: str) -> List[str]:
    """
    Fetch all cluster IDs from Cast AI cost reports API.

    Args:
        start_time: Start time in ISO format
        end_time: End time in ISO format
        api_key: Cast AI API key

    Returns:
        List of cluster IDs
    """
    url = 'https://api.cast.ai/v1/cost-reports/organization/clusters/report'

    params = {
        'startTime': start_time,
        'endTime': end_time
    }

    headers = {
        'X-API-Key': api_key,
        'accept': 'application/json'
    }

    print(f"Fetching cluster IDs from {url}...")

    try:
        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()

        data = response.json()

        # Extract cluster IDs and names
        clusters = []
        if 'items' in data:
            for item in data['items']:
                cluster_id = item.get('clusterId')
                cluster_name = item.get('clusterName', 'Unknown')
                if cluster_id:
                    clusters.append({
                        'id': cluster_id,
                        'name': cluster_name
                    })
                    print(f"  Found cluster: {cluster_name} ({cluster_id})")

        cluster_ids = [c['id'] for c in clusters]

        if not cluster_ids:
            print("Warning: No clusters found in the response")
            return []

        print(f"Found {len(cluster_ids)} cluster(s)")
        return cluster_ids

    except requests.exceptions.RequestException as e:
        print(f"Error fetching cluster IDs: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response body: {e.response.text}")
        sys.exit(1)


def get_value_realization_report(
    org_id: str,
    cluster_ids: List[str],
    start_time: str,
    end_time: str,
    api_key: str
) -> Dict[str, Any]:
    """
    Fetch value realization timeline report from Cast AI API.

    Args:
        org_id: Organization ID
        cluster_ids: List of cluster IDs
        start_time: Start time in ISO format
        end_time: End time in ISO format
        api_key: Cast AI API key

    Returns:
        JSON response as dictionary
    """
    url = f'https://api.cast.ai/reporting/v1beta/organizations/{org_id}:runValueRealizationTimelineReport'

    params = {
        'startTime': start_time,
        'endTime': end_time,
        'step': 'ONE_MONTH'
    }

    headers = {
        'accept': 'application/json',
        'X-API-Key': api_key,
        'Content-Type': 'application/json'
    }

    payload = {
        'clusterIds': cluster_ids
    }

    print(f"\nFetching value realization report...")
    print(f"  Organization ID: {org_id}")
    print(f"  Cluster IDs: {len(cluster_ids)} clusters")
    print(f"  Time range: {start_time} to {end_time}")

    try:
        response = requests.post(
            url,
            params=params,
            headers=headers,
            json=payload,
            timeout=60
        )
        response.raise_for_status()

        data = response.json()
        print("Successfully fetched value realization report")
        return data

    except requests.exceptions.RequestException as e:
        print(f"Error fetching value realization report: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response body: {e.response.text}")
        sys.exit(1)


def convert_to_csv(data: Dict[str, Any], output_file: str):
    """
    Convert value realization report JSON to CSV format.

    Args:
        data: JSON response data
        output_file: Output CSV file path
    """
    if 'timelineItems' not in data:
        print("Error: No timelineItems found in response")
        sys.exit(1)

    # Define CSV columns
    fieldnames = [
        'time_frame',
        'actualCost',
        'projectedCost',
        'autoscalerSavings',
        'workloadAutoscalerSavings',
        'total_savings',
        'cpu_actualCost',
        'cpu_projectedCost',
        'cpu_provisionedCoresHourly',
        'cpu_projectedCoresHourly',
        'cpu_requestedCoresHourly',
        'cpu_provisionedCoreHours',
        'cpu_projectedCoreHours',
        'cpu_requestedCoreHours',
        'memory_actualCost',
        'memory_projectedCost',
        'memory_provisionedBytesHourly',
        'memory_projectedBytesHourly',
        'memory_requestedBytesHourly',
        'memory_provisionedByteHours',
        'memory_projectedByteHours',
        'memory_requestedByteHours'
    ]

    print(f"\nWriting data to {output_file}...")

    try:
        with open(output_file, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for item in data['timelineItems']:
                # Extract timestamp and convert to YYYY-MM format
                timestamp = item.get('timestamp', '')
                time_frame = datetime.fromisoformat(
                    timestamp.replace('Z', '+00:00')
                ).strftime('%Y-%m')

                # Extract cost data
                cost = item.get('cost', {})
                actual_cost = cost.get('actualCost', 0)
                projected_cost = cost.get('projectedCost', 0)

                # Calculate total savings
                total_savings = projected_cost - actual_cost

                # Extract CPU data
                cpu = item.get('cpu', {})

                # Extract memory data
                memory = item.get('memory', {})

                # Build row
                row = {
                    'time_frame': time_frame,
                    'actualCost': actual_cost,
                    'projectedCost': projected_cost,
                    'autoscalerSavings': cost.get('autoscalerSavings', 0),
                    'workloadAutoscalerSavings': cost.get('workloadAutoscalerSavings', 0),
                    'total_savings': total_savings,
                    'cpu_actualCost': cpu.get('actualCost', 0),
                    'cpu_projectedCost': cpu.get('projectedCost', 0),
                    'cpu_provisionedCoresHourly': cpu.get('provisionedCoresHourly', 0),
                    'cpu_projectedCoresHourly': cpu.get('projectedCoresHourly', 0),
                    'cpu_requestedCoresHourly': cpu.get('requestedCoresHourly', 0),
                    'cpu_provisionedCoreHours': cpu.get('provisionedCoreHours', 0),
                    'cpu_projectedCoreHours': cpu.get('projectedCoreHours', 0),
                    'cpu_requestedCoreHours': cpu.get('requestedCoreHours', 0),
                    'memory_actualCost': memory.get('actualCost', 0),
                    'memory_projectedCost': memory.get('projectedCost', 0),
                    'memory_provisionedBytesHourly': memory.get('provisionedBytesHourly', 0),
                    'memory_projectedBytesHourly': memory.get('projectedBytesHourly', 0),
                    'memory_requestedBytesHourly': memory.get('requestedBytesHourly', 0),
                    'memory_provisionedByteHours': memory.get('provisionedByteHours', 0),
                    'memory_projectedByteHours': memory.get('projectedByteHours', 0),
                    'memory_requestedByteHours': memory.get('requestedByteHours', 0)
                }

                writer.writerow(row)
                print(f"  Written: {time_frame} - Savings: ${total_savings:,.2f}")

        print(f"\nSuccess! CSV file created: {output_file}")
        print(f"Total rows: {len(data['timelineItems'])}")

    except IOError as e:
        print(f"Error writing CSV file: {e}")
        sys.exit(1)


def main():
    """Main execution function."""
    print("=" * 70)
    print("Cast AI Value Realization Report to CSV Exporter")
    print("=" * 70)

    # Parse arguments
    args = parse_arguments()

    # Validate and convert dates
    start_time = validate_date_format(args.start_month, '--start-month')
    end_time = validate_date_format(args.end_month, '--end-month')

    # For the end month, we want the last day of the month
    # Convert end_time to end of month
    end_date = datetime.strptime(args.end_month, '%Y-%m')
    # Move to next month and subtract one day to get last day of current month
    if end_date.month == 12:
        next_month = end_date.replace(year=end_date.year + 1, month=1, day=1)
    else:
        next_month = end_date.replace(month=end_date.month + 1, day=1)

    end_time = next_month.strftime('%Y-%m-01T00:00:00.000000000Z')

    # Step 1: Get cluster IDs
    cluster_ids = get_cluster_ids(start_time, end_time, args.api_key)

    if not cluster_ids:
        print("No clusters found. Exiting.")
        sys.exit(1)

    # Step 2: Get value realization report
    report_data = get_value_realization_report(
        args.org_id,
        cluster_ids,
        start_time,
        end_time,
        args.api_key
    )

    # Step 3: Convert to CSV
    convert_to_csv(report_data, args.output)

    print("\n" + "=" * 70)
    print("Process completed successfully!")
    print("=" * 70)


if __name__ == '__main__':
    main()
