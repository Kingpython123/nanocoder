from shop.pricing import apply_discount


def test_percent():
    assert apply_discount(200, 15) == 170.0


def test_zero_and_full():
    assert apply_discount(80, 0) == 80
    assert apply_discount(80, 100) == 0
