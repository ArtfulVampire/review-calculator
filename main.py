import asyncio
import logging

import aiohttp
import asyncpg

import common
import configs
import loop_chiefs
import loop_gaps
import loop_logins
import loop_notify
import loop_startrek
import loop_stats
import loop_telegram
import secrets

logger = logging.getLogger()


class Context:
    staff_token: str
    github_token: str
    tg_token: str
    config: configs.Config
    session: aiohttp.client.ClientSession
    conn: asyncpg.Connection


async def create_ctx(
        secrets_dict: dict, session: aiohttp.client.ClientSession,
):
    ctx = Context()
    ctx.conn = await asyncpg.connect(**secrets_dict['pg_dsn'])
    ctx.session = session
    ctx.config = configs.Config(is_test=False)
    ctx.staff_token = secrets_dict['staff_token']
    ctx.github_token = secrets_dict['github_token']
    ctx.tg_token = secrets_dict['tg_token']
    return ctx


async def loop_wrapper(context, delta, func):
    while True:
        try:
            if delta:
                await asyncio.sleep(common.secs_to_next_round(delta))
            await func(context)
        except BaseException:
            logger.exception(f'Exception during {func.__name__} iteration.')
            await asyncio.sleep(30)


async def cron_wrapper(context, func, **sleep_kwargs):
    while True:
        try:
            await asyncio.sleep(common.seconds_till(**sleep_kwargs))
            await func(context)
            await asyncio.sleep(60)
        except BaseException:
            logger.exception(f'Exception during {func.__name__} iteration.')
            await asyncio.sleep(30)


async def run_wrapper():
    async with aiohttp.ClientSession() as session:
        # set some "global" stuff
        secrets_dict = secrets.load_secrets()
        context = await create_ctx(secrets_dict, session)
        async with asyncpg.create_pool(
                min_size=10, max_size=10, **secrets_dict['pg_dsn'],
        ) as pool:
            context.pool = pool
            logging_format = (
                'tskv'
                '\ttimestamp=%(asctime)s'
                '\tlevel=%(levelname)s'
                '\tfile=%(filename)s'
                '\tfunc=%(funcName)s'
                '\tline=%(lineno)s'
                '\ttext=%(message)s'
            )
            logging.basicConfig(
                filename='/tmp/server.log',
                format=logging_format,
                # datefmt='%Y-%m-%dT%H-%M-%S%Z',
            )
            logging.getLogger().setLevel(logging.INFO)
            # logging.getLogger().setLevel(logging.DEBUG)

            # what are you? a cron-task imitation? pathetic!
            await asyncio.gather(
                loop_wrapper(
                    context,
                    context.config.process_stats_delta,
                    loop_stats.process_stats,
                ),
                loop_wrapper(
                    context,
                    context.config.process_notify_delta,
                    loop_notify.process_notify,
                ),
                loop_wrapper(
                    context,
                    None,  # long polling, doesn't need sleep here
                    loop_telegram.process_telegram_input,
                ),
                loop_wrapper(
                    context,
                    context.config.process_gaps_delta,
                    loop_gaps.update_gaps_info,
                ),
                loop_wrapper(
                    context,
                    context.config.process_subordinated_delta,
                    loop_chiefs.update_subordinated,
                ),
                loop_wrapper(
                    context,
                    context.config.process_logins_delta,
                    loop_logins.update_logins,
                ),
                cron_wrapper(
                    context,
                    loop_startrek.notify_startrek,
                    weekday=0,
                    hour=10,  # local Moscow time
                    minute=45,
                ),
            )


if __name__ == '__main__':
    asyncio.run(run_wrapper())
