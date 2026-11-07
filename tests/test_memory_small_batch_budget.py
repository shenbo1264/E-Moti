from decimal import Decimal

import pytest

from tools.eval_memory_small_batch import reserve_request, usage_cost


def payload(**changes):
    return {'model': 'deepseek-flash', 'messages': [{'role': 'user', 'content': '一次小批量验证'}],
            'max_tokens': 4096, **changes}


def test_reservation_counts_utf8_and_maximum_output():
    cost = reserve_request(payload(), Decimal('0'), 0)
    assert Decimal('0.034') < cost < Decimal('0.04')


@pytest.mark.parametrize('body,reserved,calls', [
    (payload(), Decimal('0'), 10),
    (payload(), Decimal('0.49'), 0),
    (payload(model='deepseek-v4-pro'), Decimal('0'), 0),
    (payload(max_tokens=4097), Decimal('0'), 0),
    (payload(tools=[{'type': 'function'}]), Decimal('0'), 0),
])
def test_reject_before_network_when_limits_exceeded(body, reserved, calls):
    with pytest.raises(ValueError):
        reserve_request(body, reserved, calls)


def test_weekend_accounting_uses_cached_and_uncached_usage_separately():
    row = {'requested_at_utc': '2026-11-07T14:00:00+00:00', 'provider_response': {'usage': {
        'prompt_tokens': 1000, 'prompt_cache_hit_tokens': 400, 'prompt_cache_miss_tokens': 600,
        'completion_tokens': 100}}}
    assert usage_cost([row]) == '0.001008'
