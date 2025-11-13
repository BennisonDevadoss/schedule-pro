import math


def create_paginator_type(
    total: int,
    per_page: int,
    end_at: int,
    start_at: int,
    prev_page: int,
    total_pages: int,
    current_page: int,
    is_next_page: bool,
    is_last_page: bool,
    is_first_page: bool,
    next_page: int | None,
) -> dict[str, int | bool | None]:
    return {
        "total": total,
        "end_at": end_at,
        "start_at": start_at,
        "per_page": per_page,
        "prev_page": prev_page,
        "total_pages": total_pages,
        "current_page": current_page,
        "is_next_page": is_next_page,
        "is_last_page": is_last_page,
        "is_first_page": is_first_page,
        "next_page": next_page,
    }


def paginator_result(
    count: int, page: int, per_page: int
) -> dict[str, int | bool | None]:
    start_at = (page - 1) * per_page + 1
    end = page * per_page
    end_at = count if count < end else end

    return {
        "total": count,
        "per_page": per_page,
        "end_at": end_at,
        "start_at": start_at,
        "current_page": page,
        "prev_page": page - 1,
        "next_page": page + 1 if page + 1 <= math.ceil(count / per_page) else None,
        "total_pages": (count // per_page) + (1 if count % per_page != 0 else 0),
        "is_next_page": page + 1 <= math.ceil(count / per_page),
        "is_first_page": page == 1,
        "is_last_page": per_page * page >= count,
    }


def paginate(
    paginate_result: dict[str, int | bool | None], data: list, name: str
) -> dict[str, dict[str, int | bool | None] | list]:
    return {name: data, "pagination": paginate_result}
