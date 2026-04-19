"""
apify_client.py
---------------
Wrapper around the Apify REST API for running actors and retrieving datasets.

Actors used
-----------
- Reddit scraper : `trudax/reddit-scraper-lite`  (free, no credit card)

For reference: https://docs.apify.com/api/v2
"""

import os
import time
import logging
import requests
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

APIFY_BASE_URL = "https://api.apify.com/v2"

# Actor IDs (Apify store slugs)
REDDIT_SCRAPER_ACTOR = "trudax/reddit-scraper-lite"


class ApifyClient:
    """
    Minimal Apify client for actor runs and dataset retrieval.

    Parameters
    ----------
    api_token : str, optional
        Apify API token. Falls back to APIFY_API_TOKEN env var.
    poll_interval : int
        Seconds between status-poll calls while waiting for actor to finish.
    timeout : int
        Max seconds to wait for actor completion before giving up.
    """

    def __init__(
        self,
        api_token: Optional[str] = None,
        poll_interval: int = 5,
        timeout: int = 300,
    ):
        self.api_token = api_token or os.getenv("APIFY_API_TOKEN", "")
        if not self.api_token:
            raise ValueError(
                "Apify API token not found. "
                "Set APIFY_API_TOKEN environment variable or pass api_token."
            )
        self.poll_interval = poll_interval
        self.timeout = timeout
        logger.info("ApifyClient initialised.")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_token}",
        }

    def _run_actor(self, actor_id: str, input_data: Dict[str, Any]) -> str:
        """
        Start an actor run and return the run ID.
        """
        url = f"{APIFY_BASE_URL}/acts/{actor_id}/runs"
        logger.info("Starting Apify actor: %s", actor_id)
        response = requests.post(
            url,
            headers=self._headers(),
            json=input_data,
            timeout=30,
        )
        response.raise_for_status()
        run_id = response.json()["data"]["id"]
        logger.info("Actor run started. Run ID: %s", run_id)
        return run_id

    def _wait_for_run(self, run_id: str) -> str:
        """
        Poll until the run reaches a terminal status.
        Returns the default dataset ID.
        """
        url = f"{APIFY_BASE_URL}/actor-runs/{run_id}"
        elapsed = 0
        while elapsed < self.timeout:
            response = requests.get(url, headers=self._headers(), timeout=30)
            response.raise_for_status()
            data = response.json()["data"]
            status = data["status"]
            logger.debug("Actor run %s status: %s", run_id, status)
            if status == "SUCCEEDED":
                dataset_id = data["defaultDatasetId"]
                logger.info("Actor succeeded. Dataset ID: %s", dataset_id)
                return dataset_id
            if status in ("FAILED", "ABORTED", "TIMED-OUT"):
                raise RuntimeError(f"Actor run {run_id} ended with status: {status}")
            time.sleep(self.poll_interval)
            elapsed += self.poll_interval
        raise TimeoutError(f"Actor run {run_id} did not finish within {self.timeout}s")

    def _get_dataset_items(
        self, dataset_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Download items from a dataset.
        """
        url = f"{APIFY_BASE_URL}/datasets/{dataset_id}/items"
        params = {"limit": limit, "clean": "true"}
        response = requests.get(
            url, headers=self._headers(), params=params, timeout=30
        )
        response.raise_for_status()
        items = response.json()
        logger.info("Retrieved %d items from dataset %s", len(items), dataset_id)
        return items

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scrape_reddit(
        self,
        search_queries: List[str],
        posts_per_query: int = 10,
        include_comments: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Scrape Reddit posts matching the given search queries.

        Parameters
        ----------
        search_queries : list[str]
            Search terms to run.
        posts_per_query : int
            Number of posts to fetch per query.
        include_comments : bool
            Whether to include top-level comments in the result.

        Returns
        -------
        list[dict]  – raw Reddit post/comment objects from Apify
        """
        all_results: List[Dict[str, Any]] = []

        for query in search_queries:
            logger.info("Scraping Reddit for query: '%s'", query)
            actor_input = {
                "searches": [query],
                "type": "posts",
                "sort": "relevance",
                "time": "year",
                "maxItems": posts_per_query,
                "maxCommentsPerPost": 5 if include_comments else 0,
                "proxy": {
                    "useApifyProxy": True,
                    "apifyProxyGroups": ["RESIDENTIAL"],
                },
            }
            try:
                run_id = self._run_actor(REDDIT_SCRAPER_ACTOR, actor_input)
                dataset_id = self._wait_for_run(run_id)
                items = self._get_dataset_items(dataset_id, limit=posts_per_query * 3)
                all_results.extend(items)
                logger.info(
                    "Query '%s' returned %d items (total so far: %d)",
                    query,
                    len(items),
                    len(all_results),
                )
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("Error scraping query '%s': %s", query, exc)
                # Continue with remaining queries instead of failing hard

        return all_results
