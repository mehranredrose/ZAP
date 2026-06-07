from rest_framework.pagination import CursorPagination as DRFCursorPagination


class CursorPagination(DRFCursorPagination):
    """
    Cursor-based pagination for all list endpoints.
    Offset pagination is NOT used — it degrades catastrophically at scale
    (OFFSET 1000000 requires the DB to scan 1M rows).
    """
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
    ordering = "-created_at"