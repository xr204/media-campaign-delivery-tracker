import argparse
from media_campaign import InfraiClient, campaign_snapshot, deliver_to_creator, ingest_asset, process_asset


def main() -> None:
    parser = argparse.ArgumentParser(description="Deliver a processed media asset and inspect opens.")
    parser.add_argument("--to", required=True, help="creator email")
    parser.add_argument("--creator", default="Creator")
    parser.add_argument("--asset", default="episode-001")
    args = parser.parse_args()
    asset = ingest_asset(args.asset, "Campaign episode", "https://media.example/episode-001")
    job = process_asset(asset)
    delivery = deliver_to_creator(InfraiClient(), job, args.creator, args.to)
    print(campaign_snapshot(InfraiClient(), delivery))


if __name__ == "__main__":
    main()
