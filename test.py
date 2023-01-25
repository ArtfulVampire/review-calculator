import asyncio
import datetime as dt
import logging
import typing as tp

import aiohttp
# import asyncpg

import calendarm
import common
import configs
import github
import loop_chiefs
import loop_gaps
import loop_logins
import loop_notify
import loop_startrek
import loop_stats
import loop_telegram
# import secrets
import serialization
import staff
import stats
import storage
import telegram
import user_settings
import queries

logger = logging.getLogger()

class Context:
    staff_token: str
    github_token: str
    tg_token: str
    config: configs.Config
    session: aiohttp.client.ClientSession
    # conn: asyncpg.Connection


async def create_ctx(
        secrets_dict: dict, session: aiohttp.client.ClientSession,
):
    ctx = Context()
    ctx.session = session
    ctx.config = configs.Config(is_test=False)
    ctx.github_token = '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'
    return ctx


USER = 'artfulvampire'

async def run_wrapper():
    async with aiohttp.ClientSession() as session:
        ctx = await create_ctx({}, session)
        #reviews = await github.get_requested_reviews(USER, ctx)
        now = dt.datetime.now()
        timelimit = (now - dt.timedelta(days=now.weekday() + 7)).date()  # config
        #query = queries.get_requested_prs(USER, timelimit.isoformat())
        prs = 'is:open type:pr'
        reviewer = f'review-requested:{USER}'
        not_approved = f'-review:approved'
        updated = f'updated:>{timelimit}'
        sort = 'sort:updated-asc'
        params = {
            'query': f'{prs} {reviewer}',
            'type': 'ISSUE',
            'last': 100,
        }
        result = queries._make_search_query(params)
        query = serialization.serialize_request(result, indent=2, is_pretty=True)
        print(query)
        reviews = await github._get_search_results({'query': query}, USER, True, ctx)
        print(reviews)

asyncio.run(run_wrapper())


# if __name__ == '__main__':
#    asyncio.run(run_wrapper())
