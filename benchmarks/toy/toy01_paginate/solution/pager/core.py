def page_count(total: int, per_page: int) -> int:
    """Number of pages needed to show `total` items, `per_page` per page."""
    if per_page <= 0:
        raise ValueError("per_page must be positive")
    return (total + per_page - 1) // per_page


def get_page(items: list, page: int, per_page: int) -> list:
    """Return the items on 1-based `page`."""
    pages = page_count(len(items), per_page)
    if page < 1 or page > max(pages, 1):
        raise ValueError("page out of range")
    start = (page - 1) * per_page
    return items[start : start + per_page]
