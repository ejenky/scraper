"""Vertical definitions with search queries."""
from __future__ import annotations

VERTICALS: dict[str, dict] = {
    "casino": {
        "queries": [
            "online casino affiliate program",
            "igaming operator marketing partnership",
            "casino brand influencer program",
            "new online casino launch 2025 2026",
            "online casino media buying agency",
            "casino operator hiring media buyer",
            "white label casino marketing",
            "igaming company seeking affiliates",
            "online slots brand partnership",
            "live casino operator marketing contact",
            "casino operator social media marketing",
            "igaming growth marketing",
        ],
        "directories": [
            "https://www.askgamblers.com/online-casinos/all",
            "https://www.casino.org/online-casinos/",
            "https://www.casinomeister.com/",
        ],
        "maps_queries": [
            "online casino company",
            "igaming operator",
            "gambling software company",
        ],
        "play_store_queries": [
            "casino slots",
            "online casino",
            "live casino",
            "poker",
        ],
    },
    "sports_betting": {
        "queries": [
            "sports betting affiliate program",
            "sportsbook operator marketing partnership",
            "sports betting app influencer marketing",
            "new sportsbook brand 2025 2026",
            "sports betting media buying",
            "esports betting operator affiliate",
            "sports betting company hiring growth",
            "sportsbook operator social media",
        ],
        "directories": [],
        "maps_queries": ["sports betting company", "sportsbook operator"],
        "play_store_queries": ["sports betting", "sportsbook", "esports betting"],
    },
    "crypto": {
        "queries": [
            "crypto exchange affiliate program",
            "crypto casino marketing partnership",
            "crypto sports betting operator affiliate",
            "defi platform marketing contact",
            "web3 gaming marketing partnership",
            "crypto trading platform media buying",
            "crypto prediction market affiliate",
            "blockchain gaming influencer program",
            "crypto exchange hiring growth marketing",
            "nft marketplace affiliate program",
        ],
        "directories": [],
        "maps_queries": ["cryptocurrency company", "crypto exchange"],
        "play_store_queries": ["crypto trading", "crypto casino", "web3 game"],
    },
    "mobile_games": {
        "queries": [
            "mobile game publisher user acquisition",
            "mobile game studio media buying",
            "hyper casual game publisher marketing",
            "mobile game influencer marketing program",
            "mobile game user acquisition manager hiring",
            "indie game publisher marketing contact",
            "mobile game studio partnership",
            "casual game developer affiliate",
        ],
        "directories": [],
        "maps_queries": ["mobile game studio", "game development company"],
        "play_store_queries": [
            "idle game",
            "casual game",
            "strategy game",
            "RPG mobile",
            "puzzle game",
        ],
    },
    "apps": {
        "queries": [
            "mobile app user acquisition partnership",
            "fintech app influencer marketing",
            "social app media buying",
            "dating app marketing partnership",
            "health fitness app user acquisition",
            "vpn app affiliate program",
            "trading app affiliate program",
            "app growth agency partner",
        ],
        "directories": [],
        "maps_queries": ["mobile app company", "app development studio"],
        "play_store_queries": ["fintech app", "dating app", "vpn app", "trading app"],
    },
    "prediction_markets": {
        "queries": [
            "prediction market platform affiliate",
            "prediction market marketing partnership",
            "fantasy sports operator affiliate",
            "prediction market influencer program",
            "binary options affiliate program",
            "event betting platform marketing",
        ],
        "directories": [],
        "maps_queries": ["prediction market company"],
        "play_store_queries": ["prediction market", "fantasy sports", "event betting"],
    },
    "esports": {
        "queries": [
            "esports organization sponsorship partnership",
            "esports team marketing partnership",
            "esports betting operator affiliate program",
            "esports tournament marketing partner",
        ],
        "directories": [],
        "maps_queries": ["esports organization"],
        "play_store_queries": ["esports"],
    },
    "fantasy_sports": {
        "queries": [
            "fantasy sports operator affiliate program",
            "daily fantasy sports marketing partnership",
            "fantasy sports app user acquisition",
        ],
        "directories": [],
        "maps_queries": ["fantasy sports company"],
        "play_store_queries": ["fantasy sports", "daily fantasy"],
    },
}


# Target decision-maker titles
TARGET_TITLES = [
    # C-suite
    "ceo", "cmo", "coo", "cto", "founder", "co-founder",
    # Marketing leadership
    "vp marketing", "head of marketing", "director of marketing",
    "marketing director", "chief marketing officer",
    # Growth
    "vp growth", "head of growth", "growth director", "growth lead",
    # User acquisition
    "head of ua", "ua manager", "ua director", "user acquisition",
    # Media buying
    "media buyer", "media buying", "head of media",
    "performance marketing", "paid media",
    # Partnerships / BD
    "head of partnerships", "partnership manager", "partnerships director",
    "head of affiliates", "affiliate manager",
    "business development", "bd manager", "bd director",
    # General marketing
    "marketing manager", "digital marketing manager",
]
