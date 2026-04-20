"""
reddit_poster.py
----------------
RedditPostAgent

Given a list of generated Reddit replies, uses the PRAW wrapper
to authenticate into a Reddit account and automatically post the replies
on the parent posts. Includes random sleep intervals to mimic human
behavior and avoid automated shadowbans.
"""

import logging
import os
import time
import random
from typing import List, Dict, Any

try:
    import praw
except ImportError:
    praw = None

logger = logging.getLogger(__name__)

class RedditPostAgent:
    """
    Automates the posting of generated replies to Reddit.
    Requires REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME,
    and REDDIT_PASSWORD to be set in the environment.
    """

    def __init__(self):
        self.client_id = os.getenv("REDDIT_CLIENT_ID")
        self.client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        self.username = os.getenv("REDDIT_USERNAME")
        self.password = os.getenv("REDDIT_PASSWORD")
        
        if praw is None:
            logger.warning("PRAW library is not installed. Run `pip install praw`. Cannot post.")
            self.reddit = None
            self.can_post = False
            return

        if all([self.client_id, self.client_secret, self.username, self.password]):
            # Set up the Reddit bot instance
            self.reddit = praw.Reddit(
                client_id=self.client_id,
                client_secret=self.client_secret,
                user_agent=f"windows:CWT_Agent:v1.0 (by u/{self.username})",
                username=self.username,
                password=self.password
            )
            self.can_post = True
            logger.info(f"RedditPostAgent initialized successfully for user u/{self.username}.")
        else:
            logger.warning("Reddit API credentials missing in .env. Running in dry-run mode (no actual posting).")
            self.reddit = None
            self.can_post = False

    def run(self, replies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Takes the drafted replies and attempts to post them via Reddit API.
        Adds random delays between posts to prevent spam-blocking.
        """
        if not self.can_post:
            logger.info("Auto-posting is disabled. Returning drafts as-is.")
            for r in replies:
                r["posted_successfully"] = False
            return replies

        logger.info(f"RedditPostAgent attempting to publish {len(replies)} replies...")
        
        for i, reply in enumerate(replies):
            url = reply.get("url", "")
            text = reply.get("reply_text", "")
            
            if not url or "reddit.com" not in url:
                logger.warning(f"Invalid Reddit URL skipped: {url}")
                reply["posted_successfully"] = False
                continue

            try:
                # 1. Get the submission by URL
                logger.info(f"Posting to target URL: {url}")
                submission = self.reddit.submission(url=url)
                
                # 2. Reply to the post
                comment = submission.reply(text)
                
                # 3. Store the live permalink of the new comment
                reply["live_url"] = f"https://www.reddit.com{comment.permalink}"
                reply["posted_successfully"] = True
                logger.info(f"✅ Successfully posted! Live URL: {reply['live_url']}")
                
                # 4. Human-like delay between posts to prevent immediate ban (30s - 90s)
                # Ensure we don't delay after the very last post
                if i < len(replies) - 1:
                    sleep_time = random.randint(30, 90)
                    logger.info(f"Sleeping for {sleep_time} seconds to simulate human activity and avoid rate limits...")
                    time.sleep(sleep_time)

            except Exception as e:
                logger.error(f"Failed to post to {url}. Error: {e}")
                reply["posted_successfully"] = False

        return replies
