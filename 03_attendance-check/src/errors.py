"""例外階層（docs/03_spec.md §8）。"""


class DemoError(Exception):
    """本デモの全例外の基底。"""

    exit_code: int = 1


class InputSchemaError(DemoError):
    """CSV ヘッダが必須列を満たさない等。"""

    exit_code = 1


class DataClassGuardError(DemoError):
    """--data-class ガード違反。"""

    exit_code = 2


class DateValidationError(DemoError):
    """--month / --as-of-date の書式不正。"""

    exit_code = 2


class SamplesDirectoryNotFoundError(DemoError):
    exit_code = 1


class OutputPathViolationError(DemoError):
    """出力先が output/ 配下を逸脱した場合に送出。"""

    exit_code = 1
