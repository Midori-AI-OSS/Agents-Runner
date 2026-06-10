from __future__ import annotations
from typing import Any


class FakeSignal:
    def connect(self, *args: Any, **kwargs: Any) -> None:
        return

    def disconnect(self, *args: Any, **kwargs: Any) -> None:
        return

    def emit(self, *args: Any, **kwargs: Any) -> None:
        return


class FakeThread:
    def __init__(self, parent: Any = None) -> None:
        self.started = FakeSignal()
        self.finished = FakeSignal()

    def start(self) -> None:
        pass

    def quit(self) -> None:
        pass

    def deleteLater(self) -> None:
        pass


class FakePrepWorker:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass


class FakePrepBridge:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass
