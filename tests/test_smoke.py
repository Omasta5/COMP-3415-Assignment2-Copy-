"""A small starting test suite for the order desk."""

from pathlib import Path
import tempfile
import unittest

from supplydesk.service import OrderService


class OrderSmokeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "state.json"
        self.service = OrderService(self.path)

    def test_regular_pickup_quote(self):
        quote = self.service.quote("regular", [{"product_id": "notebook", "quantity": 2}])
        self.assertEqual(quote["subtotal_cents"], 1000)
        self.assertEqual(quote["discount_cents"], 0)
        self.assertEqual(quote["delivery_cents"], 0)
        self.assertEqual(quote["total_cents"], 1000)

    def test_student_delivery_quote(self):
        quote = self.service.quote("student", [{"product_id": "hoodie", "quantity": 2}], "delivery")
        self.assertEqual(quote["discount_cents"], 800)
        self.assertEqual(quote["delivery_cents"], 600)
        self.assertEqual(quote["total_cents"], 7800)

    def test_order_can_be_reopened(self):
        order = self.service.place_order("regular", [{"product_id": "mug", "quantity": 1}])
        self.assertEqual(order["order_id"], "ORD-0001")
        self.assertEqual(order["status"], "placed")
        self.assertEqual(OrderService(self.path).get_order(order["order_id"]), order)

    def test_cancel_order_restores_stock(self):
        before = self.service.catalog()
        order = self.service.place_order("regular", [{"product_id": "pen-pack", "quantity": 2}])
        cancelled = self.service.cancel_order(order["order_id"])
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual(self.service.catalog(), before)

# The following tests below are for Task 2

    def test_student_discount_is_applied_when_appropriate(self):
        quote = self.service.quote("student", [{"product_id": "notebook", "quantity": 1}])
        self.assertEqual(quote["discount_cents"], 0)
        self.assertEqual(quote["total_cents"], 500)

    def test_quantity_99_is_accepted_when_stock_is_available(self):
        state = self.service.store.load()
        state["catalog"][0]["stock"] = 99
        self.service.store.save(state)
        quote = self.service.quote("regular", [{"product_id": "notebook", "quantity": 99}])
        self.assertEqual(quote["items"][0]["quantity"], 99)
        self.assertEqual(quote["total_cents"], 49500)

    def test_cannot_cancel_nonexistent_order(self):
        with self.assertRaises(ValueError):
            self.service.cancel_order("nonexistent-order")

    def test_cancelling_order_twice_does_not_restore_stock_twice(self):
        order = self.service.place_order("regular", [{"product_id": "pen-pack", "quantity": 2}])
        self.service.cancel_order(order["order_id"])
        stock_after_first_cancel = self.service.catalog()
        self.service.cancel_order(order["order_id"])
        stock_after_second_cancel = self.service.catalog()
        self.assertEqual(stock_after_second_cancel, stock_after_first_cancel)

    # The following are the tests created for testing CR-01 implementaions for task 5
    
    def test_express_delivery_fee_is_applied_to_orders(self):
        items = [{"product_id": "hoodie", "quantity": 3}]

        order = self.service.place_order("regular", items, "express")

        self.assertEqual(order["fulfillment"], "express")
        self.assertEqual(order["subtotal_cents"], 12000)
        self.assertEqual(order["delivery_cents"], 1200)
        self.assertEqual(order["total_cents"], 13200)


    def test_express_delivery_fee_is_included_in_quotes(self):
        items = [{"product_id": "notebook", "quantity": 2}]

        quote = self.service.quote("regular", items, "express")

        self.assertEqual(quote["fulfillment"], "express")
        self.assertEqual(quote["subtotal_cents"], 1000)
        self.assertEqual(quote["delivery_cents"], 1200)
        self.assertEqual(quote["total_cents"], 2200)


    def test_student_discount_and_express_delivery_are_calculated_together(self):
        items = [{"product_id": "hoodie", "quantity": 2}]

        quote = self.service.quote("student", items, "express")

        self.assertEqual(quote["subtotal_cents"], 8000)
        self.assertEqual(quote["discount_cents"], 800)
        self.assertEqual(quote["delivery_cents"], 1200)
        self.assertEqual(quote["total_cents"], 8400)


    def test_standard_delivery_and_pickup_calculations_remain_unchanged(self):
        items = [{"product_id": "notebook", "quantity": 2}]

        standard_quote = self.service.quote("regular", items, "delivery")
        pickup_quote = self.service.quote("regular", items, "pickup")

        # Standard delivery retains its existing $6.00 fee.
        self.assertEqual(standard_quote["delivery_cents"], 600)
        self.assertEqual(standard_quote["total_cents"], 1600)

        # Pickup continues to have no delivery fee.
        self.assertEqual(pickup_quote["delivery_cents"], 0)
        self.assertEqual(pickup_quote["total_cents"], 1000)

        # Standard delivery is still free above the $100 threshold.
        larger_items = [{"product_id": "hoodie", "quantity": 3}]
        free_delivery_quote = self.service.quote(
            "regular", larger_items, "delivery"
        )

        self.assertEqual(free_delivery_quote["delivery_cents"], 0)
        self.assertEqual(free_delivery_quote["total_cents"], 12000)
    

if __name__ == "__main__":
    unittest.main()
