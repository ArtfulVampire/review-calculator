_REQUIRED_RESPONSE_TPL: str = (
    'https://st.yandex-team.ru/issues/?_q='
    '%22Pending+reply+from%22%3A+%22{0}%40%22'
    '+%22Resolution%22%3A+empty()'
    '+%22Sort+by%22%3A+Updated+DESC'
)

TAGS_WIKI: str = 'https://wiki.yandex-team.ru/taxi/partnerproducts/txmsttags/'

_PRODUCT_TAGS: list = [
    'Quality',
    'Tariffs',
    'Retention',
    'Acquisition',
    'Efficiency',
    'Safety',
    'New_Businesses',
    'Support',
    'Selfemployed',
    'Product',
    'CI',
    'ISS',
    'ui_test',
    'Taximeter_techno',
]


_TAXIMETER_NOTAG_TPL: str = (
    'https://st.yandex-team.ru/issues/'
    '?_q=Queue%3A+TAXIMETERBACK'
    '+Resolution%3A+Fixed'
    '+Resolved%3A+>%3D"2020-06-01+00%3A00%3A00"'
    f'{"".join([f"+Tags%3A+!+{tag}" for tag in _PRODUCT_TAGS])}'
    '+Assignee%3A+{0}'
)


def get_required_response_link(staff_login: str) -> str:
    return _REQUIRED_RESPONSE_TPL.format(staff_login)


def get_notag_link(staff_login: str) -> str:
    return _TAXIMETER_NOTAG_TPL.format(staff_login)
