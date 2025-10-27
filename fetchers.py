"""
Contest fetchers for different platforms
"""

import asyncio
import aiohttp
from datetime import datetime, timezone
from config import CODEFORCES_API_URL, LEETCODE_API_URL, CODECHEF_API_URL


class ContestFetcher:
    """Fetches contests from various platforms"""

    @staticmethod
    async def fetch_codeforces():
        """Fetch contests from Codeforces"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(CODEFORCES_API_URL) as response:
                    data = await response.json()

                    if data['status'] != 'OK':
                        return []

                    contests = []
                    for contest in data['result']:
                        if contest['phase'] == 'BEFORE':
                            # UTC timestamp from Codeforces
                            start_time = datetime.fromtimestamp(
                                contest['startTimeSeconds'],
                                tz=timezone.utc
                            )

                            contests.append({
                                'id': f"codeforces_{contest['id']}",
                                'platform': 'Codeforces',
                                'title': contest['name'],
                                'start_time': start_time.isoformat(),
                                'duration_seconds': contest['durationSeconds'],
                                'url': f"https://codeforces.com/contest/{contest['id']}"
                            })

                    return contests
        except Exception as e:
            print(f"Error fetching Codeforces contests: {e}")
            return []

    @staticmethod
    async def fetch_leetcode():
        """Fetch contests from LeetCode (GraphQL API)"""
        query = """
        query {
            allContests {
                title
                titleSlug
                startTime
                duration
            }
        }
        """

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    LEETCODE_API_URL,
                    json={'query': query}
                ) as response:
                    data = await response.json()

                    contests = []
                    current_time = datetime.now(timezone.utc)

                    for contest in data.get('data', {}).get('allContests', []):
                        # UTC timestamp from LeetCode
                        start_time = datetime.fromtimestamp(
                            contest['startTime'],
                            tz=timezone.utc
                        )

                        if start_time > current_time:
                            contests.append({
                                'id': f"leetcode_{contest['titleSlug']}",
                                'platform': 'LeetCode',
                                'title': contest['title'],
                                'start_time': start_time.isoformat(),
                                'duration_seconds': contest['duration'],
                                'url': f"https://leetcode.com/contest/{contest['titleSlug']}"
                            })

                    return contests
        except Exception as e:
            print(f"Error fetching LeetCode contests: {e}")
            return []

    @staticmethod
    async def fetch_codechef():
        """Fetch contests from CodeChef (API v3)"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(CODECHEF_API_URL) as response:
                    data = await response.json()

                    # Debug: Print the response status
                    print(f"CodeChef API Status: {data.get('status')}")
                    print(f"Future contests count: {len(data.get('future_contests', []))}")

                    if data.get('status') != 'success':
                        print(f"CodeChef API returned non-success status: {data.get('status')}")
                        return []

                    contests = []

                    # Process future contests
                    for contest in data.get('future_contests', []):
                        try:
                            # Parse ISO format datetime (includes IST timezone +05:30)
                            start_time = datetime.fromisoformat(
                                contest['contest_start_date_iso']
                            )

                            # Convert to UTC
                            start_time_utc = start_time.astimezone(timezone.utc)

                            # Debug: Print each contest
                            print(f"Processing: {contest['contest_name']} - Start: {start_time_utc}")

                            # Duration is in minutes, convert to seconds
                            duration_seconds = int(contest['contest_duration']) * 60

                            contests.append({
                                'id': f"codechef_{contest['contest_code']}",
                                'platform': 'CodeChef',
                                'title': contest['contest_name'],
                                'start_time': start_time_utc.isoformat(),
                                'duration_seconds': duration_seconds,
                                'url': f"https://www.codechef.com/{contest['contest_code']}"
                            })
                        except Exception as e:
                            print(f"Error processing CodeChef contest {contest.get('contest_code')}: {e}")
                            continue

                    print(f"Total CodeChef contests added: {len(contests)}")
                    return contests

        except Exception as e:
            print(f"Error fetching CodeChef contests: {e}")
            import traceback
            traceback.print_exc()
            return []

    @staticmethod
    async def fetch_all():
        """Fetch from all platforms"""
        results = await asyncio.gather(
            ContestFetcher.fetch_codeforces(),
            ContestFetcher.fetch_leetcode(),
            ContestFetcher.fetch_codechef(),
            return_exceptions=True
        )

        all_contests = []
        for result in results:
            if isinstance(result, list):
                all_contests.extend(result)

        return all_contests