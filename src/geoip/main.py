import os


GRANIAN_ARGS = [
    "granian",
    "--interface",
    "asgi",
    "--host",
    "0.0.0.0",
    "--port",
    "8000",
    "--reload",
    "geoip.app:app",
]


def main() -> None:
    os.execvp("granian", GRANIAN_ARGS)


if __name__ == "__main__":
    main()
