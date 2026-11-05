"""How long to wait between tries."""


def waits(tries):
    return [2 ** max(number - 1, 0) for number in range(tries)]
