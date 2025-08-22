#!/usr/bin/env python3
"""Debug script to test why tracks aren't being fetched from MusicBrainz."""

import httpx
import asyncio
import json
from pprint import pprint

MUSICBRAINZ_BASE_URL = "https://musicbrainz.org/ws/2"


async def test_musicbrainz_search(upc):
    """Test MusicBrainz API search by barcode."""
    print(f"\n{'='*60}")
    print(f"Testing MusicBrainz search for UPC: {upc}")
    print("=" * 60)

    # First, search for the release
    search_url = f"{MUSICBRAINZ_BASE_URL}/release"
    search_params = {
        "query": f"barcode:{upc}",
        "fmt": "json",
        "inc": "artists+labels+recordings+release-groups+media+discids",
    }

    headers = {
        "User-Agent": "draftmaker/1.0 ( benjaminabramowitz@gmail.com )",
        "Accept": "application/json",
    }

    async with httpx.AsyncClient() as client:
        print("\n1. SEARCH QUERY:")
        print(f"   URL: {search_url}")
        print(f"   Query: barcode:{upc}")

        response = await client.get(
            search_url, params=search_params, headers=headers, timeout=30.0
        )

        if response.status_code == 200:
            data = response.json()

            if data.get("releases") and len(data["releases"]) > 0:
                release = data["releases"][0]
                mbid = release.get("id")

                print(f"\n2. SEARCH RESULTS:")
                print(f"   Found release: {release.get('title')}")
                print(f"   MBID: {mbid}")
                print(f"   Media count: {len(release.get('media', []))}")

                # Check if tracks are in search results
                if release.get("media"):
                    for i, medium in enumerate(release["media"]):
                        tracks = medium.get("tracks", [])
                        track_count = medium.get("track-count", 0)
                        print(
                            f"   Medium {i+1}: {len(tracks)} tracks returned, {track_count} total tracks"
                        )
                        if tracks:
                            print(f"     First track: {tracks[0].get('title', 'N/A')}")

                # Now fetch the full release details using MBID
                if mbid and not release.get("media", [{}])[0].get("tracks"):
                    print("\n3. FETCHING FULL RELEASE (tracks not in search results):")
                    await asyncio.sleep(1.1)  # Rate limit

                    release_url = f"{MUSICBRAINZ_BASE_URL}/release/{mbid}"
                    release_params = {
                        "fmt": "json",
                        "inc": "artists+labels+recordings+release-groups+media+discids",
                    }

                    response2 = await client.get(
                        release_url,
                        params=release_params,
                        headers=headers,
                        timeout=30.0,
                    )

                    if response2.status_code == 200:
                        full_release = response2.json()

                        print(f"   Full release fetched: {full_release.get('title')}")
                        print(f"   Media count: {len(full_release.get('media', []))}")

                        if full_release.get("media"):
                            total_tracks = 0
                            for i, medium in enumerate(full_release["media"]):
                                tracks = medium.get("tracks", [])
                                total_tracks += len(tracks)
                                print(f"   Medium {i+1}: {len(tracks)} tracks")
                                if tracks and len(tracks) > 0:
                                    for j, track in enumerate(
                                        tracks[:3]
                                    ):  # Show first 3
                                        print(
                                            f"     Track {j+1}: {track.get('title', 'N/A')}"
                                        )
                                    if len(tracks) > 3:
                                        print(
                                            f"     ... and {len(tracks) - 3} more tracks"
                                        )

                            print(f"\n   TOTAL TRACKS: {total_tracks}")

                            if total_tracks == 0:
                                print(
                                    "\n   ⚠️ PROBLEM: Media exists but no tracks returned!"
                                )
                                print(
                                    "   This means we need to fetch recordings separately!"
                                )
            else:
                print("   No releases found")


# Test UPCs
test_upcs = [
    "016581720824",  # From the batch
    "075596200820",  # From the batch
    "077779847921",  # From earlier test
]


async def main():
    for upc in test_upcs:
        await test_musicbrainz_search(upc)
        await asyncio.sleep(1.5)  # Rate limiting between tests


if __name__ == "__main__":
    asyncio.run(main())
