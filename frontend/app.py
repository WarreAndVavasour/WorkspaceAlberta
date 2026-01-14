from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from flask import Flask, Response, redirect, render_template, request, session, url_for

CATALOG_PATH = Path(__file__).resolve().parent.parent / "generator" / "catalog.json"

EXAMPLE_PROBLEMS = [
    {
        "title": "Track customer conversations",
        "description": (
            "I need to keep track of customer support conversations from Zendesk and "
            "match them with payment data in Stripe to understand which customers are having issues."
        ),
    },
    {
        "title": "Automate invoice reminders",
        "description": (
            "I want to automatically send reminder emails through SendGrid when QuickBooks "
            "invoices are overdue by more than 7 days."
        ),
    },
    {
        "title": "Sync project updates",
        "description": (
            "When tasks in Asana are marked complete, I need to update our client in Slack "
            "and log the hours in our time tracking spreadsheet."
        ),
    },
    {
        "title": "Analyze sales pipeline",
        "description": (
            "I need a weekly report that pulls deals from HubSpot, calculates conversion rates, "
            "and creates a summary document in Google Docs."
        ),
    },
]

STATUS_BADGES = {
    "native": "Ready",
    "openapi": "API",
    "proxy": "Custom",
    "hosted": "Cloud",
}

app = Flask(__name__)
app.secret_key = os.environ.get("WORKSPACEALBERTA_SECRET_KEY", "workspacealberta-dev")


def _load_catalog() -> list[dict[str, Any]]:
    data = CATALOG_PATH.read_text(encoding="utf-8")
    return json.loads(data)


CATALOG = _load_catalog()
CATALOG_BY_ID = {tool["id"]: tool for tool in CATALOG}
CATEGORIES = ["all"] + sorted({tool["category"] for tool in CATALOG})


def _get_selected_tools() -> list[str]:
    return session.get("selected_tools", [])


def _set_selected_tools(selected: list[str]) -> None:
    session["selected_tools"] = selected


def _get_problem() -> str:
    return session.get("problem_description", "")


def _set_problem(description: str) -> None:
    session["problem_description"] = description


def _filter_tools(search: str, category: str) -> list[dict[str, Any]]:
    search_lower = search.lower().strip()
    filtered: list[dict[str, Any]] = []
    for tool in CATALOG:
        matches_search = (
            search_lower in tool["display_name"].lower()
            or search_lower in tool["description"].lower()
            if search_lower
            else True
        )
        matches_category = category == "all" or tool["category"] == category
        if matches_search and matches_category:
            filtered.append(tool)
    return filtered


@app.route("/")
def index() -> str:
    return render_template("index.html")


@app.route("/tools", methods=["GET", "POST"])
def tools() -> str | Response:
    if request.method == "POST":
        selected = request.form.getlist("tools")
        if selected:
            _set_selected_tools(selected)
            return redirect(url_for("problem"))
        _set_selected_tools([])

    selected = _get_selected_tools()
    search_query = request.args.get("q", "")
    filter_category = request.args.get("category", "all")
    filtered_tools = _filter_tools(search_query, filter_category)

    return render_template(
        "tools.html",
        tools=filtered_tools,
        selected=selected,
        categories=CATEGORIES,
        search_query=search_query,
        filter_category=filter_category,
        status_badges=STATUS_BADGES,
    )


@app.route("/problem", methods=["GET", "POST"])
def problem() -> str | Response:
    error_message = ""
    selected_example = request.args.get("example")

    if request.method == "POST":
        description = request.form.get("description", "").strip()
        word_count = len([word for word in description.split() if word])
        if word_count < 10:
            error_message = "Please use at least 10 words so we can understand the problem."
        else:
            _set_problem(description)
            return redirect(url_for("preview"))
    else:
        description = _get_problem()
        if selected_example is not None and selected_example.isdigit():
            index = int(selected_example)
            if 0 <= index < len(EXAMPLE_PROBLEMS):
                description = EXAMPLE_PROBLEMS[index]["description"]

    word_count = len([word for word in description.split() if word]) if description else 0

    return render_template(
        "problem.html",
        description=description,
        word_count=word_count,
        error_message=error_message,
        examples=EXAMPLE_PROBLEMS,
        selected_example=selected_example,
    )


@app.route("/preview")
def preview() -> str | Response:
    selected_ids = _get_selected_tools()
    if not selected_ids:
        return redirect(url_for("tools"))

    description = _get_problem()
    if not description:
        return redirect(url_for("problem"))

    selected_tools = [
        CATALOG_BY_ID[tool_id]
        for tool_id in selected_ids
        if tool_id in CATALOG_BY_ID
    ]

    command_string = "python -m generator.generator " + " ".join(selected_ids)

    return render_template(
        "preview.html",
        description=description,
        selected_tools=selected_tools,
        selected_ids=selected_ids,
        command_string=command_string,
    )


@app.route("/download")
def download() -> Response:
    selected_ids = _get_selected_tools()
    description = _get_problem()
    if not selected_ids or not description:
        return redirect(url_for("preview"))

    tool_lines = "\n".join(
        f"- {CATALOG_BY_ID[tool_id]['display_name']} "
        f"({CATALOG_BY_ID[tool_id]['category']})"
        for tool_id in selected_ids
        if tool_id in CATALOG_BY_ID
    )

    content = f"""# WorkspaceAlberta Configuration

## Problem Statement
{description}

## Selected Tools ({len(selected_ids)})
{tool_lines}

## Next Steps
1. Clone the WorkspaceAlberta repository
2. Run the generator with these tool IDs:
   python -m generator.generator {' '.join(selected_ids)}
3. Fill in your API keys in the generated .env file
4. Open the workspace in Cursor IDE

---
Generated with WorkspaceAlberta
Built for Alberta entrepreneurs
"""

    return Response(
        content,
        headers={
            "Content-Disposition": "attachment; filename=workspace-config.md"
        },
        mimetype="text/markdown",
    )


@app.route("/reset")
def reset() -> Response:
    session.clear()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)
