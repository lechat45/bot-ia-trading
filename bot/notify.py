"""Notifications sur le téléphone avec ntfy (gratuit, sans compte : https://ntfy.sh).

Installe l'application ntfy, abonne-toi à un nom de « sujet » difficile à deviner
(ex. bot-ia-trading-7f3k9q), puis mets ce nom dans la variable NTFY_TOPIC (.env en local,
Secret GitHub pour l'hébergement). Sans NTFY_TOPIC, rien n'est envoyé.
"""
import logging
import os

import requests

log = logging.getLogger("notif")


def send(titre: str, message: str, tags: str = "chart_with_upwards_trend", priorite: str = "default") -> None:
    topic = os.getenv("NTFY_TOPIC", "").strip()
    if not topic or os.getenv("NOTIFY_DISABLED"):
        return
    server = os.getenv("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
    try:
        requests.post(f"{server}/{topic}", data=message.encode("utf-8"), timeout=10,
                      headers={"Title": titre.encode("utf-8"), "Tags": tags, "Priority": priorite})
    except requests.RequestException as e:  # une notification ratée ne doit jamais gêner le trading
        log.info("notification non envoyée : %s", e)
