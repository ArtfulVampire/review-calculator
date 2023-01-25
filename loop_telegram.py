import logging

import callbacks
import reviews
import staff
import storage
import telegram


logger = logging.getLogger()


async def _get_auth_staff_login(telegram_login: str, chat_id: str, ctx) -> str:
    staff_login = await staff.get_staff_login(telegram_login, ctx)
    if not staff_login:
        await telegram.send_message(telegram.unauth_message(), chat_id, ctx)
    return staff_login


async def process_telegram_input(ctx):
    async with ctx.pool.acquire() as conn:
        offset = await storage.get_tg_update_offset(conn)
        if not offset:
            logger.error('Failed to get telegram offset, set 0')
            offset = 0

        updates = await telegram.get_updates(offset, ctx)

        if not updates:
            # logger.debug('Empty telegram updates')
            return

        for update in updates:
            chat_id = update.chat_id  # str
            if not chat_id:
                logger.error(f'cannot process update: {update}')
                continue

            tg_login = update.telegram_login
            await storage.save_user_chat_id(tg_login, chat_id, conn)

            # request for authentification
            if update.text == '/start':
                staff_login, is_registered = await staff.register_user(
                    tg_login, chat_id, ctx,
                )
                logger.info(
                    f'login = {staff_login}, is_registered = {is_registered}',
                )
                if not staff_login:  # telegram_login not found on staff
                    await telegram.send_message(
                        await telegram.intruder_message(), chat_id, ctx,
                    )
                    continue

                await telegram.send_message(
                    await telegram.hello_message(
                        staff_login, is_registered, ctx,
                    ),
                    chat_id,
                    ctx,
                )
                logger.info(f'login = {staff_login}, set 1 hour notifications')
                await callbacks.set_notifications(staff_login, 1, chat_id, ctx)
                continue

            staff_login: str = await _get_auth_staff_login(
                tg_login, chat_id, ctx,
            )
            if not staff_login:  # unauthentificated request
                continue

            # authenticated requests
            if update.is_callback:
                # logger.debug(f'callback_data = {update.callback_data}')
                index = update.callback_data.rfind('_')
                action_name = update.callback_data[:index]
                action_value = int(update.callback_data[index + 1 :])
                logger.info(
                    f'invoke callback: name = {action_name}, '
                    f'value = {action_value}, '
                    f'index = {index}',
                )
                await callbacks.invoke_callback(
                    action_name, action_value, staff_login, chat_id, ctx,
                )

            elif update.text == '/get_stats':
                await telegram.ask_for_stats(chat_id, ctx)

            elif update.text == '/get_subordinated_stats':
                await telegram.ask_for_subordinated_stats(chat_id, ctx)

            elif update.text == '/my_settings':
                await telegram.ask_for_settings(chat_id, ctx)

            elif update.text == '/show_reviewed':
                await telegram.ask_for_reviewed(chat_id, ctx)

            elif update.text == '/what_can_i_review':
                await telegram.ask_for_open_reviews(chat_id, ctx)

            elif update.text == '/get_requested_reviews':
                res = await reviews.show_requested(
                    staff_login, chat_id, False, ctx,
                )
                if not res:
                    await telegram.send_message(
                        'Nothing to show', chat_id, ctx,
                    )

            elif update.text == '/get_current_reviews':
                res = await reviews.get_current(staff_login, chat_id, ctx)
                if not res:
                    await telegram.send_message(
                        'Nothing to show', chat_id, ctx,
                    )

            elif update.text == '/stop':
                await staff.deregister_user(tg_login, ctx)
                await telegram.send_message(
                    await telegram.goodbye_message(staff_login, ctx),
                    chat_id,
                    ctx,
                )

        await storage.set_tg_update_offset(
            str(updates[-1].update_id + 1), conn,
        )
