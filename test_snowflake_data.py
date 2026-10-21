
from src.db import fetch_opportunities


def main():
    opportunities = fetch_opportunities()

    print("Successfully queried Snowflake.")
    print(f"Records returned: {len(opportunities)}")

    for opportunity in opportunities[:3]:
        print(
            f"- {opportunity['title']} "
            f"[{opportunity['verification_status']}]"
        )


if __name__ == "__main__":
    main()
