from time import perf_counter


class Timer:
    def __enter__(self) -> "Timer":
        self.started = perf_counter()
        self.elapsed_ms = 0.0
        return self

    def __exit__(self, *_: object) -> None:
        self.elapsed_ms = round((perf_counter() - self.started) * 1000, 2)
