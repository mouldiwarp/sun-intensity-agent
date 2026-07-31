import argparse
import json
import sys

from .core import get_score
from .errors import OWMError, format_error_response
from .constants import CLI_EXIT_SUCCESS, CLI_EXIT_ERROR, CLI_EXIT_UNEXPECTED_ERROR


def main() -> None:
    """Run the CLI application."""
    parser = argparse.ArgumentParser(description="Sun intensity score from OpenWeatherMap")
    parser.add_argument("--lat", type=float, help="Override latitude from OWM_LAT env var")
    parser.add_argument("--lon", type=float, help="Override longitude from OWM_LON env var")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")

    args = parser.parse_args()

    try:
        result = get_score(lat=args.lat, lon=args.lon)
        output = json.dumps(result, indent=2 if args.pretty else None)
        print(output)
        sys.exit(CLI_EXIT_SUCCESS)

    except (OWMError, ValueError) as e:
        error_response = format_error_response(e)
        print(json.dumps(error_response), file=sys.stderr)
        sys.exit(CLI_EXIT_ERROR)

    except Exception as e:
        error_response = format_error_response(e)
        print(json.dumps(error_response), file=sys.stderr)
        sys.exit(CLI_EXIT_UNEXPECTED_ERROR)


if __name__ == "__main__":
    main()
