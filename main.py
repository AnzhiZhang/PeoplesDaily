import os
import uuid
import argparse

from src.peoples_daily import TodayPeopleDaily


def write_multiline_output(fh, name, value):
    delimiter = uuid.uuid4()
    print(f'{name}<<{delimiter}', file=fh)
    print(value, file=fh)
    print(delimiter, file=fh)


def main():
    # setup parser
    parser = argparse.ArgumentParser(
        description="Get today people's daily",
    )
    parser.add_argument(
        "--write-github-output",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Write GitHub output",
    )

    # parse arguments
    args = parser.parse_args()
    write_github_output = args.write_github_output

    # get today peoples daily
    today_peoples_daily = TodayPeopleDaily()
    today_peoples_daily.get_today_peoples_daily()

    # set output
    if write_github_output:
        with open(os.environ['GITHUB_OUTPUT'], 'a') as fh:
            for name, value in today_peoples_daily.data.items():
                if '\n' in value:
                    write_multiline_output(fh, name, value)
                else:
                    print(f'{name}={value}', file=fh)


if __name__ == '__main__':
    main()
