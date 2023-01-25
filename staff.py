import datetime as dt
import itertools
import logging
import typing as tp

import storage

_STAFF_API_PREFIX = 'https://nda.ya.ru/t/OkwP-QZh5pPZcd'
_CHUNK_SIZE = 30

_GAP_API_PREFIX = 'https://nda.ya.ru/t/4QEPWJCG5pPZdp'


logger = logging.getLogger()


async def _get_staff_login_api(telegram_login: str, ctx) -> str:
    response = await ctx.session.get(
        f'{_STAFF_API_PREFIX}/persons',
        params={
            '_query': (
                f'accounts==match('
                f'{{"type":"telegram",'
                f'"value_lower":"{telegram_login.lower()}"}})'
            ),
            '_fields': 'login',
            '_one': 1,
        },
        headers={'Authorization': f'OAuth {ctx.staff_token}'},
    )
    response_json = await response.json()
    return response_json['login']


async def get_subordinated_nearest(staff_login: str, ctx) -> tp.List[str]:
    response = await ctx.session.get(
        f'{_STAFF_API_PREFIX}/persons',
        params={
            'chief.login': staff_login,
            'official.is_dismissed': 'false',
            '_fields': 'login',
        },
        headers={'Authorization': f'OAuth {ctx.staff_token}'},
    )
    response_json = await response.json()
    return [item['login'] for item in response_json['result']]


async def get_subordinated_all(staff_login: str, ctx) -> tp.List[str]:
    result: tp.List[str] = []

    next_link: tp.Optional[str] = (
        f'{_STAFF_API_PREFIX}/persons'
        f'?_fields=login'
        f'&chiefs.login={staff_login}'
        f'&official.is_dismissed=false'
        f'&_limit={_CHUNK_SIZE}'
    )
    while next_link is not None:
        response = await ctx.session.get(
            next_link, headers={'Authorization': f'OAuth {ctx.staff_token}'},
        )
        response_json = await response.json()
        result.extend([item['login'] for item in response_json['result']])
        next_link = response_json.get('links', {}).get('next', None)

    return result


# returns staff_login, was_already_registered
async def register_user(
        telegram_login: str, chat_id: str, ctx,
) -> tp.Tuple[tp.Optional[str], bool]:
    staff_login: str = await storage.get_staff_login_pg(
        telegram_login, ctx.conn,
    )
    if staff_login:
        logger.debug(f'{staff_login} already registered')
    else:
        staff_login = await _get_staff_login_api(telegram_login, ctx)
        if not staff_login:
            logger.warning(f'cant find staff login for @{telegram_login}')
            return None, False

    logger.debug(
        f'got staff login {staff_login} for telegram @{telegram_login}',
    )

    await storage.save_user_mappings(
        staff_login, telegram_login, chat_id, ctx.conn,
    )

    return staff_login, False


async def deregister_user(telegram_login: str, ctx) -> None:
    await storage.delete_user_mappings(telegram_login, ctx.conn)


async def get_staff_login(telegram_login: str, ctx) -> str:
    staff_login: str = await storage.get_staff_login_pg(
        telegram_login, ctx.conn,
    )
    logger.debug(
        f'got staff login {staff_login} for telegram @{telegram_login}',
    )
    return staff_login


async def get_telegram_login(staff_login: str, ctx) -> tp.Optional[str]:
    response = await ctx.session.get(
        f'{_STAFF_API_PREFIX}/persons',
        params={
            'login': staff_login,
            'official.is_dismissed': 'false',
            '_fields': 'login,telegram_accounts',
        },
        headers={'Authorization': f'OAuth {ctx.staff_token}'},
    )
    response_json = await response.json()
    if not response_json['result']:
        return None

    response_users = response_json.get('result')
    if not response_users:
        logger.warning(f'no user found with login {staff_login}')
        return None

    tg_items = response_users[0].get('telegram_accounts')
    if not tg_items:
        logger.warning(f'no telegram_accounts found for {staff_login}')
        return None

    return tg_items[0]['value_lower']


async def get_telegram_login_with_pg(
        staff_login: str, ctx,
) -> tp.Optional[str]:
    tg_login_pg = await storage.get_telegram_login_pg(staff_login, ctx.conn)
    if tg_login_pg:
        return tg_login_pg

    tg_login = await get_telegram_login(staff_login, ctx)
    if tg_login:
        await storage.save_user_mappings(staff_login, tg_login, None, ctx.conn)

    return tg_login


async def get_telegram_logins(
        staff_logins: tp.Iterable[str], ctx,
) -> tp.Dict[str, tp.Set[str]]:
    result: tp.Dict[str, tp.Set[str]] = {}

    chunks = [iter(staff_logins)] * _CHUNK_SIZE
    for chunk in itertools.zip_longest(*chunks):
        response = await ctx.session.get(
            f'{_STAFF_API_PREFIX}/persons',
            params={
                'login': ','.join(
                    [item for item in chunk if item is not None],
                ),
                'official.is_dismissed': 'false',
                '_fields': 'login,telegram_accounts',
            },
            headers={'Authorization': f'OAuth {ctx.staff_token}'},
        )
        response_json = await response.json()
        for item in response_json['result']:
            tg_logins: tp.Set[str] = set()
            for tg_item in item['telegram_accounts']:
                tg_logins.add(tg_item['value_lower'])
            result[item['login']] = tg_logins

        # TODO - backup pagination plan
        # next_link = response_json.get('links', {}).get('next', '')

    return result


async def get_absent_time(
        staff_login: str, date_from: dt.date, date_to: dt.date, ctx,
) -> tp.List[tp.Tuple[dt.datetime, dt.datetime]]:
    try:
        response = await ctx.session.get(
            f'{_GAP_API_PREFIX}/api/gaps_find/',
            params={
                'person_login': staff_login,
                'date_from': date_from.isoformat(),
                'date_to': date_to.isoformat(),
            },
            headers={'Authorization': f'OAuth {ctx.staff_token}'},
        )
    except BaseException:
        logger.warning('error during gaps api request')
        return []

    response_json = await response.json()
    gaps = response_json['gaps']

    result: tp.List[tp.Tuple[dt.datetime, dt.datetime]] = []
    for gap in gaps:
        if gap.get('work_in_absence'):
            continue

        result.append(
            (
                dt.datetime.fromisoformat(gap['date_from']),
                dt.datetime.fromisoformat(gap['date_to']),
            ),
        )

    return result


async def get_fellow_authors(staff_login: str, rng: int, ctx) -> tp.Set[str]:
    subs_both = await storage.get_subordinated(staff_login, ctx.conn)

    if subs_both:
        if rng == 0:
            subs_both[1].discard(staff_login)
            return subs_both[1]

        rng -= 1

    response = await ctx.session.get(
        f'{_STAFF_API_PREFIX}/persons',
        params={'login': staff_login, '_fields': 'chiefs.login'},
        headers={'Authorization': f'OAuth {ctx.staff_token}'},
    )
    response_json = await response.json()
    chief_login = response_json['result'][0]['chiefs'][rng]['login']

    subs_both = await storage.get_subordinated(chief_login, ctx.conn)
    if not subs_both:
        return set()

    subs_both[1].discard(staff_login)
    return subs_both[1]


async def is_partner_product(staff_login: str, conn) -> bool:
    return staff_login in await storage.get_partner_product_logins(conn)
