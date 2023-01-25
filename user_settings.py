import typing as tp

import storage


async def disable_notifications(staff_login: str, ctx) -> None:
    await storage.disable_notifications(staff_login, ctx.conn)


async def set_hours(hours: tp.Iterable[int], staff_login: str, ctx) -> None:
    await storage.set_hours(hours, staff_login, ctx.conn)
