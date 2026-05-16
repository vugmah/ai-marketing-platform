"""Pilot Onboarding Tracker

Tracks customer onboarding progress and identifies blockers.
Usage: cd backend && python scripts/staging/pilot_onboarding_tracker.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

ONBOARDING_STEPS = [
    ("tenant_provisioned", "Day 0: Tenant Provisioned"),
    ("welcome_sent", "Day 0: Welcome Email Sent"),
    ("branches_setup", "Day 1: Branches Setup"),
    ("users_invited", "Day 1: Users Invited"),
    ("whatsapp_connected", "Day 2: WhatsApp Connected"),
    ("instagram_connected", "Day 2: Instagram Connected"),
    ("facebook_connected", "Day 2: Facebook Connected"),
    ("erp_connected", "Day 3: ERP Connected (Read-Only)"),
    ("erp_validated", "Day 3: ERP Data Validated"),
    ("knowledge_uploaded", "Day 4: Knowledge Base Uploaded"),
    ("ai_validated", "Day 4: AI Training Validated"),
    ("first_report", "Day 5: First Report Generated"),
    ("first_ai_support", "Day 5: First AI Support Interaction"),
    ("first_campaign_draft", "Day 5: First Campaign Created"),
    ("weekly_review", "Day 6-7: Weekly Review"),
]

# Simulated pilot customer data
PILOT_CUSTOMERS = [
    {
        "tenant_id": "pilot_001",
        "name": "Demo Market",
        "start_date": "2026-05-10",
        "steps_completed": [
            "tenant_provisioned", "welcome_sent", "branches_setup",
            "users_invited", "whatsapp_connected", "instagram_connected",
            "erp_connected", "knowledge_uploaded", "first_report",
        ],
        "current_blocker": "erp_validated",
        "support_tickets": 2,
        "ai_interactions": 15,
        "satisfaction": 8,
    },
    {
        "tenant_id": "pilot_002",
        "name": "TechStore Istanbul",
        "start_date": "2026-05-12",
        "steps_completed": [
            "tenant_provisioned", "welcome_sent", "branches_setup",
            "users_invited", "whatsapp_connected",
        ],
        "current_blocker": "instagram_connected",
        "support_tickets": 4,
        "ai_interactions": 3,
        "satisfaction": 6,
    },
    {
        "tenant_id": "pilot_003",
        "name": "Cafe Network",
        "start_date": "2026-05-14",
        "steps_completed": [
            "tenant_provisioned", "welcome_sent", "branches_setup",
        ],
        "current_blocker": "users_invited",
        "support_tickets": 1,
        "ai_interactions": 0,
        "satisfaction": None,
    },
]


def calculate_progress(customer: dict) -> dict:
    total = len(ONBOARDING_STEPS)
    completed = len(customer["steps_completed"])
    pct = round((completed / total) * 100, 1)

    # Find current step
    current_step = None
    for step_id, step_name in ONBOARDING_STEPS:
        if step_id not in customer["steps_completed"]:
            current_step = step_name
            break

    return {
        "total_steps": total,
        "completed": completed,
        "percentage": pct,
        "current_step": current_step or "COMPLETE",
        "days_since_start": (datetime.now() - datetime.strptime(customer["start_date"], "%Y-%m-%d")).days,
    }


def identify_blockers() -> list:
    blockers = []
    blocker_frequency = {}

    for customer in PILOT_CUSTOMERS:
        if customer["current_blocker"]:
            b = customer["current_blocker"]
            blocker_frequency[b] = blocker_frequency.get(b, 0) + 1
            blockers.append({
                "tenant": customer["tenant_id"],
                "name": customer["name"],
                "blocker": b,
                "tickets": customer["support_tickets"],
            })

    return blockers, blocker_frequency


def main() -> int:
    print("=" * 60)
    print("PILOT ONBOARDING TRACKER")
    print(f"Report Date: {datetime.now().strftime('%Y-%m-%d')}")
    print("=" * 60)

    total_customers = len(PILOT_CUSTOMERS)
    total_steps = len(ONBOARDING_STEPS)

    print(f"\n--- Customer Progress ({total_customers} pilot customers) ---")
    overall_progress = 0
    for customer in PILOT_CUSTOMERS:
        progress = calculate_progress(customer)
        overall_progress += progress["percentage"]
        status = "COMPLETE" if progress["percentage"] == 100 else "IN PROGRESS"
        print(f"\n  {customer['name']} ({customer['tenant_id']})")
        print(f"    Status: {status} | Progress: {progress['completed']}/{progress['total_steps']} ({progress['percentage']}%)")
        print(f"    Current: {progress['current_step']}")
        print(f"    Days: {progress['days_since_start']} | Tickets: {customer['support_tickets']} | AI interactions: {customer['ai_interactions']}")
        if customer['satisfaction']:
            print(f"    Satisfaction: {customer['satisfaction']}/10")

    avg_progress = round(overall_progress / total_customers, 1)
    print(f"\n--- Overall Metrics ---")
    print(f"  Average completion: {avg_progress}%")
    print(f"  Total customers: {total_customers}")
    print(f"  Total steps per customer: {total_steps}")

    # Blockers
    print(f"\n--- Active Blockers ---")
    blockers, freq = identify_blockers()
    for b in blockers:
        print(f"  [{b['tenant']}] {b['blocker']} ({b['tickets']} tickets)")

    print(f"\n--- Blocker Frequency ---")
    for blocker, count in sorted(freq.items(), key=lambda x: -x[1]):
        print(f"  {blocker}: {count} customer(s)")

    # Save report
    report = {
        "generated_at": datetime.now().isoformat(),
        "customers": PILOT_CUSTOMERS,
        "overall_completion_pct": avg_progress,
        "blocker_frequency": freq,
        "recommendations": [
            f"Most common blocker: {max(freq, key=freq.get) if freq else 'None'}" if freq else "No active blockers",
            f"Focus support on: {', '.join([b['tenant'] for b in blockers[:2]])}" if len(blockers) >= 2 else f"Focus on: {blockers[0]['tenant']}" if blockers else "All on track",
        ],
    }

    output_path = PROJECT_ROOT / "scripts" / "staging" / "pilot_onboarding_status.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n{'=' * 60}")
    print(f"Report saved: {output_path}")
    print(f"Average completion: {avg_progress}%")
    if freq:
        print(f"Active blockers: {len(blockers)}")
        print(f"Most common: {max(freq, key=freq.get)}")
    else:
        print("No active blockers")

    if avg_progress >= 80:
        print("STATUS: Onboarding ON TRACK")
        return 0
    elif avg_progress >= 50:
        print("STATUS: Onboarding NEEDS ATTENTION")
        return 0
    else:
        print("STATUS: Onboarding AT RISK")
        return 1


if __name__ == "__main__":
    sys.exit(main())
