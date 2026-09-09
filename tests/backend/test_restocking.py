"""
Tests for restocking API endpoints.
"""
import re
from datetime import datetime

import pytest


class TestRestockingEndpoints:
    """Test suite for restocking-related endpoints."""

    def _sample_items(self):
        return [
            {"sku": "SKU-001", "name": "Test Widget", "quantity": 10, "unit_cost": 5.5},
            {"sku": "SKU-002", "name": "Test Gadget", "quantity": 3, "unit_cost": 12.0},
        ]

    def test_create_restock_order_returns_expected_shape(self, client):
        """Test that submitting a restock order returns a well-formed order."""
        payload = {"items": self._sample_items(), "total_budget": 500.0}
        response = client.post("/api/restocking/orders", json=payload)
        assert response.status_code == 201

        order = response.json()
        assert "id" in order
        assert re.match(r"^RSO-2025-\d{4}$", order["order_number"])
        assert order["status"] == "Processing"
        assert 3 <= order["lead_time_days"] <= 14

        order_date = datetime.strptime(order["order_date"], "%Y-%m-%d")
        expected_delivery = datetime.strptime(order["expected_delivery"], "%Y-%m-%d")
        assert (expected_delivery - order_date).days == order["lead_time_days"]

        expected_total = sum(item["quantity"] * item["unit_cost"] for item in self._sample_items())
        assert abs(order["total_value"] - expected_total) < 0.01
        assert len(order["items"]) == 2

    def test_get_restock_orders_lists_created_order(self, client):
        """Test that a created restock order appears in the GET list."""
        payload = {"items": self._sample_items(), "total_budget": 500.0}
        create_response = client.post("/api/restocking/orders", json=payload)
        created_order = create_response.json()

        response = client.get("/api/restocking/orders")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert any(order["id"] == created_order["id"] for order in data)

    def test_create_restock_order_rejects_empty_items(self, client):
        """Test that submitting a restock order with no items is rejected."""
        payload = {"items": [], "total_budget": 100.0}
        response = client.post("/api/restocking/orders", json=payload)
        assert response.status_code == 400

        data = response.json()
        assert "detail" in data

    def test_create_restock_order_rejects_non_positive_quantity(self, client):
        """Test that submitting a restock order with a zero/negative quantity is rejected."""
        payload = {
            "items": [{"sku": "SKU-001", "name": "Test Widget", "quantity": 0, "unit_cost": 5.5}],
            "total_budget": 100.0,
        }
        response = client.post("/api/restocking/orders", json=payload)
        assert response.status_code == 400

        data = response.json()
        assert "detail" in data
