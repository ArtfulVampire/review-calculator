import logging

import storage

NDA_API_PREFIX = 'https://nda.ya.ru/--'


logger = logging.getLogger()


async def get_link(link: str, ctx) -> str:
    async with ctx.pool.acquire() as conn:
        from_db = await storage.get_nda_link(link, conn)
        if from_db:
            logger.debug(f'return link from db : {from_db}')
            return from_db

        return link

        # TODO request access in Firewall service to nda
        result: str = ''
        try:
            response = await ctx.session.get(
                NDA_API_PREFIX, params={'url': link},
            )
            result = await response.text()
        except BaseException:
            logger.warning(
                f'exception in nda api, return non-nda link: {link}',
            )
            return link

        logger.debug(f'return link from api : {result}')
        await storage.save_nda_link(link, result, conn)
        return result
