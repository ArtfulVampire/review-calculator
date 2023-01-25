import datetime as dt
import json
import typing as tp

import github


async def get_cursor(owner: str, repo: str, conn) -> str:
    _get_cursor_query = """
    SELECT cursor
    FROM reviews.cursors
    WHERE owner = $1 AND repo = $2;
    """
    row = await conn.fetchrow(_get_cursor_query, owner, repo)
    return row.get('cursor') if row else None


async def save_cursor(
        cursor: str,
        pull_request: github.PullRequest,
        merged_at: dt.datetime,
        conn,
) -> None:
    _save_cursor_query = """
    INSERT INTO reviews.cursors (owner, repo, cursor)
    VALUES ($1, $2, $3)
    ON CONFLICT (owner, repo) DO UPDATE
      SET cursor = $3
      WHERE reviews.cursors.owner = $1
        AND reviews.cursors.repo = $2;
    """
    await conn.execute(
        _save_cursor_query, pull_request.owner, pull_request.repo, cursor,
    )

    _save_cursor_query_history = """
    INSERT INTO reviews.cursors_history
      (owner, repo, number, cursor, merged_at)
    VALUES ($1, $2, $3, $4, $5)
    ON CONFLICT DO NOTHING;
    """
    await conn.execute(
        _save_cursor_query_history,
        pull_request.owner,
        pull_request.repo,
        pull_request.number,
        cursor,
        merged_at,
    )


async def mark_as_processed(pull_request: github.PullRequest, conn) -> None:
    _set_pr_processed_query = """
    INSERT INTO reviews.processed_prs
      (owner, repo, number, event_at)
    VALUES ($1, $2, $3, NOW() AT TIME ZONE 'UTC')
    ON CONFLICT DO NOTHING;
    """
    await conn.execute(
        _set_pr_processed_query,
        pull_request.owner,
        pull_request.repo,
        pull_request.number,
    )


async def is_pr_processed(pull_request: github.PullRequest, conn) -> bool:
    _check_pr_processed_query = """
    SELECT COUNT(*) = 1
    FROM reviews.processed_prs
    WHERE owner = $1
      AND repo = $2
      AND number = $3;
    """
    row = await conn.fetchrow(
        _check_pr_processed_query,
        pull_request.owner,
        pull_request.repo,
        pull_request.number,
    )
    return row[0]


async def save_times(
        pull_request: github.PullRequest, pr_stats: tp.List[tp.Dict], conn,
) -> None:
    _save_stats_query = """
    INSERT INTO reviews.review_stats
      (owner, repo, number, reviewer, minutes, review_at)
    VALUES (
      $1,
      $2,
      $3,
      UNNEST($4::TEXT[]),
      UNNEST($5::INTEGER[]),
      UNNEST($6::TIMESTAMPTZ[])
    )
    ON CONFLICT DO NOTHING;
    """
    reviewers: list = []
    minutes: list = []
    review_ats: list = []
    for item in pr_stats:
        reviewers.append(item['reviewer'])
        minutes.append(item['minutes'])
        review_ats.append(item['review_at'])

    await conn.execute(
        _save_stats_query,
        pull_request.owner,
        pull_request.repo,
        pull_request.number,
        reviewers,
        minutes,
        review_ats,
    )


async def get_partner_product_logins(conn) -> tp.List[str]:
    _get_partner_product_logins = """
    SELECT value
    FROM reviews.key_value
    WHERE reviews.key_value.key = 'partner_product_logins';
    """
    row = await conn.fetchrow(_get_partner_product_logins)
    if not row:
        return []

    return json.loads(row['value'])


async def get_tg_update_offset(conn) -> tp.Optional[int]:
    _get_tg_update_offset = """
    SELECT value
    FROM reviews.key_value
    WHERE reviews.key_value.key = 'tg_update_offset';
    """
    row = await conn.fetchrow(_get_tg_update_offset)
    return int(row['value']) if row and 'value' in row else None


async def set_tg_update_offset(value: str, conn) -> None:
    _set_tg_update_offset = """
    INSERT INTO reviews.key_value (key, value)
    VALUES ('tg_update_offset', $1)
    ON CONFLICT (key) DO UPDATE
      SET value = $1
      WHERE reviews.key_value.key = 'tg_update_offset';
    """
    await conn.execute(_set_tg_update_offset, value)


async def get_times(
        login: str, date_from: dt.datetime, date_to: dt.datetime, conn,
) -> tp.List[int]:
    _get_reviewer_times_query = """
    SELECT ARRAY(
      SELECT minutes
      FROM reviews.review_stats
      WHERE reviewer = $1
        AND review_at BETWEEN $2 AND $3
    );
    """
    result = await conn.fetchrow(
        _get_reviewer_times_query, login, date_from, date_to,
    )
    return result['array'] if result and 'array' in result else []


async def save_user_chat_id(telegram_login: str, chat_id: str, conn) -> None:
    _save_chat_id_query = """
    INSERT INTO reviews.users_telegrams (telegram_login, chat_id)
    VALUES ($1, $2)
    ON CONFLICT DO NOTHING;
    """
    await conn.execute(_save_chat_id_query, telegram_login, int(chat_id))


async def save_user_mappings(
        staff_login: str, telegram_login: str, chat_id: tp.Optional[str], conn,
) -> None:
    _save_user_mappings_query = """
    WITH logins_query AS (
      INSERT INTO reviews.users_logins (staff_login, telegram_login)
      VALUES ($1, $2)
      ON CONFLICT (staff_login) DO UPDATE
        SET telegram_login = $2
        WHERE reviews.users_logins.staff_login = $1
    )

    INSERT INTO reviews.users_telegrams (telegram_login, chat_id)
    VALUES ($2, $3)
    ON CONFLICT DO NOTHING;
    """

    _save_login_mappings_query = """
    INSERT INTO reviews.users_logins (staff_login, telegram_login)
    VALUES ($1, $2)
    ON CONFLICT (staff_login) DO NOTHING;
    """

    if chat_id:
        await conn.execute(
            _save_user_mappings_query,
            staff_login,
            telegram_login,
            int(chat_id),
        )
    else:
        await conn.execute(
            _save_login_mappings_query, staff_login, telegram_login,
        )


async def delete_user_mappings(telegram_login: str, conn) -> None:
    _delete_user_mappings_query = """
    WITH logins_query AS (
      DELETE FROM reviews.users_logins
      WHERE telegram_login = $1
    )

    DELETE FROM reviews.users_telegrams
    WHERE telegram_login = $1;
    """
    await conn.execute(_delete_user_mappings_query, telegram_login)


async def delete_users_mappings(staff_logins: tp.Iterable[str], conn) -> None:
    _delete_users_mappings_query = """
    WITH
    telegram_logins AS (
      SELECT telegram_login
      FROM reviews.users_logins
      WHERE staff_login = ANY($1)
    ),
    chat_ids_delete AS (
      DELETE FROM reviews.users_telegrams
      WHERE telegram_login IN (
        SELECT telegram_login
        FROM telegram_logins
      )
    ),
    logins_delete AS (
      DELETE FROM reviews.users_logins
      WHERE telegram_login IN (
        SELECT telegram_login
        FROM telegram_logins
      )
    )
    DELETE FROM reviews.users_settings
    WHERE staff_login = ANY($1::TEXT[]);
    """
    await conn.execute(_delete_users_mappings_query, staff_logins)


async def get_chat_id(telegram_login: str, conn) -> tp.Optional[str]:
    _get_chat_id_query = """
    SELECT chat_id
    FROM reviews.users_telegrams
    WHERE telegram_login = $1;
    """
    row = await conn.fetchrow(_get_chat_id_query, telegram_login)
    if not row:
        return None
    as_int = row.get('chat_id')
    if not as_int:
        return None
    return str(as_int)


async def get_staff_login_pg(telegram_login: str, conn) -> str:
    _get_staff_login_query = """
    SELECT staff_login
    FROM reviews.users_logins
    WHERE telegram_login = $1;
    """
    row = await conn.fetchrow(_get_staff_login_query, telegram_login)
    return row.get('staff_login') if row else None


async def get_all_staff_logins(conn) -> dict:
    _get_all_staff_logins_query = """
    SELECT staff_login, telegram_login
    FROM reviews.users_logins;
    """
    rows = await conn.fetch(_get_all_staff_logins_query)
    return {row['staff_login']: row['telegram_login'] for row in rows}


async def get_telegram_login_pg(staff_login: str, conn) -> str:
    _get_telegram_login_query = """
    SELECT telegram_login
    FROM reviews.users_logins
    WHERE staff_login = $1;
    """
    row = await conn.fetchrow(_get_telegram_login_query, staff_login)
    return row.get('telegram_login') if row else None


async def disable_notifications(staff_login: str, conn) -> None:
    _disable_notifications_query = """
    UPDATE reviews.users_settings
       SET review_notify_enabled = FALSE
     WHERE staff_login = $1;
    """
    await conn.execute(_disable_notifications_query, staff_login)


async def set_myprs(value: bool, staff_login: str, conn) -> None:
    _set_myprs_query = """
    UPDATE reviews.users_settings
       SET my_prs = $1
     WHERE staff_login = $2;
    """
    await conn.execute(_set_myprs_query, value, staff_login)


async def set_wipprs(value: bool, staff_login: str, conn) -> None:
    _set_wipprs_query = """
    UPDATE reviews.users_settings
       SET wip_prs = $1
     WHERE staff_login = $2;
    """
    await conn.execute(_set_wipprs_query, value, staff_login)


async def set_startrek(value: bool, staff_login: str, conn) -> None:
    _set_startrek_query = """
    UPDATE reviews.users_settings
       SET startrek = $1
     WHERE staff_login = $2;
    """
    await conn.execute(_set_startrek_query, value, staff_login)


async def set_hours(hours: tp.Iterable[int], staff_login: str, conn) -> None:
    _set_hours_query = """
    INSERT INTO reviews.users_settings
      (staff_login, review_notify_hours, review_notify_enabled)
    VALUES ($1, $2, TRUE)
    ON CONFLICT (staff_login) DO UPDATE
      SET review_notify_enabled = TRUE,
          review_notify_hours = $2
    WHERE reviews.users_settings.staff_login = $1;
    """
    await conn.execute(_set_hours_query, staff_login, hours)


async def get_reviewers_settings(conn) -> tp.Dict[str, tp.Dict]:
    _get_reviewers_query = """
    SELECT staff_login, review_notify_hours, my_prs, wip_prs, startrek
    FROM reviews.users_settings
    WHERE review_notify_enabled;
    """
    rows = await conn.fetch(_get_reviewers_query)
    return {
        login: {
            'hours': hours,
            'my': my_prs,
            'wip': wip_prs,
            'startrek': startrek,
        }
        for login, hours, my_prs, wip_prs, startrek in rows
    }


async def get_reviewer_settings(
        staff_login: str, conn,
) -> tp.Optional[tp.Dict]:
    _get_reviewer_query = """
    SELECT review_notify_hours, my_prs, wip_prs
    FROM reviews.users_settings
    WHERE staff_login = $1;
    """
    row = await conn.fetchrow(_get_reviewer_query, staff_login)
    if not row:
        return None

    return {'hours': row[0], 'my': row[1], 'wip': row[2]}


async def set_gaps(
        staff_login: str,
        gaps: tp.List[tp.Tuple[dt.datetime, dt.datetime]],
        conn,
) -> None:
    json_gaps = [
        {'begin': begin.isoformat(), 'end': end.isoformat()}
        for begin, end in gaps
    ]

    _set_gaps_query = """
    INSERT INTO reviews.cache_gaps
      (staff_login, gaps)
    VALUES ($1, $2::JSONB)
    ON CONFLICT (staff_login) DO UPDATE
      SET gaps = $2::JSONB
    WHERE reviews.cache_gaps.staff_login = $1;
    """
    await conn.execute(_set_gaps_query, staff_login, json.dumps(json_gaps))


async def get_gaps(
        staff_login: str, conn,
) -> tp.List[tp.Tuple[dt.datetime, dt.datetime]]:
    _get_gaps_query = """
    SELECT gaps
    FROM reviews.cache_gaps
    WHERE staff_login = $1;
    """
    row = await conn.fetchrow(_get_gaps_query, staff_login)
    if not row:
        return []

    return [
        (
            dt.datetime.fromisoformat(gap['begin']),
            dt.datetime.fromisoformat(gap['end']),
        )
        for gap in json.loads(row['gaps'])
    ]


async def set_subordinated(
        staff_login: str,
        sub_nearest: tp.List[str],
        sub_all: tp.List[str],
        conn,
) -> None:
    _set_subordinated_query = """
    INSERT INTO reviews.subordinated
      (staff_login, sub_nearest, sub_all)
    VALUES ($1, $2, $3)
    ON CONFLICT (staff_login) DO UPDATE
      SET sub_nearest = $2::TEXT[],
          sub_all = $3::TEXT[]
    WHERE reviews.subordinated.staff_login = $1;
    """
    await conn.execute(
        _set_subordinated_query, staff_login, sub_nearest, sub_all,
    )


async def get_subordinated(
        staff_login: str, conn,
) -> tp.Optional[tp.Tuple[tp.Set[str], tp.Set[str]]]:
    _get_subordinated_query = """
    SELECT sub_nearest, sub_all
    FROM reviews.subordinated
    WHERE staff_login = $1;
    """
    result = await conn.fetchrow(_get_subordinated_query, staff_login)
    if not result:
        return None

    return set(result['sub_nearest']), set(result['sub_all'])


async def get_nda_link(link: str, conn) -> tp.Optional[str]:
    _get_nda_link_query = """
    SELECT nda
    FROM reviews.nda_links
    WHERE url = $1;
    """
    row = await conn.fetchrow(_get_nda_link_query, link)
    return row[0] if row else None


async def save_nda_link(link: str, nda: str, conn) -> None:
    _save_nda_link_query = """
    INSERT INTO reviews.nda_links (url, nda)
    VALUES ($1, $2)
    ON CONFLICT DO NOTHING;
    """
    return await conn.execute(_save_nda_link_query, link, nda)
