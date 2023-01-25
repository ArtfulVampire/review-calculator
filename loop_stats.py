import logging
import typing as tp

import common
import github
import stats
import storage


logger = logging.getLogger()


async def process_stats(ctx):
    async with ctx.pool.acquire() as conn:
        logger.debug('stats calculation started')

        for owner, repos in common.REPOS.items():
            logger.debug(f'processing owner {owner}')
            for repo in repos:
                logger.debug(f'processing repo {repo}')

                last_run_cursor = await storage.get_cursor(owner, repo, conn)
                if not last_run_cursor:
                    logger.warning(
                        f'not found last cursor for {repo}, '
                        'acquire cursor for the last pr',
                    )
                    (
                        pr_num,
                        last_run_cursor,
                        merged_at,
                    ) = await github.get_new_pr_cursor(owner, repo, 100, ctx)

                    if not last_run_cursor:
                        logger.error(f'failed to get cursor {owner}, {repo}')
                        continue
                    await storage.save_cursor(
                        last_run_cursor,
                        github.PullRequest(owner, repo, pr_num),
                        merged_at,
                        conn,
                    )

                new_pr_numbers, new_cursor, merged_at = (
                    await github.get_new_pr_numbers(
                        owner,
                        repo,
                        last_run_cursor,
                        20,  # config
                        True,  # ???
                        ctx,
                    )
                )

                if not new_pr_numbers:
                    logger.debug(f'no new prs for owner {owner}, repo {repo}')
                    continue
                else:
                    logger.debug(f'{len(new_pr_numbers)} new prs obtained')

                for pr_number in new_pr_numbers:
                    pull_request = github.PullRequest(owner, repo, pr_number)
                    if await storage.is_pr_processed(pull_request, conn):
                        logger.debug(f'{pull_request} already processed, skip')
                        continue

                    pr_stats: tp.List[tp.Dict] = await stats.get_review_stats(
                        pull_request, ctx,
                    )

                    await storage.mark_as_processed(pull_request, conn)
                    await storage.save_times(pull_request, pr_stats, conn)
                    logger.debug(f'{pull_request} successfully processed')

                await storage.save_cursor(
                    new_cursor,
                    github.PullRequest(owner, repo, new_pr_numbers[-1]),
                    merged_at,
                    conn,
                )
                logger.debug(
                    f'cursor updated for owner {owner} and repo {repo}',
                )
