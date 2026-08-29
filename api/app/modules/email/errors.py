class EmailError(Exception):
    pass


class EmailNotConfigured(EmailError):
    pass


class EmailSendError(EmailError):
    pass
