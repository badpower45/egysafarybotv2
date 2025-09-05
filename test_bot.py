import unittest
from bot import find_route_logic

class TestRouteLogic(unittest.TestCase):
    def test_direct_route(self):
        routes = [
            {"routeName": "Route 1", "keyPoints": ["A", "B", "C", "D"], "fare": "5 جنيه"},
        ]
        result = find_route_logic("A", "D", routes)
        self.assertIn("Route 1", result)

    def test_no_route(self):
        routes = [
            {"routeName": "Route 1", "keyPoints": ["A", "B", "C"], "fare": "5 جنيه"},
        ]
        result = find_route_logic("A", "E", routes)
        self.assertIn("❌", result)

    def test_transfer_route(self):
        routes = [
            {"routeName": "Route 1", "keyPoints": ["A", "B", "C"], "fare": "5 جنيه"},
            {"routeName": "Route 2", "keyPoints": ["C", "D", "E"], "fare": "7 جنيه"},
        ]
        result = find_route_logic("A", "E", routes)
        self.assertIn("تبديل مطلوب", result)

if __name__ == "__main__":
    unittest.main()