import subprocess

import vault_client

SECRET_ID = 'sec-01ea8pyb1a071eptcask7tf1gn'

def load_secrets() -> dict:
    yav_token: str = subprocess.run(
        ['yav', 'oauth'], capture_output=True,
    ).stdout.decode('ascii').strip()

    client = vault_client.instances.Production(
        authorization=yav_token, decode_files=True,
    )

    values: dict = client.get_version(SECRET_ID)['value']
    return {
        'github_token': values['value3'],
        'tg_token': values['value4_v2'],
        'staff_token': values['value5'],
        'pg_dsn': {
            'host': 'localhost',
            'user': values['value1'],
            'password': values['value2'],
            'port': 5432,
            'database': 'github_calculator',
        },
    }
