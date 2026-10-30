from shop.checkout import cart_total


def test_no_discount():
    assert cart_total([(10.0, 2), (5.0, 1)]) == 25.0


def test_discount():
    assert cart_total([(10.0, 2), (5.0, 1)], percent=20) == 20.0
