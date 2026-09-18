from app.core.exceptions import AppError


class FinancialError(AppError):
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(code=code, message=message, status_code=status_code)


def fin_error(code: str, message: str, status_code: int = 400) -> FinancialError:
    return FinancialError(code, message, status_code)
