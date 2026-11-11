"""Operations used by the command-line order desk."""

from supplydesk.storage import JsonStore

# Order configuration constants
MINIMUM_ORDER_QUANTITY = 1
MAXIMUM_ORDER_QUANTITY = 99

STUDENT_DISCOUNT_THRESHOLD_CENTS = 5000
STUDENT_DISCOUNT_PERCENT = 10
PERCENTAGE_BASE = 100
ROUNDING_ADJUSTMENT = 50

FREE_DELIVERY_THRESHOLD_CENTS = 10000
DELIVERY_FEE_CENTS = 600
EXPRESS_DELIVERY_FEE_CENTS = 1200

ORDER_ID_PADDING_LENGTH = 4

class OrderService:
    def __init__(self, state_path=".supplydesk/state.json"):
        self.store = JsonStore(state_path)

    def catalog(self):
        return self.store.load()["catalog"]

    def quote(self, customer_type, items, fulfillment="pickup"):
        state = self.store.load()
        return self._build_quote(
            state, customer_type, items, fulfillment
    )

    def place_order(self, customer_type, items, fulfillment="pickup"):
        state = self.store.load()
        quote = self._build_quote(
            state, customer_type, items, fulfillment
        )

        order = {
            "order_id": "ORD-" + str(state["next_order_number"]).zfill(ORDER_ID_PADDING_LENGTH),
            "status": "placed",
            **quote,
        }

        for line in quote["items"]:
            product = self._find_product(state, line["product_id"])
            if product is not None:
                product["stock"] -= line["quantity"]

        state["next_order_number"] += 1
        state["orders"].append(order)
        self.store.save(state)
        return order

    def _find_product(self, state, product_id):
        for product in state["catalog"]:
            if product["product_id"] == product_id:
                return product
        return None

    def _find_order(self, state, order_id):
        for order in state["orders"]:
            if order["order_id"] == order_id:
                return order
        raise ValueError("Unknown order: " + order_id)

    def _build_quote(self, state, customer_type, items, fulfillment):
        if customer_type not in ("regular", "student"):
            raise ValueError("Customer type must be regular or student.")

        if fulfillment not in ("pickup", "delivery", "express"):
            raise ValueError("Fulfillment must be pickup, delivery, or express.")

        if not isinstance(items, list) or not items:
            raise ValueError("An order must contain at least one item.")

        lines = []
        subtotal = 0

        for item in items:
            if not isinstance(item, dict):
                raise ValueError("Each item must contain a product_id and quantity.")

            product = self._find_product(state, item.get("product_id"))

            if product is None:
                raise ValueError("Unknown product.")

            quantity = item.get("quantity")

            if (
                type(quantity) is not int
                or quantity < MINIMUM_ORDER_QUANTITY
                or quantity > MAXIMUM_ORDER_QUANTITY
            ):
                raise ValueError(
                    f"Quantity must be an integer from "
                    f"{MINIMUM_ORDER_QUANTITY} to {MAXIMUM_ORDER_QUANTITY}."
                )

            if quantity > product["stock"]:
                raise ValueError("Not enough stock for " + product["product_id"] + ".")

            line_total = product["unit_price_cents"] * quantity
            subtotal += line_total

            lines.append({
                "product_id": product["product_id"],
                "name": product["name"],
                "unit_price_cents": product["unit_price_cents"],
                "quantity": quantity,
                "line_total_cents": line_total,
            })

        discount = 0

        if (
            customer_type == "student"
            and subtotal > STUDENT_DISCOUNT_THRESHOLD_CENTS
        ):
            discount = (
                subtotal * STUDENT_DISCOUNT_PERCENT + ROUNDING_ADJUSTMENT
            ) // PERCENTAGE_BASE

        delivery = 0

        if fulfillment == "express":
            delivery = EXPRESS_DELIVERY_FEE_CENTS
        elif (
            fulfillment == "delivery"
            and subtotal - discount < FREE_DELIVERY_THRESHOLD_CENTS
        ):
            delivery = DELIVERY_FEE_CENTS

        return {
            "customer_type": customer_type,
            "fulfillment": fulfillment,
            "items": lines,
            "subtotal_cents": subtotal,
            "discount_cents": discount,
            "delivery_cents": delivery,
            "total_cents": subtotal - discount + delivery,
        }

    def list_orders(self):
        return self.store.load()["orders"]

    def get_order(self, order_id):
        state = self.store.load()
        return self._find_order(state, order_id)

    def cancel_order(self, order_id):
        state = self.store.load()
        order = self._find_order(state, order_id)

        if order["status"] == "cancelled":
            return order

        for line in order["items"]:
            for product in state["catalog"]:
                if product["product_id"] == line["product_id"]:
                    product["stock"] += line["quantity"]

        order["status"] = "cancelled"
        self.store.save(state)
        return order
