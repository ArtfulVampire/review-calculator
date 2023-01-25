ENDPOINT = 'https://api.github.com/graphql'


async def perform_request(graphql_query: dict, ctx) -> dict:
    # TODO add 304 processing and stuff by the github API documentation
    response = await ctx.session.post(
        ENDPOINT,
        json=graphql_query,
        headers={'Authorization': f'Bearer {ctx.github_token}'},
    )
    response_json = await response.json()
    print(f'response_code={response.status}')

    return response_json
