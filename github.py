import dataclasses
import datetime as dt
# import logging
import re
import typing as tp

import common
import graphql
import queries
import staff


GITHUB_PREFIX = 'https://github.com'


# logger = logging.getLogger()


def _ago_to_string(datetime: dt.datetime) -> str:
    days = (dt.date.today() - datetime.date()) // dt.timedelta(days=1)
    days_str = 'today'
    if days == 1:
        days_str = 'yesterday'
    elif days > 1:
        days_str = f'{days} days ago on {datetime.strftime("%A")}'
    # days_str += f' at {datetime.strftime("%H:%M")}' # TODO timezone
    return days_str


@dataclasses.dataclass()
class Review:
    author: str
    commit: str
    submitted_at: tp.Optional[dt.datetime]

    def __str__(self):
        return f'last reviewed {_ago_to_string(self.submitted_at)}'


@dataclasses.dataclass(frozen=True, order=True)
class PullRequest:
    owner: str
    repo: str
    number: int
    title: tp.Optional[str] = None
    is_wip: bool = False
    merged_at: tp.Optional[dt.datetime] = None
    author: str = 'unknown'
    author_telegram: tp.Optional[str] = None
    plus: int = 0
    minus: int = 0
    last_review: tp.Optional[Review] = None  # last_review by the caller

    def to_dict(self) -> dict:
        return {'owner': self.owner, 'repo': self.repo, 'number': self.number}

    def get_path(self) -> str:
        return f'{GITHUB_PREFIX}/{self.owner}/{self.repo}/pull/{self.number}'

    def get_short_slug(self) -> str:
        return f'{self.owner}/{self.repo}#{self.number}'

    def get_slug(self) -> str:
        title: str = self.title or ''
        if len(title) > 50:
            title = title[:47]
            title = re.sub(r'\\', '', title)
            title += ' ...'

        return title if title else self.get_short_slug()

    def get_diff_link(self) -> tp.Optional[str]:
        if not self.last_review:
            return None

        return f'{self.get_path()}/files/{self.last_review.commit}..HEAD'

    def get_merged_at(self):
        return (
            f'merged {_ago_to_string(self.merged_at)}'
            if self.merged_at
            else ''
        )

    def __str__(self):
        return self.get_slug()


def _parse_time(arg: str) -> dt.datetime:
    return dt.datetime.strptime(arg, '%Y-%m-%dT%H:%M:%S%z').astimezone(
        dt.timezone.utc,
    )


async def get_timeline(
        pull_request: PullRequest, ctx,
) -> tp.Tuple[str, tp.List[dict]]:
    query = queries.get_timeline(
        pull_request.owner, pull_request.repo, pull_request.number,
    )

    response_json = await graphql.perform_request(query, ctx)

    resp = response_json['data']['repository']['pullRequest']

    author: str = resp['author']['login']
    events: tp.List[tp.Dict] = resp['timelineItems']['nodes']
    return author, events


async def get_new_pr_numbers(
        owner: str,
        repo: str,
        cursor: str,
        how_many: int,
        is_merged: bool,
        ctx,
) -> tp.Tuple[tp.List[int], tp.Optional[str], tp.Optional[dt.datetime]]:
    query = queries.get_pr_numbers(owner, repo, cursor, how_many, is_merged)

    response_json = await graphql.perform_request(query, ctx)
    edges = response_json['data']['repository']['pullRequests']['edges']

    numbers: tp.List[int] = []
    for edge_dict in edges:
        numbers.append(edge_dict['node']['number'])

    return (
        numbers,
        (edges[-1]['cursor'] if is_merged and edges else None),
        (
            _parse_time(edges[-1]['node']['mergedAt'])
            if is_merged and edges
            else None
        ),
    )


async def get_new_pr_cursor(
        owner: str, repo: str, offset: int, ctx,
) -> tp.Optional[tp.Tuple[int, str, dt.datetime]]:
    query = queries.get_pr_numbers(
        owner=owner,
        repo=repo,
        cursor=None,
        how_many=min(offset + 1, 100),
        is_merged=True,
    )

    response_json = await graphql.perform_request(query, ctx)
    edges = response_json['data']['repository']['pullRequests']['edges']

    return (
        (
            edges[0]['node']['number'],
            edges[0]['cursor'],
            _parse_time(edges[0]['node']['mergedAt']),
        )
        if edges
        else None
    )


async def _get_search_results(
        query: dict,
        github_login: tp.Optional[str],
        get_author_login: bool,
        ctx,
) -> tp.List[PullRequest]:
    def _parse_time(timestring: tp.Optional[str]) -> tp.Optional[dt.datetime]:
        if not timestring:
            return None
        return dt.datetime.strptime(timestring, '%Y-%m-%dT%H:%M:%SZ')

    response_json = await graphql.perform_request(query, ctx)
    print(f'response_json = {response_json}')
    # logger.info(f'{response_json}')
    edges = response_json['data']['search']['edges']

    result: tp.List[PullRequest] = []
    for edge_dict in edges:
        node = edge_dict['node']
        owner = node['repository']['owner']['login']
        repo = node['repository']['name']

        # should filter here ?
        if owner not in common.REPOS or repo not in common.REPOS[owner]:
            continue

        if node['isDraft']:
            # TODO make a switcher in settings
            continue

        labels = {label['name'].lower() for label in node['labels']['nodes']}
        if 'not for merge' in labels:
            # TODO make a switcher in settings ?
            continue

        last_review: tp.Optional[Review] = None
        if github_login:
            for review in reversed(node['reviews']['nodes']):
                if review['author']['login'] == github_login:
                    last_review = Review(
                        author=review['author']['login'],
                        commit=review['commit']['oid'],
                        submitted_at=_parse_time(review['submittedAt']),
                    )
                break

        tg_login = None
        if get_author_login:
            tg_login = await staff.get_telegram_login_with_pg(
                node['author']['login'], ctx,
            )

        result.append(
            PullRequest(
                owner=owner,
                repo=repo,
                number=node['number'],
                title=node['title'],
                is_wip='wip' in labels,
                merged_at=_parse_time(node.get('mergedAt')),
                author=node['author']['login'],
                author_telegram=tg_login,
                plus=node['additions'],
                minus=node['deletions'],
                last_review=last_review,
            ),
        )

    result.sort(reverse=True)
    # logger.info(f'_get_search_results response size = {len(result)}')
    return result


async def get_requested_reviews(
        github_login: str, ctx,
) -> tp.List[PullRequest]:
    now = dt.datetime.now()
    timelimit = (now - dt.timedelta(days=now.weekday() + 7)).date()  # config
    query = queries.get_requested_prs(github_login, timelimit.isoformat())
    return await _get_search_results(query, github_login, True, ctx)


async def get_abandoned_prs(
        github_login: str, delta: dt.timedelta, ctx,
) -> tp.List[PullRequest]:
    date_limit = (dt.datetime.now() - delta).date()
    query = queries.get_abandoned_prs(github_login, date_limit.isoformat())
    return await _get_search_results(query, None, False, ctx)


async def get_open_prs(
        github_logins: tp.Iterable[str], asker_login: str, ctx,
) -> tp.List[PullRequest]:
    date_limit = (
        (dt.datetime.now() - dt.timedelta(days=10)).date().isoformat()
    )  # config

    result: tp.List[PullRequest] = []
    # TODO single request?
    for github_login in github_logins:
        query = queries.get_open_prs(github_login, date_limit)
        chunk = await _get_search_results(query, asker_login, True, ctx)
        result.extend(chunk)

    result.sort(reverse=True)
    return result


async def get_reviewed_prs(
        github_login: str,
        date_from: dt.datetime,
        date_to: dt.datetime,
        merged: tp.Optional[bool],
        ctx,
) -> tp.List[PullRequest]:
    query = queries.get_reviewed_prs(
        github_login,
        date_from.date().isoformat(),
        date_to.date().isoformat(),
        merged,
    )
    return await _get_search_results(query, github_login, True, ctx)
