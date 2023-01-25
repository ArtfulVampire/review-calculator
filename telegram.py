import datetime as dt
import json
import logging
import re
import typing as tp

import github
import nda
import startrek

ENDPOINT = 'https://api.telegram.org/bot'

# 'GITHUB_HOST/pulls/review-requested'
REQUESTED = 'https://nda.ya.ru/t/NVrtFNDk3bm54Z'
# 'GITHUB_HOST/pulls'
PULLS = 'https://nda.ya.ru/t/yZOjrZvC3bm54b'


class Update:
    __slots__ = (
        'update_id',
        'telegram_login',
        'chat_id',
        'update_type',
        'callback_data',
        'text',
        'event_at',
    )

    update_id: int
    telegram_login: str
    chat_id: str
    update_type: int  # 0 for message 1 for callback_query, TODO enum
    callback_data: str
    text: str
    event_at: tp.Optional[dt.datetime]

    def __init__(self, update: dict):
        self.update_id = update['update_id']
        logger.debug(f'update_id = {self.update_id}')

        message: dict = {}
        if 'message' in update:
            self.update_type = 0
            message = update.get('message', {})
        elif 'callback_query' in update:
            self.update_type = 1
            callback_query = update.get('callback_query', {})
            logger.debug(f'callback_query = {callback_query}')

            self.callback_data = callback_query.get('data', {})
            message = callback_query.get('message', {})
        else:
            logger.error(f'unexpected update = {update}')
            self.chat_id = ''  # crutch for loop_telegram
            return

        logger.debug(f'message = {message}')

        chat = message.get('chat', {})

        self.telegram_login = chat.get('username', '').lower()
        logger.debug(f'telegram_login = {self.telegram_login}')

        self.chat_id = str(chat['id'])
        logger.debug(f'chat_id = {self.chat_id}')

        self.text = message['text']
        logger.debug(f'text = {self.text}')

        date = message.get('date')
        logger.debug(f'date = {date}')
        self.event_at = dt.datetime.fromtimestamp(date) if date else None

    def __bool__(self):
        return (
            self.update_id
            and self.chat_id
            and self.telegram_login
            and self.text
            and self.event_at
        )

    @property
    def is_message(self):
        return self.update_type == 0

    @property
    def is_callback(self):
        return self.update_type == 1


logger = logging.getLogger()


def _ending(val: int) -> str:
    return '' if val == 1 else 's'


# TODO make more general to use directly in send_message
def _escape(string: str) -> str:
    if not string:
        return ''
    chars = f'([{re.escape(r"_*[]()~`>#+-=|{}.!")}])'
    return re.sub(chars, r'\\\1', string)


async def _staff_link(staff_login: str, ctx) -> str:
    staff_link = await nda.get_link(
        f'https://staff.yandex-team.ru/{staff_login}', ctx,
    )
    return f'[{_escape(staff_login)}]({staff_link})'


async def send_message(message: str, chat_id: str, ctx) -> None:
    response = await ctx.session.post(
        f'{ENDPOINT}{ctx.tg_token}/sendMessage',
        params={
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'MarkdownV2',
        },
    )
    response_json = await response.json()

    if not response_json['ok'] and response_json['error_code'] != 403:
        logger.error(
            f'response = {response_json}, request_message = {message}',
        )


async def get_updates(offset: int, ctx) -> tp.List[Update]:
    response = await ctx.session.post(
        f'{ENDPOINT}{ctx.tg_token}/getUpdates',
        params={
            'offset': offset,
            'timeout': 300,  # config
            'allowed_updates': 'message,callback_query',
        },
    )

    response_json = await response.json()
    logger.debug(response_json)

    if response.status != 200:
        logger.debug(
            f'bad telegram updates status {response.status}'
            f', response = {response_json}',
        )
        return []

    if not response_json.get('ok', False):
        logger.error('failed response from tg')
        return []

    result: tp.List[Update] = []
    for update in response_json.get('result', []):
        item = Update(update)
        result.append(item)

    if not result:
        pass
        # logger.info('empty response from tg')

    return result


async def hello_message(staff_login: str, is_registered: bool, ctx) -> str:
    escaped_link = await _staff_link(staff_login, ctx)
    return (
        f'Hello\nLooks like your are {escaped_link} on staff'
        if not is_registered
        else f'Your are already registered as {escaped_link}'
    )


async def goodbye_message(staff_login: str, ctx) -> str:
    return (
        f'Goodbye\\, {await _staff_link(staff_login, ctx)}\n'
        'You won\'t get notifications anymore '
        'but you can /start again and they\'ll be back\\.'
    )


async def _pr_link(pull_request: github.PullRequest, ctx) -> str:
    pr_link = await nda.get_link(pull_request.get_path(), ctx)
    return f'[{_escape(pull_request.get_slug())}]({pr_link})'


async def _st_required_link(staff_login: str, ctx) -> tp.Optional[str]:
    return await nda.get_link(
        startrek.get_required_response_link(staff_login), ctx,
    )


async def _st_notag_link(staff_login: str, ctx) -> str:
    return await nda.get_link(startrek.get_notag_link(staff_login), ctx)


async def _pr_string(pull_request: github.PullRequest, ctx) -> str:
    title_size = f'{await _pr_link(pull_request, ctx)}'
    pr_size = f'\\+{pull_request.plus}\\-{pull_request.minus}'

    author = f'by {await _staff_link(pull_request.author, ctx)}'
    if pull_request.author_telegram:
        author += f', tg: \\@{_escape(pull_request.author_telegram)}\\'

    last_review_diff = (
        _escape(f'{pull_request.last_review}')
        if pull_request.last_review
        else ''
    )
    diff_link = pull_request.get_diff_link()
    if diff_link:
        last_review_diff += (
            f', [only diff]({await nda.get_link(diff_link, ctx)})'
        )

    merged_at = _escape(pull_request.get_merged_at())

    result = f'{title_size} {pr_size}\n{author}\n'
    result += f'{last_review_diff}\n' if last_review_diff else ''
    result += f'{merged_at}\n' if merged_at else ''
    return result


async def hourly_notification(
        review: tp.Iterable[github.PullRequest],
        abandoned: tp.Iterable[github.PullRequest],
        ctx,
) -> str:
    result: str = ''
    if review:
        result += 'You have the following prs for review\\:\n'
        for pull_request in review:
            result += f'{await _pr_string(pull_request, ctx)}\n'
        result += 'You can find them '
        result += f'[here]({REQUESTED})\n\n'

    if abandoned:
        result += f'You{" also" if review else ""} have some abandoned prs\\.'
        result += ' The oldest are\\:\n'
        for pull_request in abandoned:
            result += f'{await _pr_link(pull_request, ctx)}\n'
        result += 'You can find them '
        result += f'[here]({PULLS})\n'
        result += 'Close them\\, finish\\, or add \\"backlog\\" tag'
        result += ' to disable notifications on them\n\n'

    result += 'To customize notifications call /my\\_settings'
    return result


async def want_review_message(
        pull_requests: tp.List[github.PullRequest], ctx,
) -> str:
    result: str = 'You can review the following prs\\:\n'
    for pull_request in pull_requests:
        result += f'{await _pr_string(pull_request, ctx)}\n'
    return result


async def show_reviewed_message(
        reviewed: tp.List[github.PullRequest], github_login: str, ctx,
) -> str:
    result: str = ''
    if not reviewed:
        result = 'You have no reviewed prs this week'
    else:
        result += 'You have reviewed the following prs\\:\n'
        for pull_request in reviewed:
            result += f'{await _pr_string(pull_request, ctx)}\n'

    return result


def no_stats_message() -> str:
    return 'No stats available for you now'


def unauth_message() -> str:
    return 'I don\'t know, who you are\\, send /start first'


def intruder_message() -> str:
    return (
        'This is kinda private bot and it cannot find you telegram_login '
        'in some private storage\\. Maybe you forgot to put it on staff?'
    )


async def startrack_message(staff_login: str, show_notag: bool, ctx) -> str:
    result: str = (
        'Good morning\\!\n'
        'This is a new kind of notification about Startrek\\:\n'
        'Please check the tickets where your answer is required\\:\n'
        f'The list of the tickets is [here]({await _st_required_link(staff_login, ctx)})\n'
        'The list may be empty\\, it means all is OK\n\n'
    )
    if show_notag:
        result += (
            'You were also determined as from partner products department\\.\n'
            'Please check product tags on your finished tickets\\:\n'
            f'The list of the tickets is [here]({await _st_notag_link(staff_login, ctx)})\n'
            'The wiki\\-page on the information about the product tags is '
            f'[here]({await nda.get_link(startrek.TAGS_WIKI, ctx)})\n'
            'Again\\, it is OK if the list is empty\\, no action required\n\n'
        )

    result += 'To customize notifications call /my\\_settings'
    return result


def notifications_enabled_message(step: int) -> str:
    return (
        'Notifications enabled \\- '
        f'each {step} hour{_ending(step)}\n'
        'To change this call /my\\_settings'
    )


def set_myprs_message(myprs: bool) -> str:
    return (
        f'Notifications on your abandoned prs are {"ON" if myprs else "OFF"}'
    )


def set_wipprs_message(wipprs: bool) -> str:
    return f'Notifications on wip prs are {"ON" if wipprs else "OFF"}'


def set_startrek_message(value: bool) -> str:
    return (
        'Weekly notifications on Startrek tickets are'
        f' {"ON" if value else "OFF"}'
    )


def _stats_header(date_from: str, date_to: str) -> str:
    return f'The stats for {_escape(date_from)} \\- {_escape(date_to)} are:'


def _minutes_pretty(mins: float) -> str:
    result: str = ''
    mins = int(mins)
    days = mins // (9 * 60)  # 9 hours in working day
    if days:
        result += f'{days} day{_ending(days)}, '

    hours = (mins % (9 * 60)) // 60
    if hours or days:
        result += f'{hours} hour{_ending(hours)}, '

    minutes = mins % 60
    result += f'{minutes} minute{_ending(minutes)}'
    return result


def _single_stats(stats: dict) -> str:
    return f"""```
  quantity: {stats['number']}
  average: {_minutes_pretty(stats['mean'])}
  median:  {_minutes_pretty(stats['median'])}
  std.dev: {_minutes_pretty(stats['sigma'])}
```"""


def format_single_stats(date_from: str, date_to: str, stats: dict) -> str:
    result: str = _stats_header(date_from, date_to)
    result += '\n'
    result += _single_stats(stats)
    return result


def format_multiple_stats(
        date_from: str, date_to: str, stats_dict: dict,
) -> str:
    result: str = _stats_header(date_from, date_to)
    result += '\n'
    for login, stats in stats_dict.items():
        result += f'{_escape(login)}:'
        result += '\n'
        result += _single_stats(stats)
    return result


async def _reply_markup_message(
        chat_id: str,
        message: str,
        inline_keyboard: tp.List[tp.List[dict]],
        ctx,
) -> None:
    response = await ctx.session.post(
        f'{ENDPOINT}{ctx.tg_token}/sendMessage',
        params={
            'chat_id': chat_id,
            'text': message,
            'reply_markup': json.dumps({'inline_keyboard': inline_keyboard}),
        },
    )
    response_json = await response.json()

    if not response_json['ok']:
        logger.error(f'response = {response_json}')


async def ask_for_settings(chat_id: str, ctx) -> None:
    message = 'Choose your notification params'
    keyboard = [
        [
            {'text': 'each hour', 'callback_data': 'notify_1'},
            {'text': 'each 2 hours', 'callback_data': 'notify_2'},
        ],
        [
            {'text': 'each 4 hours', 'callback_data': 'notify_4'},
            {'text': 'disable', 'callback_data': 'notify_0'},
        ],
        [
            {'text': 'my prs on', 'callback_data': 'myprs_1'},
            {'text': 'my prs off', 'callback_data': 'myprs_0'},
        ],
        [
            {'text': 'wip prs on', 'callback_data': 'wipprs_1'},
            {'text': 'wip prs off', 'callback_data': 'wipprs_0'},
        ],
        [
            {'text': 'startrek on', 'callback_data': 'startrek_1'},
            {'text': 'startrek off', 'callback_data': 'startrek_0'},
        ],
    ]
    await _reply_markup_message(chat_id, message, keyboard, ctx)


async def ask_for_open_reviews(chat_id: str, ctx) -> None:
    message = 'Choose the scope of PR authors'
    keyboard = [
        [{'text': 'My group', 'callback_data': 'want_review_0'}],
        [{'text': '+ neighbour groups', 'callback_data': 'want_review_1'}],
    ]
    await _reply_markup_message(chat_id, message, keyboard, ctx)


async def ask_for_stats(chat_id: str, ctx) -> None:
    message = 'Choose the week to show stats for'
    keyboard = [
        [{'text': 'This week', 'callback_data': 'week_0'}],
        [{'text': 'Prev week', 'callback_data': 'week_1'}],
        [{'text': '2 weeks ago', 'callback_data': 'week_2'}],
        [{'text': '3 weeks ago', 'callback_data': 'week_3'}],
        [{'text': 'All the time', 'callback_data': 'week_-1'}],
    ]
    await _reply_markup_message(chat_id, message, keyboard, ctx)


async def ask_for_subordinated_stats(chat_id: str, ctx) -> None:
    message = 'Choose the type of subordination'
    keyboard = [
        [
            {
                'text': 'Nearest, this week',
                'callback_data': 'stats_sub_nearest_0',
            },
            {'text': 'All, this week', 'callback_data': 'stats_sub_all_0'},
        ],
        [
            {
                'text': 'Nearest, prev week',
                'callback_data': 'stats_sub_nearest_1',
            },
            {'text': 'All, prev week', 'callback_data': 'stats_sub_all_1'},
        ],
        [
            {
                'text': 'Nearest, 2 weeks ago',
                'callback_data': 'stats_sub_nearest_2',
            },
            {'text': 'All, 2 weeks ago', 'callback_data': 'stats_sub_all_2'},
        ],
        [
            {
                'text': 'Nearest, all the time',
                'callback_data': 'stats_sub_nearest_-1',
            },
            {'text': 'All, all the time', 'callback_data': 'stats_sub_all_-1'},
        ],
    ]
    await _reply_markup_message(chat_id, message, keyboard, ctx)


async def ask_for_reviewed(chat_id: str, ctx) -> None:
    message = 'Choose the week to show reviewed for'
    keyboard = [
        [{'text': 'This week', 'callback_data': 'reviewed_0'}],
        [{'text': 'Prev week', 'callback_data': 'reviewed_1'}],
        [{'text': '2 weeks ago', 'callback_data': 'reviewed_2'}],
        [{'text': '3 weeks ago', 'callback_data': 'reviewed_3'}],
    ]
    await _reply_markup_message(chat_id, message, keyboard, ctx)
