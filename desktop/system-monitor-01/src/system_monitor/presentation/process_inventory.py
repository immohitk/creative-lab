
"""Pure filtering and sorting logic for the process inventory."""

from collections.abc import Mapping, Sequence


SORT_KEYS = (
    "name",
    "pid",
    "category",
    "cpu_percent",
    "memory_bytes",
    "status",
    "executable_path",
)

CATEGORY_FILTERS = (
    "All",
    "System",
    "Service",
    "Application",
    "Unclassified",
)


def filter_and_sort_processes(
    processes: Sequence,
    classifications: Mapping,
    *,
    search_text: str = "",
    category: str = "All",
    sort_key: str = "cpu_percent",
    descending: bool = True,
) -> list:
    """Filter all processes and return them in the requested sort order."""

    if sort_key not in SORT_KEYS:
        raise ValueError(f"Unsupported process sort key: {sort_key}")

    if category not in CATEGORY_FILTERS:
        raise ValueError(f"Unsupported process category: {category}")

    if not isinstance(search_text, str):
        raise TypeError("Search text must be a string.")

    query = search_text.strip().casefold()
    filtered = []

    for process in processes:
        classification = classifications.get(process.pid)
        process_category = (
            classification.category
            if classification is not None
            else "Unclassified"
        )

        if category != "All" and process_category != category:
            continue

        executable_path = (
            getattr(process, "executable_path", None) or ""
        )

        if query:
            searchable = (
                process.name,
                str(process.pid),
                executable_path,
            )

            if not any(
                query in value.casefold()
                for value in searchable
            ):
                continue

        filtered.append((process, process_category))

    def value(item):
        process, process_category = item

        if sort_key == "name":
            return process.name.casefold()
        if sort_key == "pid":
            return process.pid
        if sort_key == "category":
            return process_category.casefold()
        if sort_key == "cpu_percent":
            return process.cpu_percent
        if sort_key == "memory_bytes":
            return process.memory_bytes
        if sort_key == "status":
            return process.status.casefold()

        executable_path = getattr(process, "executable_path", None)
        return executable_path.casefold() if executable_path else None

    available = [
        item for item in filtered
        if value(item) is not None
    ]
    unavailable = [
        item for item in filtered
        if value(item) is None
    ]

    if sort_key == "cpu_percent":
        # Establish deterministic tie-breakers first.
        available.sort(
            key=lambda item: (
                -item[0].memory_bytes,
                item[0].pid,
            )
        )
        # Stable sorting preserves memory-descending tie order.
        available.sort(
            key=lambda item: item[0].cpu_percent,
            reverse=descending,
        )
    else:
        available.sort(
            key=value,
            reverse=descending,
        )

    return [
        process
        for process, _category in available + unavailable
    ]
