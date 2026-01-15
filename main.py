import sys

from agents_runner.app import run_app


def main() -> None:
    try:
        run_app(sys.argv)
    except Exception as error:
        print(str(error))


if __name__ == "__main__":
    main()
