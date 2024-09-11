import logging

FORMAT = logging.Formatter(
    '[%(asctime)s] [%(levelname)s]: [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


class Logger(logging.Logger):
    def __init__(self, name: str):
        super().__init__(name)

        # logger
        self.debug_mode = False
        self.setLevel(logging.INFO)

        # console handler
        self.ch = logging.StreamHandler()
        self.ch.setLevel(logging.INFO)
        self.ch.setFormatter(FORMAT)
        self.addHandler(self.ch)

    def set_debug(self, debug: bool = False) -> None:
        """
        Set debug mode to on or off.
        :param debug: Turn on debug mode if it is True, off otherwise.
        """
        if debug:
            self.debug_mode = True
            self.setLevel(logging.DEBUG)
            self.ch.setLevel(logging.DEBUG)
        else:
            self.debug_mode = False
            self.setLevel(logging.INFO)
            self.ch.setLevel(logging.INFO)
