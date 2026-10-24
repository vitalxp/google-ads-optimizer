from __future__ import annotations

from typing import Any

from google.ads.googleads.client import GoogleAdsClient

from ads_optimizer.ids import format_customer_id


def get_customer_meta(client: GoogleAdsClient, customer_id: str) -> dict[str, Any]:
    cid = format_customer_id(customer_id)
    query = """
        SELECT
          customer.id,
          customer.descriptive_name,
          customer.currency_code,
          customer.time_zone,
          customer.manager
        FROM customer
        LIMIT 1
    """
    service = client.get_service("GoogleAdsService")
    rows = list(service.search(customer_id=cid, query=query))
    if not rows:
        return {
            "id": cid,
            "name": "",
            "currency_code": "USD",
            "time_zone": "",
            "manager": False,
        }
    c = rows[0].customer
    return {
        "id": str(c.id),
        "name": c.descriptive_name or "",
        "currency_code": c.currency_code or "USD",
        "time_zone": c.time_zone or "",
        "manager": bool(c.manager),
    }


def list_client_accounts_under_manager(
    client: GoogleAdsClient, manager_id: str
) -> list[dict[str, Any]]:
    mid = format_customer_id(manager_id)
    query = """
        SELECT
          customer_client.client_customer,
          customer_client.descriptive_name,
          customer_client.currency_code,
          customer_client.manager,
          customer_client.status,
          customer_client.level
        FROM customer_client
        WHERE customer_client.status = 'ENABLED'
          AND customer_client.manager = FALSE
          AND customer_client.level = 1
    """
    service = client.get_service("GoogleAdsService")
    out: list[dict[str, Any]] = []
    for row in service.search(customer_id=mid, query=query):
        resource = row.customer_client.client_customer  # customers/123
        cid = format_customer_id(resource.split("/")[-1])
        out.append(
            {
                "id": cid,
                "name": row.customer_client.descriptive_name or "",
                "currency_code": row.customer_client.currency_code or "",
                "manager": False,
                "resource_name": resource,
            }
        )
    return out


def resolve_operating_account(
    client: GoogleAdsClient, preferred_customer_id: str
) -> dict[str, Any]:
    """If preferred ID is MCC, switch to first linked client account."""
    preferred = format_customer_id(preferred_customer_id)
    meta = get_customer_meta(client, preferred)
    if not meta.get("manager"):
        return {
            "customer_id": preferred,
            "login_customer_id": None,
            "account": meta,
            "switched_from_manager": False,
        }

    clients = list_client_accounts_under_manager(client, preferred)
    if not clients:
        # Fallback: accessible customers that are not managers
        from ads_optimizer.insights import list_accessible_accounts

        for acc in list_accessible_accounts(client):
            if acc["id"] == preferred:
                continue
            try:
                m = get_customer_meta(client, acc["id"])
            except Exception:
                continue
            if not m.get("manager"):
                clients.append({**acc, **m})
                break

    if not clients:
        raise RuntimeError(
            f"Аккаунт {preferred} — manager (MCC). "
            "Укажите GOOGLE_ADS_CUSTOMER_ID клиентского аккаунта и "
            "GOOGLE_ADS_LOGIN_CUSTOMER_ID MCC в .env."
        )

    chosen = clients[0]
    return {
        "customer_id": chosen["id"],
        "login_customer_id": preferred,
        "account": {
            "id": chosen["id"],
            "name": chosen.get("name") or "",
            "currency_code": chosen.get("currency_code") or "USD",
            "time_zone": "",
            "manager": False,
        },
        "manager": meta,
        "switched_from_manager": True,
        "available_clients": clients,
    }


def pick_operating_account(client: GoogleAdsClient) -> dict[str, Any]:
    """Pick the first client account when customer id is unset or dummy."""
    from ads_optimizer.insights import list_accessible_accounts

    accounts = list_accessible_accounts(client)
    if not accounts:
        raise RuntimeError(
            "No accessible Google Ads accounts for this Google login. "
            "Confirm the developer token and that the signed-in user can see the account."
        )

    clients: list[dict[str, Any]] = []
    managers: list[dict[str, Any]] = []
    for acc in accounts:
        try:
            meta = get_customer_meta(client, acc["id"])
        except Exception:
            continue
        row = {**acc, **meta}
        if meta.get("manager"):
            managers.append(row)
        else:
            clients.append(row)

    if clients:
        chosen = clients[0]
        return {
            "customer_id": chosen["id"],
            "login_customer_id": None,
            "account": {
                "id": chosen["id"],
                "name": chosen.get("name") or "",
                "currency_code": chosen.get("currency_code") or "USD",
                "time_zone": chosen.get("time_zone") or "",
                "manager": False,
            },
            "switched_from_manager": False,
            "available_clients": clients,
        }
    if managers:
        return resolve_operating_account(client, managers[0]["id"])

    first = accounts[0]
    return {
        "customer_id": first["id"],
        "login_customer_id": None,
        "account": {
            "id": first["id"],
            "name": first.get("name") or first["id"],
            "currency_code": "USD",
            "time_zone": "",
            "manager": False,
        },
        "switched_from_manager": False,
        "available_clients": accounts,
    }
