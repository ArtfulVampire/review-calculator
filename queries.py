import typing as tp

import serialization


def get_timeline(owner: str, repo: str, number: int) -> dict:
    return serialization.graphql_query(
        {
            'query': {
                'repository': {
                    serialization.PARAMS_KEY: {'owner': owner, 'name': repo},
                    'pullRequest': {
                        serialization.PARAMS_KEY: {'number': number},
                        'author': {'login': None},
                        'timelineItems': {
                            serialization.PARAMS_KEY: {
                                'first': 100,  # TODO add pagination
                                'itemTypes': [
                                    'READY_FOR_REVIEW_EVENT',
                                    'REVIEW_REQUESTED_EVENT',
                                    'REVIEW_REQUEST_REMOVED_EVENT',
                                    'PULL_REQUEST_REVIEW',
                                    'MERGED_EVENT',
                                    'CLOSED_EVENT',
                                ],
                            },
                            'updatedAt': None,
                            'totalCount': None,
                            'nodes': {
                                '__typename': None,
                                '... on ReadyForReviewEvent': {
                                    'actor': {'login': None},
                                    'createdAt': None,
                                },
                                '... on PullRequestReview': {
                                    'author': {'login': None},
                                    'submittedAt': None,
                                    'state': None,
                                },
                                '... on ReviewRequestedEvent': {
                                    'actor': {'login': None},
                                    'createdAt': None,
                                    'requestedReviewer': {
                                        '... on User': {'login': None},
                                    },
                                },
                                '... on ReviewRequestRemovedEvent': {
                                    'actor': {'login': None},
                                    'createdAt': None,
                                    'requestedReviewer': {
                                        '... on User': {'login': None},
                                    },
                                },
                                '... on MergedEvent': {
                                    'actor': {'login': None},
                                    'createdAt': None,
                                },
                                '... on ClosedEvent': {
                                    'actor': {'login': None},
                                    'createdAt': None,
                                },
                            },
                        },
                    },
                },
            },
        },
    )


def get_pr_numbers(
        owner: str,
        repo: str,
        cursor: tp.Optional[str],
        how_many: int,
        is_merged: bool,
) -> dict:
    params: dict = {'orderBy': {'direction': 'ASC', 'field': 'UPDATED_AT'}}
    if is_merged:
        params['states'] = ['MERGED']
        if cursor:
            params['after'] = cursor
            params['first'] = how_many
        else:
            params['last'] = how_many
    else:
        params['states'] = ['OPEN']
        params['last'] = how_many

    return serialization.graphql_query(
        {
            'query': {
                'repository': {
                    serialization.PARAMS_KEY: {'owner': owner, 'name': repo},
                    'pullRequests': {
                        serialization.PARAMS_KEY: params,
                        'edges': {
                            'node': {'number': {}, 'mergedAt': {}},
                            'cursor': {},
                        },
                    },
                },
            },
        },
    )


def _make_search_query(params: dict) -> dict:
    return {
        'query': {
            'search': {
                serialization.PARAMS_KEY: params,
                'edges': {
                    'node': {
                        '... on PullRequest': {
                            'repository': {
                                'name': None,
                                'owner': {'login': None},
                            },
                            'author': {'login': None},
                            'additions': None,
                            'deletions': None,
                            'isDraft': None,
                            'title': None,
                            'reviews': {
                                # TODO the dependent logic may fail
                                serialization.PARAMS_KEY: {'last': 10},
                                'nodes': {
                                    'author': {'login': None},
                                    'commit': {
                                        'abbreviatedOid': None,
                                        'oid': None,
                                    },
                                    'submittedAt': None,
                                },
                            },
                            'merged': None,
                            'mergedAt': None,
                            'number': None,
                            'url': None,
                            'labels': {
                                # TODO the dependent logic may fail
                                serialization.PARAMS_KEY: {'first': 10},
                                'nodes': {'name': None},
                            },
                        },
                    },
                },
            },
        },
    }


def get_requested_prs(github_login: str, timelimit: str) -> dict:
    prs = 'is:open type:pr'
    reviewer = f'review-requested:{github_login}'
    not_approved = f'-review:approved'
    updated = f'updated:>{timelimit}'
    sort = 'sort:updated-asc'

    params = {
        'query': f'{prs} {reviewer} {not_approved} {updated} {sort}',
        # 'type': 'ISSUE',
        # 'last': 10,  # config
    }
    result = _make_search_query(params)
    return serialization.graphql_query(result)


def get_abandoned_prs(github_login: str, timelimit: str) -> dict:
    prs = 'is:open type:pr'
    author = f'author:{github_login}'
    updated = f'updated:<{timelimit}'
    not_backlog = '-label:backlog'
    sort = 'sort:updated-asc'

    params = {
        'query': f'{prs} {author} {updated} {not_backlog} {sort}',
        'type': 'ISSUE',
        'first': 3,  # config
    }

    return serialization.graphql_query(_make_search_query(params))


def get_open_prs(github_login: str, date_from: str) -> dict:
    prs = 'is:open type:pr'
    author = f'author:{github_login}'
    updated = f'updated:>{date_from}'
    review = '-review:approved'
    not_backlog = '-label:backlog'
    not_draft = 'draft:false'
    sort = 'sort:updated-asc'

    params = {
        'query': (
            f'{prs} {author} {updated} {not_backlog} '
            f'{not_draft} {review} {sort}'
        ),
        'type': 'ISSUE',
        'first': 3,  # config
    }

    return serialization.graphql_query(_make_search_query(params))


def get_reviewed_prs(
        github_login: str,
        date_from: str,
        date_to: str,
        merged: tp.Optional[bool],
) -> dict:
    prs = 'type:pr'
    reviewer = f'reviewed-by:{github_login}'
    not_author = f'-author:{github_login}'
    updated = f'updated:{date_from}..{date_to}'
    merge = (
        f'is:{"merged" if merged else "open"}' if merged is not None else ''
    )
    sort = 'sort:updated-asc'

    params: dict = {
        'query': f'{prs} {reviewer} {not_author} {updated} {merge} {sort}',
        'type': 'ISSUE',
        'first': 20,
    }

    return serialization.graphql_query(_make_search_query(params))
