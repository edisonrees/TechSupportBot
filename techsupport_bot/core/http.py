"""
Defines the wrapper around HTTP calling allow true async, caching, and rate limiting
This has no commands
"""

from __future__ import annotations

import time
import urllib
from collections import deque
from json import JSONDecodeError
from typing import TYPE_CHECKING, Any, Self
from urllib.parse import urlparse

import aiohttp
import expiringdict
import munch
from botlogging import LogLevel
from core import custom_errors

if TYPE_CHECKING:
    import bot


class HTTPCalls:
    """
    This requires a class so it can store the bot variable upon setup
    This allows access to the config file and logging

    Args:
        bot (bot.TechSupportBot): The bot object that will be making http calls.
            This is only used for access to file_config and nothing more
    """

    def __init__(self: Self, bot: bot.TechSupportBot) -> None:
        self.bot = bot
        self.http_cache = expiringdict.ExpiringDict(
            max_len=self.bot.file_config.cache.http_cache_length,
            max_age_seconds=self.bot.file_config.cache.http_cache_seconds,
        )
        self.url_rate_limit_history = {}
        # Rate limit configurations for each root URL
        # This is "URL": (calls, seconds)
        self.rate_limits = {
            "api.urbandictionary.com": (2, 60),
            "api.openai.com": (3, 60),
            "www.googleapis.com": (5, 60),
            "ipinfo.io": (1, 30),
            "api.open-notify.org": (1, 60),
            "geocode.xyz": (1, 60),
            "v2.jokeapi.dev": (10, 60),
            "api.kanye.rest": (1, 60),
            "newsapi.org": (1, 30),
            "accounts.spotify.com": (3, 60),
            "api.spotify.com": (3, 60),
            "api.mymemory.translated.net": (1, 60),
            "api.openweathermap.org": (3, 60),
            "api.wolframalpha.com": (3, 60),
            "xkcd.com": (5, 60),
            "api.github.com": (3, 60),
            "api.giphy.com": (3, 60),
            "strawpoll.com": (3, 60),
            "api.thecatapi.com": (10, 60),
            "dog.ceo": (10, 60),
            "frogs.media": (3, 60),
            "randomfox.ca": (4, 60),
        }
        # For the variable APIs, if they don't exist, don't rate limit them
        try:
            self.rate_limits[
                urlparse(self.bot.file_config.api.api_url.dumpdbg).netloc
            ] = (
                1,
                60,
            )
        except AttributeError:
            print("No dumpdbg API URL found. Not rate limiting dumpdbg")
        try:
            self.rate_limits[urlparse(self.bot.file_config.api.api_url.linx).netloc] = (
                20,
                60,
            )
        except AttributeError:
            print("No linx API URL found. Not rate limiting linx")

    async def http_call(
        self: Self, method: str, url: str, *args: tuple, **kwargs: dict[str, Any]
    ) -> munch.Munch:
        """Makes an HTTP request.

        By default this returns JSON/dict with the status code injected.
        use_cache (bool):  True if the GET result should be grabbed from cache
        get_raw_response (bool): True if the actual response object should be returned

        Args:
            method (str): the HTTP method to use
            url (str): the URL to call
            *args (tuple): Used to allow any combination of parameters to the API
            **kwargs (dict[str, Any]): Used to allow any combination of parameters to the API

        Raises:
            HTTPRateLimit: Raised if the API is currently on cooldown
            HTTPRateLimitAppCommand: Raised if the API is currently on cooldown

        Returns:
            munch.Munch: The munch object containing the response from the API
        """

        # Get the URL not the endpoint being called
        use_app_error = kwargs.pop("use_app_error", False)
        ignore_rate_limit = False
        root_url = urlparse(url).netloc

        # If the URL is not rate limited, we assume it can be executed an unlimited amount of times
        if root_url in self.rate_limits:
            executions_allowed, time_window = self.rate_limits[root_url]

            now = time.time()

            # If the URL being called is not in the history, add it
            # A deque allows easy max limit length
            if root_url not in self.url_rate_limit_history:
                self.url_rate_limit_history[root_url] = deque(
                    [], maxlen=executions_allowed
                )

            # Determine which calls, if any, have to be removed because they are out of the time
            while (
                self.url_rate_limit_history[root_url]
                and now - self.url_rate_limit_history[root_url][0] >= time_window
            ):
                self.url_rate_limit_history[root_url].popleft()

            # Determind if we hit or exceed the limit, and we should observe the limit
            if (
                not ignore_rate_limit
                and len(self.url_rate_limit_history[root_url]) >= executions_allowed
            ):
                time_to_wait = time_window - (
                    now - self.url_rate_limit_history[root_url][0]
                )
                time_to_wait = max(time_to_wait, 0)
                if use_app_error:
                    raise custom_errors.HTTPRateLimitAppCommand(time_to_wait)
                raise custom_errors.HTTPRateLimit(time_to_wait)

            # Add an entry for this call with the timestamp the call was placed
            self.url_rate_limit_history[root_url].append(now)

        url = url.replace(" ", "%20").replace("+", "%2b")

        method = method.lower()
        use_cache = kwargs.pop("use_cache", False)
        get_raw_response = kwargs.pop("get_raw_response", False)

        cache_key = url.lower()
        if kwargs.get("params"):
            params = urllib.parse.urlencode(kwargs.get("params"))
            cache_key = f"{cache_key}?{params}"

        cached_response = (
            self.http_cache.get(cache_key) if (use_cache and method == "get") else None
        )

        client = None
        if cached_response:
            response_object = cached_response
            log_message = f"Retrieving cached HTTP GET response ({cache_key})"
            return await self.process_http_response(
                response_object, method, cache_key, get_raw_response, log_message
            )
        async with aiohttp.ClientSession() as client:
            method_fn = getattr(client, method.lower())
            async with method_fn(url, *args, **kwargs) as response_object:
                log_message = (
                    f"Making HTTP {method.upper()} request to URL: {cache_key}"
                )
                return await self.process_http_response(
                    response_object,
                    method,
                    cache_key,
                    get_raw_response,
                    log_message,
                )

    async def process_http_response(
        self: Self,
        response_object: aiohttp.ClientResponse,
        method: str,
        cache_key: str,
        get_raw_response: bool,
        log_message: bool,
    ) -> munch.Munch:
        """Processes the HTTP response object, both cached and fresh

        Args:
            response_object (aiohttp.ClientResponse): The raw response object
            method (str): The HTTP method this request is using
            cache_key (str): The key for the cache array
            get_raw_response (bool): Whether the function should return the response raw
            log_message (bool): The message to send to the log

        Returns:
            munch.Munch: The resposne object ready for use
        """
        if method == "get":
            self.http_cache[cache_key] = response_object

        await self.bot.logger.send_log(
            message=log_message,
            level=LogLevel.INFO,
            console_only=True,
        )

        if get_raw_response:
            response = {
                "status": response_object.status,
                "text": await response_object.text(),
            }
        else:
            try:
                response_json = await response_object.json()
            except (
                aiohttp.ClientResponseError,
                JSONDecodeError,
            ) as exception:
                response_json = {}
                await self.bot.logger.send_log(
                    message=f"{method.upper()} request to URL: {cache_key} failed",
                    level=LogLevel.ERROR,
                    console_only=True,
                    exception=exception,
                )

            response = (
                munch.munchify(response_json) if response_object else munch.Munch()
            )
            try:
                response["status_code"] = getattr(response_object, "status", None)
            except TypeError:
                await self.bot.logger.send_log(
                    message="Failed to add status_code to API response",
                    level=LogLevel.WARNING,
                )

        return response
