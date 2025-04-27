import traceback


class Error:
    def __init__(self, message):
        self.message = message
        self.exc_message = traceback.format_exc()

    def __str__(self):
        s = self.message
        if not "NoneType: None" in self.exc_message:
            s += "\n"
            s += "---------- Message for developers ----------\n"
            s += self.exc_message
            s += "--------------------------------------------"
        return s
