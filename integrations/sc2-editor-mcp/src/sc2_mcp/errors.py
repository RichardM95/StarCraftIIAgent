class SC2Error(Exception):
    """An actionable, structured domain error."""

    def __init__(self, code: str, message: str, **details):
        super().__init__(message)
        self.code = code
        self.details = details

    def as_dict(self):
        return {"code": self.code, "message": str(self), "details": self.details}
