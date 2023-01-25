PARAMS_KEY = '__params'


# c: {__params: {a: 1, b: 'ASC'}} is serialized as 'c(a:1, b:ASC)'
def serialize_params(params: dict, with_comma: bool) -> str:
    result: str = ''
    for key, val in params.items():
        result += f'{key}:'

        if isinstance(val, list) and val and isinstance(val[0], str):
            result += '['
            # a hack for list enum - no quotes
            # lists of strings are not used in the project
            result += ', '.join(val)
            result += ']'
        elif isinstance(val, str):
            if val.isupper():  # a hack for enum
                result += f'{val}'
            else:
                result += f'"{val}"'
        elif isinstance(val, dict):
            result += ' { '
            result += serialize_params(params=val, with_comma=False)
            result += '} '
        else:
            result += f'{val}'
        result += ', ' if with_comma else ' '
    return result[:-2] if with_comma else result


def serialize_request(data: dict, indent: int, is_pretty: bool) -> str:
    result: str = ''
    _indent = ' ' * 2 if is_pretty else ''
    _newline = '\n' if is_pretty else ' '

    for key, val in data.items():
        result += _indent * indent + f'{key}'

        if not val:
            result += _newline
            continue

        if PARAMS_KEY in val:
            params = serialize_params(params=val[PARAMS_KEY], with_comma=True)
            result += f'({params})'
            val.pop(PARAMS_KEY)

        if not val:
            result += _newline
            continue

        result += ' {' + _newline
        result += serialize_request(val, indent + 1, is_pretty)
        result += _indent * indent + '}' + _newline
    return result


def graphql_query(data: dict) -> dict:
    query = serialize_request(data=data, indent=1, is_pretty=False)
    return {'query': query}


def unittest():
    input_data = {
        'a': {
            'b': {'c': {}},
            'd': {
                PARAMS_KEY: {
                    'p1': 1,
                    'p2': 'string',
                    'p3': ['s1', 's2', 's3'],
                    'p4': [5, 6, 7],
                },
                'e': {},
                'f': {'g': {}},
            },
            'h': {PARAMS_KEY: {'p1': 100}},
        },
    }
    expected: str = """a {
  b {
    c
  }
  d(p1:1, p2:"string", p3:[s1, s2, s3], p4:[5, 6, 7]) {
    e
    f {
      g
    }
  }
  h(p1: 100)
}"""

    assert expected == serialize_request(
        data=input_data, indent=1, is_pretty=True,
    )
