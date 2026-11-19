"""Measures API response times against a running server.

Usage:  python scripts/benchmark.py [base_url]
The server must be started first (uvicorn app.main:app --port 8000) and seeded.
Each endpoint is called once after a restart-free warm-up and then 5 more times;
the median and the slowest of the 5 timed calls are reported.
"""
import json
import statistics
import sys
import time
from pathlib import Path

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8000'
RUNS = 5

ENDPOINTS = [
    ('Dashboard summary', '/api/analytics/summary'),
    ('Monthly trend (top 6)', '/api/analytics/trend'),
    ('Breakdown by residence', '/api/analytics/breakdown?by=residence'),
    ('Seasonality (malaria)', '/api/analytics/seasonality?code=B54'),
    ('Association rules (Apriori)', '/api/mining/rules'),
    ('Clustering of halls (k-means)', '/api/mining/clusters'),
    ('Forecast with back-test (malaria)', '/api/mining/forecast?code=B54&horizon=6'),
    ('Outbreak scan, campus, 26 weeks', '/api/mining/alerts?method=historical&level=campus&weeks=26'),
    ('Outbreak scan, halls, 26 weeks', '/api/mining/alerts?method=historical&level=residence&weeks=26'),
    ('Encounter list (page of 25)', '/api/data/encounters?page=1&size=25'),
]


def main():
    with httpx.Client(base_url=BASE, timeout=120) as c:
        tok = c.post('/api/auth/login', json={'username': 'analyst', 'password': 'Analyst@123'}).json()['token']
        h = {'Authorization': f'Bearer {tok}'}
        rows = []
        for name, path in ENDPOINTS:
            t0 = time.perf_counter(); r = c.get(path, headers=h); first = (time.perf_counter() - t0) * 1000
            r.raise_for_status()
            times = []
            for _ in range(RUNS):
                t0 = time.perf_counter(); c.get(path, headers=h).raise_for_status(); times.append((time.perf_counter() - t0) * 1000)
            rows.append({'endpoint': name, 'path': path, 'first_ms': round(first), 'median_ms': round(statistics.median(times)),
                         'max_ms': round(max(times)), 'bytes': len(r.content)})
            print(f"{name:38s} first {first:8.0f} ms   median {statistics.median(times):7.0f} ms   max {max(times):7.0f} ms")
    out = Path(__file__).resolve().parents[1] / 'data' / 'benchmark_results.json'
    out.write_text(json.dumps({'base_url': BASE, 'runs': RUNS, 'results': rows}, indent=2))
    print('saved', out)


if __name__ == '__main__':
    main()
